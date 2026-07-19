import json
import os
import shutil
import threading
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
_LOCK = threading.Lock()

# Penyimpanan data: default file lokal data/*.json (untuk dev). Vercel serverless
# filesystem-nya read-only, jadi kalau env var DATABASE_URL tersedia, otomatis
# pindah pakai Postgres (skema khusus "tennis", terisolasi dari tabel lain).
DATABASE_URL = os.environ.get("DATABASE_URL")
USE_DB = bool(DATABASE_URL)

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

    def close_request_connection():
        """Panggil di teardown_appcontext Flask supaya koneksi per-request ditutup rapi."""
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

DAY_NAMES = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
MONTH_NAMES = [
    "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]


def _path(name):
    return os.path.join(DATA_DIR, name)


def load_json(name):
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


def load_teams():
    return load_json("teams.json")


def load_matches():
    return load_json("matches.json")


def save_matches(matches):
    save_json("matches.json", matches)


def load_config():
    return load_json("config.json")


def backup_data_files(*names):
    """Cadangkan data sebelum operasi merusak (mis. reset/acak ulang).
    Di DB: disalin ke tennis.app_data_backups. Di lokal: disalin ke data/backups/."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
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


def team_label(teams, code):
    if not code:
        return "TBD"
    t = teams.get(code)
    if not t:
        return code
    return f'{t["player1"]} / {t["player2"]}'


def team_short(teams, code):
    if not code:
        return "TBD"
    return code


def truncate_words(text, max_words=2):
    words = (text or "").split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "…"


def format_date_id(date_str):
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{DAY_NAMES[d.weekday()]}, {d.day} {MONTH_NAMES[d.month]} {d.year}"


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
    """Final Ganda Putra = Best of 5 (menang 3 set). Semua laga fase grup = Best of 3 (menang 2 set)."""
    return 3 if match.get("group") == "FINAL" else 2


def compute_winner(match):
    sets = match.get("sets") or []
    if not sets:
        return None
    needed = sets_needed_to_win(match)
    a, b = compute_sets_won(sets)
    if a >= needed or b >= needed:
        return match["team_a"] if a > b else match["team_b"]
    return None


def sync_winner(match):
    """Recompute winner/status from sets. Call whenever sets are updated."""
    w = compute_winner(match)
    match["winner"] = w
    if w:
        match["status"] = "completed"
    elif match["status"] == "completed":
        match["status"] = "scheduled"
    return match


def compute_standings(matches, teams, category, group):
    """Round robin standings for a category+group.
    Poin sesuai Pedoman Aturan Mini Round Interport 2026 bagian 10:
    menang=2, kalah setelah bertanding=1, kalah W.O.=0."""
    codes = [c for c, t in teams.items() if t["category"] == category and t["group"] == group]
    table = {
        c: {
            "code": c, "team": team_label(teams, c),
            "player1": teams[c].get("player1", ""), "player2": teams[c].get("player2", ""),
            "color": teams[c].get("color", "#9c9c9c"), "text": teams[c].get("text", "#ffffff"),
            "played": 0, "win": 0, "loss": 0,
            "set_win": 0, "set_loss": 0,
            "point_win": 0, "point_loss": 0,
            "points": 0,
        } for c in codes
    }
    relevant = [
        m for m in matches
        if m["category"] == category and m["group"] == group and m["status"] == "completed"
    ]
    for m in relevant:
        a, b = m["team_a"], m["team_b"]
        if a not in table or b not in table:
            continue
        sa, sb = compute_sets_won(m["sets"])
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
            table[a]["points"] += 2
            table[b]["loss"] += 1
            table[b]["points"] += 0 if m.get("walkover") else 1
        elif m["winner"] == b:
            table[b]["win"] += 1
            table[b]["points"] += 2
            table[a]["loss"] += 1
            table[a]["points"] += 0 if m.get("walkover") else 1

    rows = list(table.values())
    for r in rows:
        r["set_diff"] = r["set_win"] - r["set_loss"]
        r["point_diff"] = r["point_win"] - r["point_loss"]
    rows.sort(key=lambda r: (-r["points"], -r["set_diff"], -r["point_diff"]))
    for i, r in enumerate(rows, start=1):
        r["rank"] = i
    return rows


def group_champion(matches, teams, category, group):
    played = [m for m in matches if m["category"] == category and m["group"] == group]
    completed = [m for m in played if m["status"] == "completed"]
    standings = compute_standings(matches, teams, category, group)
    if len(completed) < len(played) or not standings:
        return None
    return standings[0]["code"]
