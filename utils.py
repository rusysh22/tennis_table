import json
import os
import shutil
import threading
import base64
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from domain.scoring import RuleProfile, validate_match_score, validate_point_split_score, validate_score

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
_LOCK = threading.Lock()


class MatchNotFoundError(LookupError):
    pass


class MatchVersionConflictError(RuntimeError):
    pass

def now_wib(timezone_name=None):
    return datetime.now(
        ZoneInfo(
            timezone_name
            or os.environ.get("TOURNAMENT_TIMEZONE", "Asia/Jakarta")
        )
    )

BAD_WORDS = {
    "anjing", "babi", "monyet", "kunyuk", "bangsat", "bajingan", "tolol", "goblok", "bego", 
    "idiot", "kampret", "keparat", "kontol", "memek", "jembut", "ngentot", "perek", "pelacur",
    "jablay", "sialan", "jancok", "dancok", "pantek", "telek", "tai", "asu", "bgst", "anjg", "gblk",
    "picek", "buta", "budeg", "pincang"
}

import re
def censor_text(text):
    if not text:
        return text
    
    # Split text into words, but keep whitespace so we can reconstruct
    words = re.split(r'(\s+)', text)
    censored_words = []
    
    for w in words:
        if not w.strip():
            censored_words.append(w)
            continue
            
        clean_w = ''.join(c for c in w if c.isalnum()).lower()
        if clean_w in BAD_WORDS:
            # Replace alphanumeric characters with '*', preserve punctuation
            censored_w = ''.join('*' if c.isalnum() else c for c in w)
            censored_words.append(censored_w)
        else:
            censored_words.append(w)
            
    return "".join(censored_words)

# Penyimpanan data: legacy tetap menjadi default dan dapat memakai file JSON atau
# dokumen JSONB di skema `tennis`. Backend normalized adalah cutover eksplisit;
# DATABASE_URL saja tidak pernah mengaktifkannya secara tidak sengaja.
DATABASE_URL = os.environ.get("DATABASE_URL")
STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "legacy").strip().lower()
if STORAGE_BACKEND not in {"legacy", "normalized"}:
    raise RuntimeError("STORAGE_BACKEND must be either 'legacy' or 'normalized'.")

USE_NORMALIZED_DB = STORAGE_BACKEND == "normalized"
USE_DB = bool(DATABASE_URL) and not USE_NORMALIZED_DB
_NORMALIZED_REPOSITORY = None

if USE_NORMALIZED_DB:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required when STORAGE_BACKEND=normalized.")
    from intersport_core.live_repository import (
        NormalizedMatchNotFound,
        NormalizedRepository,
        NormalizedRepositoryError,
        NormalizedVersionConflict,
    )

    _NORMALIZED_REPOSITORY = NormalizedRepository(
        DATABASE_URL, os.environ.get("TOURNAMENT_SLUG")
    )

if USE_DB:
    import psycopg2
    import psycopg2.extras

    def _new_conn():
        return psycopg2.connect(DATABASE_URL)

    def _db_conn():
        """Satu koneksi dipakai ulang untuk seluruh request Flask yang sama
        (disimpan di flask.g), supaya load_json/save_json yang dipanggil
        berkali-kali dalam 1 request (mis. data_context() + context processor)
        tidak buka koneksi baru tiap kali -- connect ke Supabase pooler makan
        ~500-600ms sekali connect, jadi kalau diulang 3-4x per halaman itu
        beberapa detik sendiri. Di luar konteks request Flask (mis. skrip
        migrate_db.py), balik ke koneksi baru biasa."""
        from flask import g, has_app_context
        if has_app_context():
            conn = getattr(g, "_pg_conn", None)
            if conn is None or conn.closed:
                conn = _new_conn()
                g._pg_conn = conn
            return conn
        return _new_conn()

    def _close_legacy_request_connection():
        from flask import g
        conn = g.pop("_pg_conn", None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    def _ensure_schema():
        conn = _new_conn()
        with conn, conn.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS tennis")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tennis.app_data (
                    name TEXT PRIMARY KEY,
                    data JSONB NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tennis.app_data_backups (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    data JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """)
            conn.commit()
        conn.close()

    _ensure_schema()


def close_request_connection():
    """Close whichever per-request PostgreSQL connection is active."""
    if USE_DB:
        _close_legacy_request_connection()
    if USE_NORMALIZED_DB:
        _NORMALIZED_REPOSITORY.close_request_connection()

DAY_NAMES = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
MONTH_NAMES = [
    "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]


def _path(name):
    return os.path.join(DATA_DIR, name)


def load_json(name):
    if USE_NORMALIZED_DB:
        loaders = {
            "config.json": _NORMALIZED_REPOSITORY.load_config,
            "teams.json": _NORMALIZED_REPOSITORY.load_teams,
            "matches.json": _NORMALIZED_REPOSITORY.load_matches,
        }
        try:
            return loaders[name]()
        except KeyError as exc:
            raise ValueError(f"Normalized storage does not expose {name!r}.") from exc
    if USE_DB:
        key = name.replace(".json", "")
        with _db_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT data FROM tennis.app_data WHERE name = %s", (key,))
            row = cur.fetchone()
        if row is None:
            # Belum ada di DB (mis. pertama kali deploy) -> seed dari file
            # bawaan yang ikut ter-deploy, supaya tidak perlu migrasi manual.
            with open(_path(name), "r", encoding="utf-8") as f:
                data = json.load(f)
            save_json(name, data)
            return data
        return row[0]
    with _LOCK:
        with open(_path(name), "r", encoding="utf-8") as f:
            return json.load(f)


def save_json(name, data):
    if USE_NORMALIZED_DB:
        raise RuntimeError(
            "Generic JSON writes are disabled for normalized storage; "
            "use an entity-specific repository operation."
        )
    if USE_DB:
        key = name.replace(".json", "")
        with _db_conn() as conn, conn.cursor() as cur:
            cur.execute("""
                INSERT INTO tennis.app_data (name, data, updated_at) VALUES (%s, %s, now())
                ON CONFLICT (name) DO UPDATE SET data = EXCLUDED.data, updated_at = now()
            """, (key, psycopg2.extras.Json(data)))
            conn.commit()
        return
    with _LOCK:
        tmp = _path(name) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, _path(name))


def load_participants():
    return load_json("participants.json")


def save_participants(participants):
    if USE_NORMALIZED_DB:
        raise RuntimeError(
            "Whole-collection participant writes are disabled for normalized storage."
        )
    save_json("participants.json", participants)


def generate_participant_id(site_code, participants):
    """ID peserta baru, mis. 'BBL-01' -- diprefix kode site supaya gampang dibaca
    dan otomatis unik lintas site tanpa perlu koordinasi nomor global."""
    site_code = (site_code or "").strip().upper()
    existing = [
        int(pid.rsplit("-", 1)[-1])
        for pid in participants
        if pid.startswith(f"{site_code}-") and pid.rsplit("-", 1)[-1].isdigit()
    ]
    return f"{site_code}-{max(existing, default=0) + 1:02d}"


def upsert_participant(participants, site_code, name, id_number="", email="", photo=None, existing_id=None):
    """Cari peserta yang cocok (by id eksplisit, lalu NIK, lalu nama -- dalam site
    yang sama) dan perbarui datanya, atau buat baru kalau belum ada. Ini yang
    membuat satu orang tidak terdaftar berulang saat diinput ulang di form admin."""
    site_code = (site_code or "").strip().upper()
    pid = existing_id if existing_id in participants else None
    if not pid and id_number:
        pid = next(
            (k for k, v in participants.items()
             if v.get("site_code") == site_code and id_number and v.get("id_number") == id_number),
            None,
        )
    if not pid and name:
        pid = next(
            (k for k, v in participants.items()
             if v.get("site_code") == site_code and v.get("name", "").strip().lower() == name.strip().lower()),
            None,
        )
    if not pid:
        pid = generate_participant_id(site_code, participants)
    old = participants.get(pid, {})
    participants[pid] = {
        "name": name,
        "id_number": id_number,
        "email": email,
        "photo": photo if photo is not None else old.get("photo", ""),
        "site_code": site_code,
    }
    return pid


def _hydrate_team(team, participants):
    """Susun ulang field tampilan lama (player1, id_number1, reserves, dst) dari
    'members' (referensi participant_id + role) supaya seluruh kode pembaca tim
    yang sudah ada -- rute, template, standings -- tidak perlu tahu soal peserta
    yang kini disimpan terpisah di participants.json."""
    team = dict(team)
    members = team.get("members")
    if members is None:
        return team  # data lama/format lain (mis. fixture test) -- tampilkan apa adanya

    if team.get("entrant_type") == "roster":
        reserves = []
        for m in members:
            p = participants.get(m.get("participant_id"), {})
            reserves.append({
                "participant_id": m.get("participant_id"),
                "name": p.get("name", ""),
                "id_number": p.get("id_number", ""),
                "photo": p.get("photo", ""),
                "role": m.get("role", "putra"),
            })
        team["reserves"] = reserves
        return team

    by_role = {m.get("role"): m.get("participant_id") for m in members}
    for slot, role in (("1", "pemain1"), ("2", "pemain2")):
        pid = by_role.get(role)
        p = participants.get(pid, {}) if pid else {}
        team[f"participant_id{slot}"] = pid
        team[f"player{slot}"] = p.get("name", "")
        team[f"id_number{slot}"] = p.get("id_number", "")
        team[f"email{slot}"] = p.get("email", "")
        team[f"photo{slot}"] = p.get("photo", "")

    reserve_pid = by_role.get("cadangan")
    reserve = participants.get(reserve_pid, {}) if reserve_pid else {}
    team["reserve_participant_id"] = reserve_pid
    team["reserve_name"] = reserve.get("name", "")
    team["reserve_id_number"] = reserve.get("id_number", "")
    team["reserve_photo"] = reserve.get("photo", "")
    return team


def load_teams():
    teams = load_json("teams.json")
    if USE_NORMALIZED_DB:
        return teams
    participants = load_json("participants.json")
    return {code: _hydrate_team(t, participants) for code, t in teams.items()}


_HYDRATED_TEAM_FIELDS = (
    "player1", "player2", "id_number1", "id_number2", "email1", "email2",
    "photo1", "photo2", "participant_id1", "participant_id2", "reserves",
    "reserve_participant_id", "reserve_name", "reserve_id_number",
)


def save_teams(teams):
    if USE_NORMALIZED_DB:
        raise RuntimeError(
            "Whole-collection team writes are disabled for normalized storage."
        )
    # Callers that round-trip load_teams() -> mutate -> save_teams() (e.g.
    # auto_split_groups) get back the hydrated dict; strip the fields that
    # were derived from participants.json so teams.json stays members-only.
    cleaned = {
        code: (
            {k: v for k, v in t.items() if k not in _HYDRATED_TEAM_FIELDS}
            if "members" in t else t
        )
        for code, t in teams.items()
    }
    save_json("teams.json", cleaned)


def load_matches():
    return load_json("matches.json")


def save_matches(matches):
    if USE_NORMALIZED_DB:
        raise RuntimeError(
            "Whole-collection match writes are disabled for normalized storage."
        )
    save_json("matches.json", matches)


def _apply_match_update(matches, match_id, expected_version, updater):
    match = get_match(matches, match_id)
    if match is None:
        raise MatchNotFoundError(match_id)

    current_version = int(match.get("version", 0))
    if expected_version is not None and current_version != expected_version:
        raise MatchVersionConflictError(
            f"Match {match_id} changed from version {expected_version} to {current_version}."
        )

    schedule_fields = ("date", "time", "court", "team_a", "team_b")
    before_schedule = tuple(match.get(field) for field in schedule_fields)
    before_status = match.get("status")
    updater(match)
    after_schedule = tuple(match.get(field) for field in schedule_fields)
    if before_schedule != after_schedule or (
        before_status == "cancelled" and match.get("status") != "cancelled"
    ):
        conflicts = find_schedule_conflicts(matches, match, exclude_match_id=match_id)
        if conflicts:
            raise ValueError(" ".join(conflicts))
    match["version"] = current_version + 1
    return match


def find_schedule_conflicts(matches, candidate, exclude_match_id=None):
    """Detect same-slot court and entrant conflicts for one candidate match."""
    if (
        candidate.get("status") == "cancelled"
        or not candidate.get("date")
        or not candidate.get("time")
    ):
        return []
    candidate_entrants = {
        code for code in (candidate.get("team_a"), candidate.get("team_b")) if code
    }
    conflicts = []
    for other in matches:
        if other.get("id") == (exclude_match_id or candidate.get("id")):
            continue
        if other.get("status") == "cancelled":
            continue
        if (
            other.get("date") != candidate.get("date")
            or other.get("time") != candidate.get("time")
        ):
            continue
        if candidate.get("court") and other.get("court") == candidate.get("court"):
            conflicts.append(
                f"Bentrok lapangan dengan pertandingan {other.get('id')}."
            )
        other_entrants = {
            code for code in (other.get("team_a"), other.get("team_b")) if code
        }
        overlap = candidate_entrants & other_entrants
        if overlap:
            conflicts.append(
                "Bentrok peserta "
                f"{', '.join(sorted(overlap))} dengan pertandingan {other.get('id')}."
            )
    return conflicts


def update_match(match_id, updater, expected_version=None):
    """Atomically update one match and increment its optimistic-lock version.

    Both PostgreSQL backends use SELECT FOR UPDATE to prevent two workers from
    silently overwriting each other. The local JSON path holds the process lock
    for the complete read-modify-write cycle.
    """
    if USE_NORMALIZED_DB:
        try:
            return _NORMALIZED_REPOSITORY.update_match(
                match_id, updater, expected_version=expected_version
            )
        except NormalizedMatchNotFound as exc:
            raise MatchNotFoundError(match_id) from exc
        except NormalizedVersionConflict as exc:
            raise MatchVersionConflictError(str(exc)) from exc
        except NormalizedRepositoryError as exc:
            raise ValueError(str(exc)) from exc

    if USE_DB:
        key = "matches"
        with _db_conn() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT data FROM tennis.app_data WHERE name = %s FOR UPDATE",
                (key,),
            )
            row = cur.fetchone()
            if row is None:
                with open(_path("matches.json"), "r", encoding="utf-8") as source:
                    matches = json.load(source)
            else:
                matches = row[0]

            updated = _apply_match_update(
                matches, match_id, expected_version, updater
            )
            cur.execute(
                """
                INSERT INTO tennis.app_data (name, data, updated_at)
                VALUES (%s, %s, now())
                ON CONFLICT (name) DO UPDATE
                SET data = EXCLUDED.data, updated_at = now()
                """,
                (key, psycopg2.extras.Json(matches)),
            )
            conn.commit()
            return updated

    with _LOCK:
        path = _path("matches.json")
        with open(path, "r", encoding="utf-8") as source:
            matches = json.load(source)
        updated = _apply_match_update(matches, match_id, expected_version, updater)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as destination:
            json.dump(matches, destination, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        return updated


def load_config():
    return load_json("config.json")


def save_config(config):
    if USE_NORMALIZED_DB:
        raise RuntimeError("Whole-document config writes are disabled for normalized storage.")
    save_json("config.json", config)


def is_normalized_backend():
    return USE_NORMALIZED_DB


SPORT_CODE_ABBR = {"padel": "PDL", "badminton": "BM", "table-tennis": "TM"}


def list_sites():
    if USE_NORMALIZED_DB:
        raise RuntimeError("Site list is not available for normalized storage yet.")
    config = load_config()
    return config.get("sites", [])


def site_name(config, site_code):
    """Nama tampilan site (dipakai sebagai nama tim publik) dari kode site, atau None."""
    if not site_code:
        return None
    for site in config.get("sites", []):
        if site.get("code") == site_code:
            return site.get("name")
    return None


def generate_team_code(site_code, category_key, config):
    """Kode entrant otomatis: {SITE}-{SPORT_ABBR}{SLOT}, mis. BBL-PDL1, BBL-PDLCAD.
    SLOT = nomor urut kategori 'pair' untuk sport itu (1, 2, ...), atau 'CAD' untuk
    kategori roster/cadangan. Global unik karena site x sport x slot tidak pernah bentrok,
    sehingga admin tidak perlu mengetik kode manual."""
    site_code = (site_code or "").strip().upper()
    category = next((c for c in config.get("categories", []) if c.get("key") == category_key), None)
    if not category:
        raise ValueError(f"Kategori '{category_key}' tidak ditemukan dalam konfigurasi.")
    sport_key = category.get("sport_key", "table-tennis")
    abbr = SPORT_CODE_ABBR.get(sport_key, sport_key[:3].upper())
    if category.get("entrant_type") == "roster":
        return f"{site_code}-{abbr}CAD"
    pair_keys = [
        c["key"] for c in config.get("categories", [])
        if c.get("sport_key") == sport_key and c.get("entrant_type", "pair") == "pair"
    ]
    slot = pair_keys.index(category_key) + 1 if category_key in pair_keys else 1
    return f"{site_code}-{abbr}{slot}"


def auto_split_groups(category_key):
    """Acak & bagi rata semua tim (tipe 'pair') di suatu kategori ke grup yang
    sudah dikonfigurasi (config.categories[].groups), berapa pun jumlah grupnya.
    Entrant tipe roster/cadangan tidak punya grup dan dilewati."""
    config = load_config()
    category = next((c for c in config.get("categories", []) if c.get("key") == category_key), None)
    if not category:
        raise ValueError(f"Kategori '{category_key}' tidak ditemukan dalam konfigurasi.")
    if category.get("entrant_type") == "roster":
        raise ValueError("Kategori roster/cadangan tidak memiliki grup untuk dibagi.")
    groups = category.get("groups") or ["A"]

    teams = load_teams()
    codes = [
        code for code, t in teams.items()
        if t.get("category") == category_key and t.get("entrant_type") != "roster"
    ]
    if len(codes) < 2:
        raise ValueError("Minimal 2 tim terdaftar di kategori ini untuk membagi grup.")

    import random as _random
    _random.shuffle(codes)
    n_groups = len(groups)
    assignment = {g: [] for g in groups}
    for index, code in enumerate(codes):
        group = groups[index % n_groups]
        teams[code]["group"] = group
        assignment[group].append(code)
    save_teams(teams)
    return assignment


def list_sports():
    if USE_NORMALIZED_DB:
        return _NORMALIZED_REPOSITORY.list_sports()
    config = load_config()
    categories = config.get("categories", [])
    enabled_sports = config.get("enabled_sports", ["table-tennis"])
    counts = {"table-tennis": 0, "padel": 0, "badminton": 0}
    for cat in categories:
        s_key = cat.get("sport_key", "table-tennis")
        counts[s_key] = counts.get(s_key, 0) + 1

    return [
        {
            "key": "padel",
            "name": "Padel",
            "icon": "🎾",
            "enabled": "padel" in enabled_sports or counts.get("padel", 0) > 0,
            "display_order": 1,
            "division_count": counts.get("padel", 0),
        },
        {
            "key": "badminton",
            "name": "Badminton",
            "icon": "🏸",
            "enabled": "badminton" in enabled_sports or counts.get("badminton", 0) > 0,
            "display_order": 2,
            "division_count": counts.get("badminton", 0),
        },
        {
            "key": "table-tennis",
            "name": "Table Tennis",
            "icon": "🏓",
            "enabled": "table-tennis" in enabled_sports or counts.get("table-tennis", 0) > 0,
            "display_order": 3,
            "division_count": counts.get("table-tennis", 0),
        },
    ]


DEFAULT_STANDING_POLICY = {
    "win_points": 2,
    "played_loss_points": 1,
    "walkover_loss_points": 0,
    "tie_break_order": [
        "competition_points",
        "head_to_head",
        "mini_table",
        "segment_difference",
        "point_difference",
    ],
}


def load_competition_structure():
    if USE_NORMALIZED_DB:
        return _NORMALIZED_REPOSITORY.load_competition_structure()

    config = load_config()
    divisions = []
    for order, category in enumerate(config.get("categories", []), start=1):
        knockout_format = category.get("knockout_format", "final_only" if category.get("has_final", True) else "no_knockout")
        has_final = category.get("has_final", True) and knockout_format != "no_knockout"
        stages = [
            {
                "id": None,
                "key": "group-stage",
                "type": "group",
                "name": "Babak Grup",
                "sequence": 1,
                "qualification_policy": (
                    {"qualifiers_per_group": 2 if knockout_format == "semi_and_final" else 1, "destination_stage": "semifinal" if knockout_format == "semi_and_final" else "final"}
                    if has_final
                    else {"champion_from_standings": True}
                ),
                "groups": [
                    {"key": key, "name": f"Group {key}", "display_order": index}
                    for index, key in enumerate(category.get("groups", []), start=1)
                ],
            }
        ]
        if has_final:
            if knockout_format == "semi_and_final":
                stages.append(
                    {
                        "id": None,
                        "key": "semifinal",
                        "type": "semifinal",
                        "name": "Babak Semifinal",
                        "sequence": 2,
                        "qualification_policy": {
                            "source": "group-stage",
                            "entrants": "top-2-groups",
                        },
                        "groups": [],
                    }
                )
            stages.append(
                {
                    "id": None,
                    "key": "final",
                    "type": "final",
                    "name": "Final",
                    "sequence": 3 if knockout_format == "semi_and_final" else 2,
                    "qualification_policy": {
                        "source": "semifinal" if knockout_format == "semi_and_final" else "group-stage",
                        "entrants": "semifinal-winners" if knockout_format == "semi_and_final" else "group-winners",
                    },
                    "groups": [],
                }
            )
        divisions.append(
            {
                "id": None,
                "key": category["key"],
                "name": category.get("label", category["key"]),
                "sport_key": category.get("sport_key", "table-tennis"),
                "sport_name": {
                    "table-tennis": "Table Tennis",
                    "padel": "Padel",
                    "badminton": "Badminton",
                }.get(category.get("sport_key", "table-tennis"), "Sport"),
                "sport_icon": {
                    "table-tennis": "🏓",
                    "padel": "🎾",
                    "badminton": "🏸",
                }.get(category.get("sport_key", "table-tennis"), "🏆"),
                "sport_enabled": True,
                "feature_flags": {
                    "schedule": True, "standings": True, "comments": True,
                    "reactions": True, "media": True, "streaming": True,
                },
                "entrant_type": "team",
                "min_team_size": 2,
                "max_team_size": 2,
                "enabled": True,
                "display_order": order,
                "standing_policy": {
                    "key": "legacy-table-tennis",
                    "version": 1,
                    "name": "InterSport Table Tennis Group Policy",
                    "config": dict(DEFAULT_STANDING_POLICY),
                },
                "default_rule_profile": {
                    "table-tennis": {
                        "key": "table-tennis-bo3", "version": 1, "name": "Table Tennis Best of 3", "segment_term": "game", "config": {"best_of": 3, "points_to_win": 11, "win_by": 2},
                    },
                    "padel": {
                        "key": "padel-standard-advantage", "version": 1, "name": "Padel Best of 3 — Advantage", "segment_term": "set", "config": {"best_of": 3, "games_to_win_set": 6, "tie_break_at": "6-6", "game_scoring_method": "advantage", "deciding_set_policy": "standard"},
                    },
                    "badminton": {
                        "key": "badminton-21-bo3", "version": 1, "name": "Badminton 21-point Best of 3", "segment_term": "game", "config": {"best_of": 3, "points_to_win": 21, "win_by": 2, "point_cap": 30},
                    },
                }.get(category.get("sport_key", "table-tennis"), {
                    "key": "default-bo3", "version": 1, "name": "Default Best of 3", "segment_term": "game", "config": {"best_of": 3, "points_to_win": 11, "win_by": 2},
                }),
                "stages": stages,
            }
        )
    return {
        "tournament": {
            "slug": config.get("tournament_short_name", "tournament"),
            "name": config.get("tournament_name", "Tournament"),
            "timezone": config.get("timezone", "Asia/Jakarta"),
        },
        "divisions": divisions,
        "rule_profiles_by_sport": {
            "table-tennis": [
                {
                    "key": "table-tennis-bo3",
                    "version": 1,
                    "name": "Table Tennis Best of 3",
                    "segment_term": "game",
                    "config": {"best_of": 3, "points_to_win": 11, "win_by": 2},
                },
                {
                    "key": "table-tennis-bo5",
                    "version": 1,
                    "name": "Table Tennis Best of 5",
                    "segment_term": "game",
                    "config": {"best_of": 5, "points_to_win": 11, "win_by": 2},
                },
            ],
            "badminton": [
                {
                    "key": "badminton-21-bo3",
                    "version": 1,
                    "name": "Badminton 21-point Best of 3",
                    "segment_term": "game",
                    "config": {
                        "best_of": 3, "points_to_win": 21,
                        "win_by": 2, "point_cap": 30,
                    },
                }
            ],
            "padel": [
                {
                    "key": "padel-standard-advantage",
                    "version": 1,
                    "name": "Padel Best of 3 — Advantage",
                    "segment_term": "set",
                    "config": {
                        "best_of": 3, "games_to_win_set": 6,
                        "tie_break_at": "6-6",
                        "game_scoring_method": "advantage",
                        "deciding_set_policy": "standard",
                    },
                },
                {
                    "key": "padel-standard-golden-point",
                    "version": 1,
                    "name": "Padel Best of 3 — Golden Point",
                    "segment_term": "set",
                    "config": {
                        "best_of": 3, "games_to_win_set": 6,
                        "tie_break_at": "6-6",
                        "game_scoring_method": "golden_point",
                        "deciding_set_policy": "standard",
                    },
                },
            ],
        },
    }


def update_announcement(title, body):
    if USE_NORMALIZED_DB:
        _NORMALIZED_REPOSITORY.update_announcement(title, body)
        return
    config = load_config()
    config["announcement_title"] = title
    config["announcement_text"] = body
    save_json("config.json", config)


# ─────────────────────────────────────────────────────────────────────
#  SPORT RULES — per-sport scoring config, editable by admin
# ─────────────────────────────────────────────────────────────────────

DEFAULT_SPORT_RULES = {
    "table-tennis": {
        "profile_key": "table-tennis-bo3",
        "profile_name": "Tenis Meja — Best of 3 Games",
        "segment_term": "game",       # "game" | "set"
        "best_of": 3,                 # 3 or 5 or 7
        "points_to_win": 11,          # 11 (standard) or 21 (old style)
        "win_by": 2,                  # deuce margin
        "point_cap": 0,               # 0 = no cap; 21 = cap (for badminton)
        "games_to_win_set": 0,        # 0 = N/A (only used for padel sets)
        "tie_break_at": "",           # "" = N/A; "6-6" for padel
        "game_scoring_method": "",    # "" = N/A; "advantage"|"golden_point" for padel
        "deciding_set_policy": "",    # "" = N/A; "standard"|"super_tiebreak" for padel
        "notes": "Setiap game menang dengan 11 poin, selisih minimal 2. Kemenangan dihitung berdasarkan game yang dimenangkan.",
    },
    "badminton": {
        "profile_key": "badminton-21-bo3",
        "profile_name": "Badminton — Best of 3 Games",
        "segment_term": "game",
        "best_of": 3,
        "points_to_win": 21,
        "win_by": 2,
        "point_cap": 30,              # deuce cap: 30-29 wins
        "games_to_win_set": 0,
        "tie_break_at": "",
        "game_scoring_method": "",
        "deciding_set_policy": "",
        "notes": "Setiap game menang dengan 21 poin, deuce di 20-20, maksimal 30. Best of 3 games.",
    },
    "padel": {
        "profile_key": "padel-standard-advantage",
        "profile_name": "Padel — Best of 3 Sets (Advantage)",
        "segment_term": "set",
        "best_of": 3,
        "points_to_win": 0,           # 0 = N/A (padel uses games_to_win_set)
        "win_by": 0,
        "point_cap": 0,
        "games_to_win_set": 6,        # menang set jika capai 6 games
        "tie_break_at": "6-6",        # tiebreak when score is 6-6
        "game_scoring_method": "advantage",   # "advantage" | "golden_point"
        "deciding_set_policy": "standard",    # "standard" | "super_tiebreak"
        "notes": "Pertandingan dengan sistem game tradisional. Set dimenangkan saat capai 6 games, tiebreak di 6-6. Best of 3 sets.",
    },
}


def get_sport_rules():
    """Return per-sport scoring rules from config, falling back to defaults."""
    config = load_config()
    saved = config.get("sport_rules", {})
    result = {}
    for sport_key, defaults in DEFAULT_SPORT_RULES.items():
        merged = dict(defaults)
        merged.update(saved.get(sport_key, {}))
        result[sport_key] = merged
    return result


def save_sport_rules(rules_by_sport: dict):
    """Persist per-sport scoring rules into config.json."""
    config = load_config()
    existing = config.get("sport_rules", {})
    for sport_key, rules in rules_by_sport.items():
        existing[sport_key] = dict(DEFAULT_SPORT_RULES.get(sport_key, {}))
        existing[sport_key].update(rules)
    config["sport_rules"] = existing
    save_json("config.json", config)



def set_champion_photo(champion_key, photo_url=None, uploaded_at=None):
    if USE_NORMALIZED_DB:
        _NORMALIZED_REPOSITORY.set_champion_photo(
            champion_key, photo_url=photo_url, uploaded_at=uploaded_at
        )
        return
    config = load_config()
    champions = config.setdefault("champions", {})
    if photo_url:
        champions[champion_key] = {
            "photo_url": photo_url,
            "uploaded_at": uploaded_at,
        }
    else:
        champions.pop(champion_key, None)
    save_json("config.json", config)


def list_gallery_photos():
    """Standalone galeri photos uploaded by admin, not tied to a match."""
    config = load_config()
    return config.get("gallery_photos", [])


def add_gallery_photos(urls):
    config = load_config()
    photos = config.setdefault("gallery_photos", [])
    uploaded_at = now_wib(config.get("timezone")).isoformat(timespec="seconds")
    for url in urls:
        photos.append({"id": uuid.uuid4().hex, "url": url, "uploaded_at": uploaded_at})
    save_config(config)


def delete_gallery_photo(photo_id):
    """Remove one standalone galeri photo by id and return its url, or None if not found."""
    config = load_config()
    photos = config.get("gallery_photos", [])
    target = next((p for p in photos if p.get("id") == photo_id), None)
    if target is None:
        return None
    config["gallery_photos"] = [p for p in photos if p.get("id") != photo_id]
    save_config(config)
    return target.get("url")


LIVE_CHAT_MAX_MESSAGES = 300


def list_live_chat_messages(after_id=None):
    """Recent live-chat messages, standalone (site-wide, not tied to a match).
    `after_id` lets pollers ask for only what's new since the last message
    they already have, instead of re-fetching the whole recent window."""
    config = load_config()
    messages = config.get("live_chat_messages", [])
    if after_id:
        idx = next((i for i, m in enumerate(messages) if m["id"] == after_id), None)
        if idx is not None:
            return messages[idx + 1:]
    return messages[-100:]


def add_live_chat_message(name, message):
    config = load_config()
    messages = config.setdefault("live_chat_messages", [])
    entry = {
        "id": uuid.uuid4().hex,
        "name": name,
        "message": message,
        "at": now_wib(config.get("timezone")).isoformat(timespec="seconds"),
    }
    messages.append(entry)
    if len(messages) > LIVE_CHAT_MAX_MESSAGES:
        del messages[: len(messages) - LIVE_CHAT_MAX_MESSAGES]
    save_config(config)
    return entry


def delete_live_chat_message(message_id):
    config = load_config()
    messages = config.get("live_chat_messages", [])
    if not any(m.get("id") == message_id for m in messages):
        return False
    config["live_chat_messages"] = [m for m in messages if m.get("id") != message_id]
    save_config(config)
    return True


def clean_youtube_embed_url(url):
    if not url or not url.strip():
        return ""
    url = url.strip()
    if "<iframe" in url.lower() and "src=" in url.lower():
        match = re.search(r'src="([^"]+)"', url, re.IGNORECASE) or re.search(r"src='([^']+)'", url, re.IGNORECASE)
        if match:
            url = match.group(1)
    vid_match = re.search(r'(?:youtube\.com/(?:watch\?v=|live/)|youtu\.be/)([\w-]+)', url)
    if vid_match:
        video_id = vid_match.group(1)
        return f"https://www.youtube.com/embed/{video_id}"
    return url


def extract_youtube_video_id(embed_url):
    if not embed_url:
        return ""
    match = re.search(r'youtube\.com/embed/([\w-]+)', embed_url)
    return match.group(1) if match else ""


def update_live_streaming_config(url, title="", live_chat_enabled=None):
    if USE_NORMALIZED_DB and hasattr(_NORMALIZED_REPOSITORY, "update_live_stream"):
        _NORMALIZED_REPOSITORY.update_live_stream(url, title, live_chat_enabled)
        return
    config = load_config()
    config["youtube_embed_url"] = clean_youtube_embed_url(url)
    config["youtube_embed_title"] = title.strip() if title else ""
    if live_chat_enabled is not None:
        config["live_chat_enabled"] = live_chat_enabled
    save_json("config.json", config)


def dynamic_circle_rounds(codes):
    if not codes or len(codes) < 2:
        return []
    team_list = list(codes)
    if len(team_list) % 2 == 1:
        team_list.append(None)
    n = len(team_list)
    rounds = []
    for _ in range(n - 1):
        rnd = []
        for i in range(n // 2):
            t1 = team_list[i]
            t2 = team_list[n - 1 - i]
            if t1 is not None and t2 is not None:
                rnd.append((t1, t2))
        if rnd:
            rounds.append(rnd)
        team_list = [team_list[0]] + [team_list[-1]] + team_list[1:-1]
    return rounds


def _scoring_profile_for(sport_key, stage_type):
    """Return the per-match scoring profile fields (merged into the match dict)
    for a given sport + stage. Padel group stage splits a single 21-point pool
    between the two sides (whoever scores more of the 21 wins -- e.g. 11-10 or
    19-2 both end the game). Padel knockout stage (semifinal/3rd place/final)
    is Best of 5 games on the classic 0/15/30/40 tennis point ladder with
    Golden Point at deuce (no advantage -- first to reach the target with any
    lead wins the game outright); teams may optionally keep playing out all 5
    games even after the match is already decided. Badminton is 21 points/best
    of 3 with a 30-point cap at every stage, except the rubber (3rd) game,
    which is shortened to a sudden-victory race to 11 -- first to 11 wins
    outright, no deuce. Table tennis keeps the existing legacy default (no
    override)."""
    if sport_key == "badminton":
        return {
            "_profile_key": "badminton-21-bo3",
            "_profile_version": 1,
            "_profile_config": {
                "best_of": 3, "points_to_win": 21, "win_by": 2, "point_cap": 30,
                "decider_points_to_win": 11, "decider_win_by": 1, "decider_point_cap": 11,
            },
            "_segment_term": "game",
        }
    if sport_key == "padel":
        if stage_type == "group":
            return {
                "_profile_config": {"best_of": 1, "points_to_win": 21},
                "_segment_term": "game",
            }
        return {
            "_profile_config": {
                "best_of": 5, "points_to_win": 40, "win_by": 1,
                "game_scoring_method": "golden_point", "allow_continuation": True,
            },
            "_segment_term": "game",
        }
    return {}


def _qual_slot_pair(groups, two_group_pair, one_group_pair):
    """Label slot kualifikasi knockout untuk sepasang (a, b). Auto-seed hanya
    didukung untuk tepat 1 atau 2 grup; 3+ grup harus diisi manual oleh admin
    (lihat auto_seed_knockout) karena tidak ada aturan cross-group seeding
    yang general untuk N grup sembarang."""
    if len(groups) == 2:
        return two_group_pair
    if len(groups) == 1:
        return one_group_pair
    return ("Diisi manual oleh admin", "Diisi manual oleh admin")


def generate_group_to_knockout_schedule(category_key, start_date=None, time_slots=None, court="Meja 1", knockout_format="final_only"):
    teams = load_teams()
    config = load_config()
    matches = load_matches()
    
    category = next((c for c in config.get("categories", []) if c.get("key") == category_key), None)
    if not category:
        raise ValueError(f"Divisi/Kategori '{category_key}' tidak ditemukan dalam konfigurasi.")
    
    category["knockout_format"] = knockout_format
    category["has_final"] = (knockout_format != "no_knockout")
    save_config(config)

    sport_key = category.get("sport_key", "table-tennis")
    cat_label = category.get("label", category_key)
    groups = category.get("groups", ["A"])
    has_final = category.get("has_final", True)
    
    if not start_date:
        start_date = config.get("start_date", "2026-07-20")
    if not time_slots:
        time_slots = ["18:00", "18:30", "19:00", "19:30"]
        
    cat_teams = {code: t for code, t in teams.items() if t.get("category") == category_key}
    if len(cat_teams) < 2:
        raise ValueError(f"Divisi '{cat_label}' minimal membutuhkan 2 tim terdaftar untuk menguji putaran grup.")

    matches = [m for m in matches if m.get("category") != category_key]
    
    existing_ids = {m.get("id") for m in matches}
    mid_counter = 1
    def get_next_id():
        nonlocal mid_counter
        while f"M{mid_counter:02d}" in existing_ids:
            mid_counter += 1
        new_id = f"M{mid_counter:02d}"
        existing_ids.add(new_id)
        return new_id

    round_label_map = {1: "Babak 1", 2: "Babak 2", 3: "Babak 3", 4: "Babak 4", 5: "Babak 5"}
    
    group_matches_queue = []
    for g in groups:
        g_codes = [code for code, t in cat_teams.items() if t.get("group") == g or (len(groups) == 1 and not t.get("group"))]
        rounds = dynamic_circle_rounds(g_codes)
        for r_idx, rnd in enumerate(rounds, start=1):
            for a, b in rnd:
                group_matches_queue.append((g, r_idx, a, b))
                
    curr_date = datetime.strptime(start_date, "%Y-%m-%d")
    slot_idx = 0
    
    group_profile = _scoring_profile_for(sport_key, "group")
    for g, round_no, a, b in group_matches_queue:
        time_str = time_slots[slot_idx % len(time_slots)]
        matches.append({
            "id": get_next_id(),
            "category": category_key,
            "category_label": cat_label,
            "sport_key": sport_key,
            "group": g,
            "round": round_no,
            "round_label": round_label_map.get(round_no, f"Babak {round_no}"),
            "stage_type": "group",
            "team_a": a,
            "team_b": b,
            "date": curr_date.strftime("%Y-%m-%d"),
            "time": time_str,
            "court": court,
            "status": "scheduled",
            "sets": [],
            "winner": None,
            "walkover": False,
            "notes": "",
            "reschedule_history": [],
            **group_profile,
        })
        slot_idx += 1
        if slot_idx % len(time_slots) == 0:
            curr_date += timedelta(days=1)
            
    knockout_count = 0
    if knockout_format != "no_knockout":
        final_date_str = config.get("final_date", curr_date.strftime("%Y-%m-%d"))
        semifinal_profile = _scoring_profile_for(sport_key, "semifinal")
        final_profile = _scoring_profile_for(sport_key, "final")
        if knockout_format == "semi_and_final":
            sf1_a, sf1_b = _qual_slot_pair(
                groups, ("Juara Group A", "Runner-up Group B"), ("Peringkat 1 Group", "Peringkat 4 Group")
            )
            sf2_a, sf2_b = _qual_slot_pair(
                groups, ("Juara Group B", "Runner-up Group A"), ("Peringkat 2 Group", "Peringkat 3 Group")
            )
            sf1_id = get_next_id()
            matches.append({
                "id": sf1_id,
                "category": category_key,
                "category_label": cat_label,
                "sport_key": sport_key,
                "group": "KNOCKOUT",
                "round": 4,
                "round_label": "Semifinal 1",
                "stage_type": "semifinal",
                "stage_key": "semifinal",
                "team_a": None,
                "team_b": None,
                "qualification_slot_a": sf1_a,
                "qualification_slot_b": sf1_b,
                "date": final_date_str,
                "time": "17:00",
                "court": court,
                "status": "scheduled",
                "sets": [],
                "winner": None,
                "walkover": False,
                "notes": f"Semifinal 1 {cat_label}: {sf1_a} vs {sf1_b}",
                "reschedule_history": [],
                **semifinal_profile,
            })
            sf2_id = get_next_id()
            matches.append({
                "id": sf2_id,
                "category": category_key,
                "category_label": cat_label,
                "sport_key": sport_key,
                "group": "KNOCKOUT",
                "round": 4,
                "round_label": "Semifinal 2",
                "stage_type": "semifinal",
                "stage_key": "semifinal",
                "team_a": None,
                "team_b": None,
                "qualification_slot_a": sf2_a,
                "qualification_slot_b": sf2_b,
                "date": final_date_str,
                "time": "17:30",
                "court": court,
                "status": "scheduled",
                "sets": [],
                "winner": None,
                "walkover": False,
                "notes": f"Semifinal 2 {cat_label}: {sf2_a} vs {sf2_b}",
                "reschedule_history": [],
                **semifinal_profile,
            })
            third_place_id = get_next_id()
            matches.append({
                "id": third_place_id,
                "category": category_key,
                "category_label": cat_label,
                "sport_key": sport_key,
                "group": "KNOCKOUT",
                "round": 4,
                "round_label": "Perebutan Juara 3",
                "stage_type": "third_place",
                "stage_key": "third_place",
                "team_a": None,
                "team_b": None,
                "qualification_slot_a": "Kalah Semifinal 1",
                "qualification_slot_b": "Kalah Semifinal 2",
                "depends_on": [sf1_id, sf2_id],
                "date": final_date_str,
                "time": "18:00",
                "court": court,
                "status": "scheduled",
                "sets": [],
                "winner": None,
                "walkover": False,
                "notes": f"Perebutan Juara 3 {cat_label}: Kalah Semifinal 1 vs Kalah Semifinal 2",
                "reschedule_history": [],
                **semifinal_profile,
            })
            matches.append({
                "id": get_next_id(),
                "category": category_key,
                "category_label": cat_label,
                "sport_key": sport_key,
                "group": "FINAL",
                "round": 5,
                "round_label": "Final",
                "stage_type": "final",
                "stage_key": "final",
                "team_a": None,
                "team_b": None,
                "qualification_slot_a": "Pemenang Semifinal 1",
                "qualification_slot_b": "Pemenang Semifinal 2",
                "depends_on": [sf1_id, sf2_id],
                "date": final_date_str,
                "time": "18:30",
                "court": court,
                "status": "scheduled",
                "sets": [],
                "winner": None,
                "walkover": False,
                "notes": f"Grand Final {cat_label}: Pemenang Semifinal 1 vs Pemenang Semifinal 2",
                "reschedule_history": [],
                **final_profile,
            })
            knockout_count += 4
        else:
            final_a, final_b = _qual_slot_pair(
                groups, ("Juara Group A", "Juara Group B"), ("Peringkat 1 Group", "Peringkat 2 Group")
            )
            matches.append({
                "id": get_next_id(),
                "category": category_key,
                "category_label": cat_label,
                "sport_key": sport_key,
                "group": "FINAL",
                "round": 4,
                "round_label": "Final",
                "stage_type": "final",
                "stage_key": "final",
                "team_a": None,
                "team_b": None,
                "qualification_slot_a": final_a,
                "qualification_slot_b": final_b,
                "date": final_date_str,
                "time": "18:00",
                "court": court,
                "status": "scheduled",
                "sets": [],
                "winner": None,
                "walkover": False,
                "notes": f"Final {cat_label}: {final_a} vs {final_b}",
                "reschedule_history": [],
                **final_profile,
            })
            knockout_count += 1
            
    save_matches(matches)
    try:
        auto_seed_knockout(category_key, matches=matches, teams=teams, config=config, force=True)
    except Exception:
        pass
    return len(group_matches_queue), knockout_count


def auto_seed_knockout(category_key, matches=None, teams=None, config=None, force=False):
    if matches is None:
        matches = load_matches()
    if teams is None:
        teams = load_teams()
    if config is None:
        config = load_config()

    category = next((c for c in config.get("categories", []) if c.get("key") == category_key), None)
    if not category:
        return False

    cat_matches = [m for m in matches if m.get("category") == category_key]
    group_matches = [m for m in cat_matches if m.get("stage_type") in ("group", "round_robin") and m.get("group") not in ("FINAL", "KNOCKOUT", "SEMIFINAL")]

    # Semifinal slots are seeded from group-stage standings, which are meaningless
    # until every group match has a real result -- an all-0 table still produces
    # *some* sort order, so without this gate the semifinal gets locked in to
    # whichever teams land first/third in that arbitrary tie-break the moment the
    # schedule is generated, long before anyone has actually played. `force`
    # intentionally does NOT bypass this: it only means "run even if nothing
    # calls this after a score update", not "seed off unfinished standings".
    group_stage_complete = bool(group_matches) and all(
        m.get("status") in ("completed", "cancelled") or is_valid_completed_match(m) or m.get("walkover")
        for m in group_matches
    )

    groups = category.get("groups", ["A"])
    standings_by_group = {}
    policy_config = (category.get("standing_policy") or {}).get("config") or DEFAULT_STANDING_POLICY
    for g in groups:
        rows = compute_standings(cat_matches, teams, category_key, g, policy_config=policy_config)
        standings_by_group[g] = rows

    changed = False
    for m in cat_matches:
        if m.get("stage_type") in ("semifinal", "semi_final", "knockout") or m.get("round_label") in ("Semifinal 1", "Semifinal 2"):
            if not group_stage_complete:
                continue
            if len(groups) == 2 and "A" in standings_by_group and "B" in standings_by_group:
                rows_a = standings_by_group.get("A", [])
                rows_b = standings_by_group.get("B", [])
                if m.get("round_label") == "Semifinal 1":
                    if len(rows_a) >= 1 and not m.get("team_a"):
                        m["team_a"] = rows_a[0]["code"]
                        changed = True
                    if len(rows_b) >= 2 and not m.get("team_b"):
                        m["team_b"] = rows_b[1]["code"]
                        changed = True
                elif m.get("round_label") == "Semifinal 2":
                    if len(rows_b) >= 1 and not m.get("team_a"):
                        m["team_a"] = rows_b[0]["code"]
                        changed = True
                    if len(rows_a) >= 2 and not m.get("team_b"):
                        m["team_b"] = rows_a[1]["code"]
                        changed = True
            elif len(groups) == 1 and "A" in standings_by_group:
                rows = standings_by_group.get("A", [])
                if m.get("round_label") == "Semifinal 1" and len(rows) >= 4:
                    if not m.get("team_a"): m["team_a"] = rows[0]["code"]; changed = True
                    if not m.get("team_b"): m["team_b"] = rows[3]["code"]; changed = True
                elif m.get("round_label") == "Semifinal 2" and len(rows) >= 4:
                    if not m.get("team_a"): m["team_a"] = rows[1]["code"]; changed = True
                    if not m.get("team_b"): m["team_b"] = rows[2]["code"]; changed = True

        elif m.get("stage_type") == "third_place":
            depends = m.get("depends_on", [])
            if len(depends) >= 2:
                sf_matches = {sf.get("id"): sf for sf in cat_matches if sf.get("id") in depends}
                sf1 = sf_matches.get(depends[0])
                sf2 = sf_matches.get(depends[1])
                for sf, slot in ((sf1, "team_a"), (sf2, "team_b")):
                    if not sf or not sf.get("winner"):
                        continue
                    if not sf.get("team_a") or not sf.get("team_b"):
                        continue
                    loser = sf["team_a"] if sf["winner"] == sf["team_b"] else sf["team_b"]
                    if m.get(slot) != loser:
                        m[slot] = loser
                        changed = True

        elif m.get("stage_type") == "final" or m.get("group") == "FINAL":
            depends = m.get("depends_on", [])
            if depends:
                sf_matches = {sf.get("id"): sf for sf in cat_matches if sf.get("id") in depends}
                if len(depends) >= 2:
                    sf1 = sf_matches.get(depends[0])
                    sf2 = sf_matches.get(depends[1])
                    if sf1 and sf1.get("winner") and m.get("team_a") != sf1.get("winner"):
                        m["team_a"] = sf1["winner"]
                        changed = True
                    if sf2 and sf2.get("winner") and m.get("team_b") != sf2.get("winner"):
                        m["team_b"] = sf2["winner"]
                        changed = True
            else:
                if len(groups) == 2 and "A" in standings_by_group and "B" in standings_by_group:
                    rows_a = standings_by_group.get("A", [])
                    rows_b = standings_by_group.get("B", [])
                    if len(rows_a) >= 1 and not m.get("team_a"):
                        m["team_a"] = rows_a[0]["code"]
                        changed = True
                    if len(rows_b) >= 1 and not m.get("team_b"):
                        m["team_b"] = rows_b[0]["code"]
                        changed = True

    if changed:
        save_matches(matches)
    return changed


def list_api_matches(
    *, sport=None, division=None, status=None, match_date=None, limit=25,
    cursor_value=None,
):
    if USE_NORMALIZED_DB:
        return _NORMALIZED_REPOSITORY.list_api_matches(
            sport=sport, division=division, status=status,
            match_date=match_date, limit=limit, cursor_value=cursor_value,
        )

    matches = load_matches()
    for match in matches:
        match.setdefault("sport_key", "table-tennis")
    if sport:
        matches = [m for m in matches if m["sport_key"] == sport]
    if division:
        matches = [m for m in matches if m.get("category") == division]
    if status:
        matches = [m for m in matches if m.get("status") == status]
    if match_date:
        matches = [m for m in matches if m.get("date") == match_date]
    matches.sort(key=lambda m: (m.get("date") or "9999-12-31", m.get("time") or "", m["id"]))
    offset = 0
    if cursor_value:
        try:
            padded = cursor_value + "=" * (-len(cursor_value) % 4)
            offset = int(base64.urlsafe_b64decode(padded.encode()).decode())
            if offset < 0:
                raise ValueError("Cursor offset cannot be negative.")
        except Exception as exc:
            raise ValueError("Invalid pagination cursor.") from exc
    page = matches[offset:offset + limit]
    next_cursor = None
    if offset + limit < len(matches):
        next_cursor = base64.urlsafe_b64encode(
            str(offset + limit).encode()
        ).decode().rstrip("=")
    return page, next_cursor


def get_api_match(match_id):
    if USE_NORMALIZED_DB:
        return _NORMALIZED_REPOSITORY.get_api_match(match_id)
    return get_match(load_matches(), match_id)


def backup_data_files(*names):
    """Cadangkan data sebelum operasi merusak (mis. reset/acak ulang).
    Di DB: disalin ke tennis.app_data_backups. Di lokal: disalin ke data/backups/."""
    ts = now_wib().strftime("%Y%m%d_%H%M%S")
    if USE_NORMALIZED_DB:
        raise RuntimeError(
            "Legacy collection backup is unavailable for normalized storage."
        )
    if USE_DB:
        with _db_conn() as conn, conn.cursor() as cur:
            for name in names:
                key = name.replace(".json", "")
                cur.execute("SELECT data FROM tennis.app_data WHERE name = %s", (key,))
                row = cur.fetchone()
                if row is not None:
                    cur.execute(
                        "INSERT INTO tennis.app_data_backups (name, data) VALUES (%s, %s)",
                        (key, psycopg2.extras.Json(row[0])),
                    )
            conn.commit()
        return
    with _LOCK:
        backup_dir = os.path.join(DATA_DIR, "backups")
        os.makedirs(backup_dir, exist_ok=True)
        for name in names:
            src = _path(name)
            if os.path.exists(src):
                stem, ext = os.path.splitext(name)
                shutil.copy(src, os.path.join(backup_dir, f"{stem}_{ts}{ext}"))


def get_match(matches, match_id):
    for m in matches:
        if m["id"] == match_id:
            return m
    return None


def match_sort_key(m):
    """Sort key for schedule listings: chronological by date/time/court, but
    matches with no confirmed time yet (semifinal/final still awaiting group-
    stage results) always sink to the bottom of their date instead of sorting
    first just because "" < any real time string."""
    return (m["date"], 0 if m.get("time") else 1, m.get("time") or "", m.get("court") or "")


def team_label(teams, code):
    if not code:
        return "TBD"
    t = teams.get(code)
    if not t:
        return code
    name = site_name(load_config(), t.get("site_code"))
    if name:
        return name
    return f'{t["player1"]} / {t["player2"]}'


def team_short(teams, code):
    if not code:
        return "TBD"
    t = teams.get(code)
    if not t:
        return code
    return t.get("site_code") or t.get("code") or code


def truncate_words(text, max_words=2):
    words = (text or "").split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "…"


def format_date_id(date_str):
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{DAY_NAMES[d.weekday()]}, {d.day} {MONTH_NAMES[d.month]} {d.year}"


def format_date_range_id(start_date, end_date):
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    if start.date() == end.date():
        return f"{start.day} {MONTH_NAMES[start.month]} {start.year}"
    if start.year == end.year and start.month == end.month:
        return f"{start.day}–{end.day} {MONTH_NAMES[start.month]} {start.year}"
    if start.year == end.year:
        return f"{start.day} {MONTH_NAMES[start.month]} – {end.day} {MONTH_NAMES[end.month]} {start.year}"
    return f"{start.day} {MONTH_NAMES[start.month]} {start.year} – {end.day} {MONTH_NAMES[end.month]} {end.year}"


def _team_names(player1, player2):
    return f"{player1}/{player2}" if player2 else player1


def build_share_text(m):
    """Teks multi-baris untuk tombol Bagikan (navigator.share) -- dipisah per
    baris (bukan satu kalimat panjang seperti og:description) supaya enak
    dibaca begitu masuk ke WhatsApp/Teams sebagai pesan teks biasa."""
    lines = [
        f"*{m['team_a_code']} vs {m['team_b_code']} — {m['category_label']}*",
        (
            f"{m.get('group')} · "
            if m.get("stage_type") in {"group", "round_robin"} and m.get("group")
            else ""
        ) + m["round_label"],
        "",
        _team_names(m["team_a_player1"], m["team_a_player2"]),
        "vs",
        _team_names(m["team_b_player1"], m["team_b_player2"]),
        "",
        f"📅 {m['date_label']}",
        f"⏰ {m['time']} WIB",
        f"📍 {m['court']}",
    ]
    if m["status"] in ("completed", "live"):
        lines.append(f"🏓 Skor: {m['sets_a']} - {m['sets_b']}")
    return "\n".join(lines)


def format_datetime_id(value):
    """value: datetime object atau string ISO (mis. dari datetime.isoformat())."""
    d = datetime.fromisoformat(value) if isinstance(value, str) else value
    return f"{d.day} {MONTH_NAMES[d.month]} {d.year}, {d.strftime('%H:%M')}"


def compute_sets_won(sets):
    """sets: list of [score_a, score_b]. Returns (sets_a, sets_b)."""
    a = sum(1 for s in sets if s[0] > s[1])
    b = sum(1 for s in sets if s[1] > s[0])
    return a, b


def sets_needed_to_win(match):
    """Return the number of segments needed to win under the match profile."""
    profile_config = match.get("_profile_config") or {}
    if profile_config.get("best_of"):
        return int(profile_config["best_of"]) // 2 + 1
    # Legacy rule: men's doubles final is Best of 5; group matches are Best of 3.
    return 3 if match.get("group") == "FINAL" else 2


def validate_match_segments(match, segments=None):
    candidate_segments = match.get("sets") or [] if segments is None else segments
    if match.get("_profile_key"):
        return validate_score(
            RuleProfile(
                sport_key=match.get("sport_key", "table-tennis"),
                profile_key=match["_profile_key"],
                version=int(match.get("_profile_version", 1)),
                config=match.get("_profile_config") or {},
            ),
            candidate_segments,
        )
    profile_config = match.get("_profile_config") or {}
    if match.get("sport_key") == "padel" and match.get("stage_type") == "group":
        # Babak grup Padel: satu game race di mana total skor kedua tim harus
        # pas mencapai target (mis. 11-10 atau 19-2 sama-sama menyelesaikan
        # game) -- bukan format "race-to-N, menang selisih M" seperti Badminton.
        return validate_point_split_score(
            candidate_segments,
            total_points=int(profile_config.get("points_to_win", 21)),
        )
    best_of = sets_needed_to_win(match) * 2 - 1
    return validate_match_score(
        candidate_segments,
        best_of=best_of,
        points_to_win=int(profile_config.get("points_to_win", 11)),
        win_by=int(profile_config.get("win_by", 2)),
        allow_continuation=bool(profile_config.get("allow_continuation")),
    )


def compute_winner(match):
    sets = match.get("sets") or []
    if not sets:
        return None
    result = validate_match_segments(match)
    if result.is_complete:
        return match["team_a"] if result.winner_side == "a" else match["team_b"]
    return None


def validate_recorded_result(match):
    """Return scoring validation plus record-level consistency errors."""
    if match.get("walkover"):
        errors = []
        if match.get("winner") not in (match.get("team_a"), match.get("team_b")):
            errors.append("Pemenang WO tidak sesuai dengan peserta pertandingan.")
        return None, errors

    result = validate_match_segments(match)
    errors = list(result.errors)
    if match.get("status") == "completed":
        if not result.is_complete:
            errors.append("Pertandingan selesai belum memiliki skor akhir yang sah.")
        else:
            expected_winner = (
                match.get("team_a") if result.winner_side == "a" else match.get("team_b")
            )
            if match.get("winner") != expected_winner:
                errors.append("Pemenang tersimpan tidak sesuai dengan skor.")
    return result, errors


def is_valid_completed_match(match):
    if match.get("status") != "completed":
        return False
    _, errors = validate_recorded_result(match)
    return not errors


def sync_winner(match):
    """Recompute winner/status from sets. Call whenever sets are updated."""
    w = compute_winner(match)
    match["winner"] = w
    if w:
        match["status"] = "completed"
    elif match["status"] == "completed":
        match["status"] = "scheduled"
    return match


def _scorekeeper_effective_events(match):
    events = sorted(
        match.get("scorekeeper_events") or [],
        key=lambda event: int(event.get("sequence") or 0),
    )
    reversed_ids = {
        event.get("reversal_of")
        for event in events
        if event.get("event_type") == "score.undo" and event.get("reversal_of")
    }
    return [
        event for event in events
        if event.get("event_type") != "score.undo"
        and event.get("id") not in reversed_ids
    ]


def scorekeeper_terms(match, current_segment=None, segment_index=None):
    """Return sport/profile-aware labels and current-segment scoring limits."""
    current_segment = current_segment or [0, 0]
    sport_key = match.get("sport_key", "table-tennis")
    config = match.get("_profile_config") or {}
    segment_term = match.get("_segment_term") or (
        "set" if sport_key == "padel" else "game"
    )
    segment_label = "Set" if segment_term == "set" else "Game"
    unit_label = "Poin"
    target = int(config.get("points_to_win", 11))
    win_by = int(config.get("win_by", 2))
    cap = config.get("point_cap")
    is_deciding_tiebreak = False

    if sport_key == "badminton":
        is_decider_game = (
            segment_index == int(config.get("best_of", 3))
            and config.get("decider_points_to_win") is not None
        )
        if is_decider_game:
            target = int(config.get("decider_points_to_win"))
            win_by = int(config.get("decider_win_by", 1))
            cap = int(config.get("decider_point_cap", target))
        else:
            target = int(config.get("points_to_win", 21))
            win_by = int(config.get("win_by", 2))
            cap = int(config.get("point_cap", 30))
    elif sport_key == "padel":
        if match.get("stage_type") == "group":
            # Babak grup: satu game split-poin -- total skor kedua tim harus pas
            # mencapai target (bukan race-to-N menang selisih M).
            unit_label = "Poin"
            target = int(config.get("points_to_win", 21))
            win_by = None
            cap = None
        else:
            # Babak knockout: Best of 5 game bertitik tenis (0/15/30/40) dengan
            # Golden Point di deuce -- lebih dulu mencapai target dengan
            # keunggulan berapa pun langsung menang game (win_by=1).
            unit_label = "Poin"
            target = int(config.get("points_to_win", 40))
            win_by = int(config.get("win_by", 1))
            cap = None

    return {
        "segment_term": segment_term,
        "segment_label": segment_label,
        "segment_label_lower": segment_label.lower(),
        "unit_label": unit_label,
        "unit_label_lower": unit_label.lower(),
        "target": target,
        "win_by": win_by,
        "cap": cap,
        "is_deciding_tiebreak": is_deciding_tiebreak,
        "current_segment": list(current_segment),
    }


def scorekeeper_state(match):
    """Build the live scorekeeper projection without affecting public standings."""
    completed_sets = [list(scores) for scores in (match.get("sets") or [])]
    effective = _scorekeeper_effective_events(match)
    current = [0, 0]
    latest_reversible = None
    for event in effective:
        if event.get("event_type") not in {"score.point_awarded", "score.correction_opened"}:
            continue
        metadata = event.get("metadata") or {}
        if metadata.get("sets_after") != completed_sets:
            continue
        after_current = metadata.get("after_current")
        if (
            isinstance(after_current, list) and len(after_current) == 2
            and all(isinstance(value, int) and value >= 0 for value in after_current)
        ):
            current = list(after_current)
            latest_reversible = (
                event if event.get("event_type") == "score.point_awarded" else None
            )

    validation = validate_match_segments(match, completed_sets)
    sets_a, sets_b = compute_sets_won(completed_sets)
    terms = scorekeeper_terms(match, current, segment_index=len(completed_sets) + 1)
    ready_to_finish = (
        match.get("status") == "live"
        and current == [0, 0]
        and validation.is_complete
    )
    return {
        "current": current,
        "completed_segments": completed_sets,
        "segments_won": {"a": sets_a, "b": sets_b},
        "validation_errors": list(validation.errors),
        "match_score_complete": validation.is_complete,
        "winner_side": validation.winner_side,
        "ready_to_finish": ready_to_finish,
        "can_score": match.get("status") == "live" and not validation.is_complete,
        "can_undo": latest_reversible is not None,
        "latest_reversible_event": latest_reversible,
        "next_segment": len(completed_sets) + 1,
        "terms": terms,
        "event_count": len(match.get("scorekeeper_events") or []),
    }


def _append_scorekeeper_event(
    match, event_type, *, side=None, value=None, reversal_of=None, metadata=None
):
    events = match.setdefault("scorekeeper_events", [])
    sequence = max(
        (int(event.get("sequence") or 0) for event in events), default=0
    ) + 1
    event = {
        "id": str(uuid.uuid4()),
        "sequence": sequence,
        "event_type": event_type,
        "side": side,
        "value": value,
        "reversal_of": reversal_of,
        "metadata": metadata or {},
        "at": now_wib(match.get("_timezone")).isoformat(timespec="seconds"),
    }
    events.append(event)
    return event


def apply_scorekeeper_action(match, action, *, side=None, reason=None):
    """Apply one event-sourced scorekeeper action to a locked match record."""
    action = (action or "").strip().lower()
    reason = (reason or "").strip()
    status = match.get("status")

    if action == "start":
        if status not in {"scheduled", "check_in", "postponed"}:
            raise ValueError("Pertandingan ini tidak dapat dimulai dari status saat ini.")
        if not match.get("team_a") or not match.get("team_b"):
            raise ValueError("Dua peserta harus ditentukan sebelum pertandingan dimulai.")
        if not match.get("date") or not match.get("time") or not match.get("court"):
            raise ValueError("Jadwal dan lapangan harus tersedia sebelum pertandingan dimulai.")
        validation = validate_match_segments(match, match.get("sets") or [])
        if validation.errors:
            raise ValueError(
                "Skor tersimpan harus dikoreksi sebelum pertandingan dimulai. "
                + " ".join(validation.errors)
            )
        if validation.is_complete:
            raise ValueError("Skor pertandingan sudah lengkap dan harus diselesaikan atau dikoreksi.")
        match["status"] = "live"
        match["winner"] = None
        match["walkover"] = False
        _append_scorekeeper_event(
            match,
            "score.match_started",
            metadata={"sets_after": [list(item) for item in match.get("sets") or []]},
        )

    elif action == "point":
        if side not in {"a", "b"}:
            raise ValueError("Sisi peserta untuk penambahan skor tidak valid.")
        if status != "live":
            raise ValueError("Mulai pertandingan sebelum menambahkan skor.")
        state = scorekeeper_state(match)
        if state["match_score_complete"]:
            raise ValueError("Skor akhir sudah lengkap. Konfirmasikan selesai atau undo skor terakhir.")
        if state["validation_errors"]:
            raise ValueError("Skor pertandingan perlu dikoreksi sebelum dilanjutkan.")
        before_current = list(state["current"])
        after_current = list(before_current)
        after_current[0 if side == "a" else 1] += 1
        sets_before = [list(item) for item in match.get("sets") or []]
        candidate_sets = sets_before + [after_current]
        validation = validate_match_segments(match, candidate_sets)
        completed_segment = not validation.errors
        if completed_segment:
            match["sets"] = candidate_sets
            next_current = [0, 0]
        else:
            next_current = after_current
        match["winner"] = None
        match["walkover"] = False
        _append_scorekeeper_event(
            match,
            "score.point_awarded",
            side=side,
            value=1,
            metadata={
                "before_current": before_current,
                "after_current": next_current,
                "sets_before": sets_before,
                "sets_after": [list(item) for item in match.get("sets") or []],
                "completed_segment": after_current if completed_segment else None,
            },
        )

    elif action == "undo":
        state = scorekeeper_state(match)
        event = state.get("latest_reversible_event")
        if event is None:
            raise ValueError("Belum ada penambahan skor yang dapat di-undo.")
        if status == "completed" and not reason:
            raise ValueError("Alasan koreksi wajib diisi untuk mengubah hasil selesai.")
        metadata = event.get("metadata") or {}
        sets_before_action = [list(item) for item in match.get("sets") or []]
        if metadata.get("sets_after") != sets_before_action:
            raise ValueError("Riwayat skor tidak lagi sesuai. Muat ulang pertandingan.")
        match["sets"] = [list(item) for item in metadata.get("sets_before") or []]
        if status == "completed":
            match.setdefault("score_corrections", []).append(
                {
                    "before": sets_before_action,
                    "after": [list(item) for item in match["sets"]],
                    "reason": reason,
                    "actor": "scorekeeper",
                    "at": now_wib(match.get("_timezone")).isoformat(timespec="seconds"),
                }
            )
            match["status"] = "live"
        match["winner"] = None
        match["walkover"] = False
        _append_scorekeeper_event(
            match,
            "score.undo",
            reversal_of=event.get("id"),
            metadata={
                "reason": reason,
                "before_current": metadata.get("after_current", [0, 0]),
                "after_current": metadata.get("before_current", [0, 0]),
                "sets_before": sets_before_action,
                "sets_after": [list(item) for item in match["sets"]],
            },
        )

    elif action == "finish":
        if status != "live":
            raise ValueError("Hanya pertandingan Live yang dapat diselesaikan.")
        state = scorekeeper_state(match)
        if state["current"] != [0, 0] or not state["match_score_complete"]:
            raise ValueError("Skor akhir pertandingan belum lengkap.")
        winner_side = state["winner_side"]
        match["winner"] = match.get("team_a") if winner_side == "a" else match.get("team_b")
        match["status"] = "completed"
        match["walkover"] = False
        _append_scorekeeper_event(
            match,
            "score.match_finished",
            side=winner_side,
            metadata={
                "sets_after": [list(item) for item in match.get("sets") or []],
                "after_current": [0, 0],
            },
        )

    elif action == "open_correction":
        if status != "completed" or match.get("walkover"):
            raise ValueError("Hanya hasil skor selesai non-WO yang dapat dibuka untuk koreksi.")
        if not reason:
            raise ValueError("Alasan koreksi wajib diisi.")
        validation = validate_match_segments(match, match.get("sets") or [])
        if not validation.is_complete or not match.get("sets"):
            raise ValueError("Hasil selesai tidak memiliki skor akhir sah yang dapat dikoreksi.")
        sets_before = [list(item) for item in match.get("sets") or []]
        final_segment = list(sets_before[-1])
        winning_index = 0 if final_segment[0] > final_segment[1] else 1
        if final_segment[winning_index] < 1:
            raise ValueError("Segmen terakhir tidak dapat dibuka untuk koreksi.")
        restored_current = list(final_segment)
        restored_current[winning_index] -= 1
        match["sets"] = sets_before[:-1]
        match["status"] = "live"
        match["winner"] = None
        match["walkover"] = False
        match.setdefault("score_corrections", []).append(
            {
                "before": sets_before,
                "after": [list(item) for item in match["sets"]],
                "reason": reason,
                "actor": "scorekeeper",
                "at": now_wib(match.get("_timezone")).isoformat(timespec="seconds"),
            }
        )
        _append_scorekeeper_event(
            match,
            "score.correction_opened",
            side="a" if winning_index == 0 else "b",
            metadata={
                "reason": reason,
                "before_current": [0, 0],
                "after_current": restored_current,
                "sets_before": sets_before,
                "sets_after": [list(item) for item in match["sets"]],
            },
        )

    else:
        raise ValueError("Aksi scorekeeper tidak dikenal.")

    return scorekeeper_state(match)


def compute_standings(matches, teams, category, group, policy_config=None):
    """Round robin standings for a category+group.
    Poin sesuai Pedoman Aturan Mini Round Interport 2026 bagian 10:
    menang=2, kalah setelah bertanding=1, kalah W.O.=0."""
    policy = {**DEFAULT_STANDING_POLICY, **(policy_config or {})}
    group_matches = [
        match for match in matches
        if match.get("category") == category and match.get("group") == group
    ]
    codes = {
        code for code, team in teams.items()
        if team.get("category") == category and team.get("group") == group
    }
    codes.update(
        code for match in group_matches
        for code in (match.get("team_a"), match.get("team_b"))
        if code
    )
    codes = sorted(codes)
    table = {
        c: {
            "code": c, "team": team_label(teams, c),
            "site_code": teams[c].get("site_code", ""),
            "player1": teams[c].get("player1", ""), "player2": teams[c].get("player2", ""),
            "color": teams[c].get("color", "#9c9c9c"), "text": teams[c].get("text", "#ffffff"),
            "played": 0, "win": 0, "loss": 0,
            "set_win": 0, "set_loss": 0,
            "point_win": 0, "point_loss": 0,
            "points": 0,
        } for c in codes
    }
    relevant = [m for m in group_matches if is_valid_completed_match(m)]
    for m in relevant:
        a, b = m["team_a"], m["team_b"]
        if a not in table or b not in table:
            continue
        sa, sb = compute_sets_won(m["sets"])
        if m.get("walkover") and not m.get("sets"):
            needed = sets_needed_to_win(m)
            if m.get("winner") == a:
                sa, sb = needed, 0
            elif m.get("winner") == b:
                sa, sb = 0, needed
        pa = sum(s[0] for s in m["sets"])
        pb = sum(s[1] for s in m["sets"])
        table[a]["played"] += 1
        table[b]["played"] += 1
        table[a]["set_win"] += sa
        table[a]["set_loss"] += sb
        table[b]["set_win"] += sb
        table[b]["set_loss"] += sa
        table[a]["point_win"] += pa
        table[a]["point_loss"] += pb
        table[b]["point_win"] += pb
        table[b]["point_loss"] += pa
        if m["winner"] == a:
            table[a]["win"] += 1
            table[a]["points"] += int(policy["win_points"])
            table[b]["loss"] += 1
            table[b]["points"] += int(
                policy["walkover_loss_points"]
                if m.get("walkover") else policy["played_loss_points"]
            )
        elif m["winner"] == b:
            table[b]["win"] += 1
            table[b]["points"] += int(policy["win_points"])
            table[a]["loss"] += 1
            table[a]["points"] += int(
                policy["walkover_loss_points"]
                if m.get("walkover") else policy["played_loss_points"]
            )

    rows = list(table.values())
    for r in rows:
        r["set_diff"] = r["set_win"] - r["set_loss"]
        r["point_diff"] = r["point_win"] - r["point_loss"]

    # Rank equal competition points by the published head-to-head policy.
    # For 3+ tied entrants, the head-to-head comparison is a mini-table made
    # only from matches between those entrants.
    by_points = {}
    for row in rows:
        by_points.setdefault(row["points"], []).append(row)

    ranked = []
    for points in sorted(by_points, reverse=True):
        tied = by_points[points]
        tied_codes = {row["code"] for row in tied}
        if len(tied) == 1:
            tied[0]["tie_break"] = None
        elif len(tied) == 2 and "head_to_head" in policy["tie_break_order"]:
            direct = next(
                (
                    match for match in relevant
                    if {match.get("team_a"), match.get("team_b")} == tied_codes
                    and match.get("winner") in tied_codes
                ),
                None,
            )
            if direct:
                winner = direct["winner"]
                tied.sort(
                    key=lambda row: (
                        row["code"] != winner,
                        -row["set_diff"],
                        -row["point_diff"],
                        row["code"],
                    )
                )
                for row in tied:
                    row["tie_break"] = "Head-to-head"
            else:
                tied.sort(
                    key=lambda row: (-row["set_diff"], -row["point_diff"], row["code"])
                )
                for row in tied:
                    row["tie_break"] = "Selisih game/poin"
        elif len(tied) >= 3 and "mini_table" in policy["tie_break_order"]:
            mini = {
                code: {"points": 0, "set_diff": 0, "point_diff": 0}
                for code in tied_codes
            }
            for match in relevant:
                a, b = match.get("team_a"), match.get("team_b")
                if a not in tied_codes or b not in tied_codes:
                    continue
                sa, sb = compute_sets_won(match.get("sets") or [])
                if match.get("walkover") and not match.get("sets"):
                    needed = sets_needed_to_win(match)
                    sa, sb = (needed, 0) if match.get("winner") == a else (0, needed)
                pa = sum(segment[0] for segment in match.get("sets") or [])
                pb = sum(segment[1] for segment in match.get("sets") or [])
                mini[a]["set_diff"] += sa - sb
                mini[b]["set_diff"] += sb - sa
                mini[a]["point_diff"] += pa - pb
                mini[b]["point_diff"] += pb - pa
                if match.get("winner") == a:
                    mini[a]["points"] += int(policy["win_points"])
                    mini[b]["points"] += int(
                        policy["walkover_loss_points"]
                        if match.get("walkover") else policy["played_loss_points"]
                    )
                elif match.get("winner") == b:
                    mini[b]["points"] += int(policy["win_points"])
                    mini[a]["points"] += int(
                        policy["walkover_loss_points"]
                        if match.get("walkover") else policy["played_loss_points"]
                    )
            tied.sort(
                key=lambda row: (
                    -mini[row["code"]]["points"],
                    -mini[row["code"]]["set_diff"],
                    -mini[row["code"]]["point_diff"],
                    -row["set_diff"],
                    -row["point_diff"],
                    row["code"],
                )
            )
            for row in tied:
                row["tie_break"] = "Mini-table head-to-head"
        else:
            tied.sort(
                key=lambda row: (-row["set_diff"], -row["point_diff"], row["code"])
            )
            for row in tied:
                row["tie_break"] = "Selisih game/poin"
        ranked.extend(tied)

    rows = ranked
    for i, r in enumerate(rows, start=1):
        r["rank"] = i
    return rows


def group_champion(matches, teams, category, group, policy_config=None):
    played = [
        m for m in matches
        if m["category"] == category and m["group"] == group
        and m.get("status") != "cancelled"
    ]
    completed = [m for m in played if is_valid_completed_match(m)]
    standings = compute_standings(
        matches, teams, category, group, policy_config=policy_config
    )
    if not played or len(completed) < len(played) or not standings:
        return None
    return standings[0]["code"]


def _matches_for_stage(matches, division_key, stage):
    division_matches = [
        match for match in matches if match.get("category") == division_key
    ]
    stage_key = stage.get("key")
    explicit = [
        match for match in division_matches
        if match.get("stage_key") == stage_key
    ]
    if explicit:
        return explicit
    if stage.get("type") in {"group", "round_robin"}:
        return [
            match for match in division_matches
            if match.get("group") and match.get("group") not in {"FINAL", "KNOCKOUT", "SEMIFINAL"} and match.get("stage_type", "group") in {"group", "round_robin"}
        ]
    if stage.get("type") == "final":
        return [match for match in division_matches if match.get("group") == "FINAL" or match.get("stage_type") == "final"]
    if stage.get("type") in {"semifinal", "semi_final", "knockout"}:
        return [match for match in division_matches if match.get("group") in {"KNOCKOUT", "SEMIFINAL"} or match.get("stage_type") in {"semifinal", "semi_final", "knockout"}]
    return []


def _terminal_stage_champion(stage_matches):
    active = [
        match for match in stage_matches if match.get("status") != "cancelled"
    ]
    if not active or any(not is_valid_completed_match(match) for match in active):
        return None
    final_match = max(
        active,
        key=lambda match: (
            int(match.get("round") or 0), match.get("date") or "",
            match.get("time") or "", match.get("id") or "",
        ),
    )
    return final_match.get("winner")


def build_competition_view(matches, teams, config, sport_key=None):
    """Build a stage-driven view used by standings, brackets, and champions."""
    structure = load_competition_structure()
    champions = config.get("champions", {})
    divisions = []
    for definition in structure.get("divisions", []):
        if not definition.get("enabled", True):
            continue
        if sport_key and sport_key != "all" and definition["sport_key"] != sport_key:
            continue
        division = dict(definition)
        division_matches = [
            match for match in matches
            if match.get("category") == division["key"]
            and match.get("sport_key", "table-tennis") == division["sport_key"]
        ]
        policy = (division.get("standing_policy") or {}).get("config") or {}
        stage_views = []
        group_winners = {}
        for stage in sorted(
            division.get("stages", []), key=lambda item: item.get("sequence", 0)
        ):
            stage_view = dict(stage)
            stage_matches = _matches_for_stage(division_matches, division["key"], stage)
            stage_view["matches"] = stage_matches
            stage_view["groups_view"] = []
            if stage.get("type") in {"group", "round_robin"}:
                for group in stage.get("groups", []):
                    group_key = group["key"]
                    rows = compute_standings(
                        division_matches, teams, division["key"], group_key,
                        policy_config=policy,
                    )
                    champion = group_champion(
                        division_matches, teams, division["key"], group_key,
                        policy_config=policy,
                    )
                    if champion:
                        group_winners[group_key] = champion
                    photo_key = f"{division['key']}_{group_key}"
                    group_matches = [
                        match for match in stage_matches
                        if match.get("group") == group_key
                    ]
                    stage_view["groups_view"].append(
                        {
                            **group,
                            "rows": rows,
                            "matches": group_matches,
                            "champion": champion,
                            "champion_target": group_key,
                            "champion_photo": champions.get(photo_key, {}).get(
                                "photo_url"
                            ),
                            "complete": bool(group_matches) and all(
                                match.get("status") == "cancelled"
                                or is_valid_completed_match(match)
                                for match in group_matches
                            ),
                        }
                    )
            stage_views.append(stage_view)

        terminal_stage = max(
            stage_views, key=lambda item: item.get("sequence", 0), default=None
        )
        champion = None
        champion_target = None
        if terminal_stage:
            if terminal_stage.get("type") in {"group", "round_robin"}:
                groups_view = terminal_stage.get("groups_view", [])
                if (
                    terminal_stage.get("qualification_policy", {}).get(
                        "champion_from_standings"
                    )
                    and len(groups_view) == 1
                ):
                    champion = groups_view[0].get("champion")
                    champion_target = groups_view[0].get("key")
            else:
                champion = _terminal_stage_champion(
                    terminal_stage.get("matches", [])
                )
                champion_target = (
                    "FINAL" if terminal_stage.get("type") == "final"
                    else terminal_stage.get("key")
                )
        photo_key = (
            f"{division['key']}_{champion_target}" if champion_target else None
        )

        # Silver = losing finalist; bronze = winner of the 3rd-place playoff.
        # Only knockout_format "semi_and_final" divisions produce a 3rd-place
        # match, so bronze stays None for "final_only" divisions.
        final_match = next(
            (
                match for match in division_matches
                if match.get("group") == "FINAL" or match.get("stage_type") == "final"
            ),
            None,
        )
        silver = None
        if final_match and is_valid_completed_match(final_match) and final_match.get("winner"):
            silver = (
                final_match["team_b"]
                if final_match["winner"] == final_match["team_a"]
                else final_match["team_a"]
            )
        third_place_match = next(
            (match for match in division_matches if match.get("stage_type") == "third_place"),
            None,
        )
        bronze = None
        if third_place_match and is_valid_completed_match(third_place_match):
            bronze = third_place_match.get("winner")

        division.update(
            {
                "matches": division_matches,
                "stages_view": stage_views,
                "group_winners": group_winners,
                "champion": champion,
                "champion_target": champion_target,
                "champion_photo": (
                    champions.get(photo_key, {}).get("photo_url")
                    if photo_key else None
                ),
                "silver": silver,
                "bronze": bronze,
            }
        )
        divisions.append(division)
    return {**structure, "divisions": divisions}


def compute_medal_tally(divisions, teams, config):
    """Olympic-style medal table: aggregate gold/silver/bronze per site across
    every division's champion/silver/bronze, ranked gold > silver > bronze."""
    site_lookup = {site["code"]: site["name"] for site in config.get("sites", [])}
    tally = {}
    for division in divisions:
        for medal, code in (
            ("gold", division.get("champion")),
            ("silver", division.get("silver")),
            ("bronze", division.get("bronze")),
        ):
            if not code:
                continue
            team = teams.get(code)
            site_code = team.get("site_code") if team else None
            if not site_code:
                continue
            entry = tally.setdefault(
                site_code,
                {"code": site_code, "name": site_lookup.get(site_code, site_code), "gold": 0, "silver": 0, "bronze": 0},
            )
            entry[medal] += 1

    ranked = sorted(
        tally.values(),
        key=lambda entry: (-entry["gold"], -entry["silver"], -entry["bronze"], entry["name"]),
    )
    for index, entry in enumerate(ranked, start=1):
        entry["rank"] = index
        entry["total"] = entry["gold"] + entry["silver"] + entry["bronze"]
    return ranked
