"""Deterministic conversion from the legacy JSON documents to normalized rows."""

from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from domain.scoring import validate_match_score as validate_table_tennis_score

from .identifiers import slugify, stable_uuid


SPORT_DEFINITIONS = (
    ("table-tennis", "Table Tennis", "🏓"),
    ("padel", "Padel", "🎾"),
    ("badminton", "Badminton", "🏸"),
)

TABLE_ORDER = (
    "tournaments",
    "sports",
    "tournament_sports",
    "rule_profiles",
    "standing_policies",
    "divisions",
    "people",
    "entrants",
    "entrant_members",
    "stages",
    "groups",
    "venues",
    "courts",
    "matches",
    "match_segments",
    "comments",
    "legacy_reaction_totals",
    "media_assets",
    "announcements",
    "audit_logs",
    "import_runs",
)


@dataclass
class ImportPlan:
    tournament_id: str
    tournament_slug: str
    records: dict[str, list[dict]]
    source_checksums: dict[str, str]
    warnings: list[dict] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)

    @property
    def counts(self):
        return {table: len(self.records.get(table, [])) for table in TABLE_ORDER}

    def as_report(self):
        return {
            "tournament_id": self.tournament_id,
            "tournament_slug": self.tournament_slug,
            "source_checksums": self.source_checksums,
            "counts": self.counts,
            "warnings": self.warnings,
            "errors": self.errors,
        }

    def assert_valid(self):
        if self.errors:
            messages = "; ".join(error["message"] for error in self.errors)
            raise ValueError(f"Legacy import plan tidak valid: {messages}")


def _canonical_checksum(value):
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return sha256(payload).hexdigest()


def _iso_scheduled_at(date_value, time_value, timezone_name):
    local = datetime.strptime(
        f"{date_value} {time_value}", "%Y-%m-%d %H:%M"
    ).replace(tzinfo=ZoneInfo(timezone_name))
    return local.isoformat(timespec="minutes")


def _rule_profile_rows(sport_ids):
    definitions = (
        (
            "table-tennis-bo3",
            "table-tennis",
            "Table Tennis Best of 3",
            "game",
            {"best_of": 3, "segments_to_win": 2, "points_to_win": 11, "win_by": 2},
        ),
        (
            "table-tennis-bo5",
            "table-tennis",
            "Table Tennis Best of 5",
            "game",
            {"best_of": 5, "segments_to_win": 3, "points_to_win": 11, "win_by": 2},
        ),
        (
            "badminton-21-bo3",
            "badminton",
            "Badminton 21-point Best of 3",
            "game",
            {
                "best_of": 3,
                "segments_to_win": 2,
                "points_to_win": 21,
                "win_by": 2,
                "point_cap": 30,
            },
        ),
        (
            "padel-standard-advantage",
            "padel",
            "Padel Best of 3 — Advantage",
            "set",
            {
                "best_of": 3,
                "segments_to_win": 2,
                "game_scoring_method": "advantage",
                "games_to_win_set": 6,
                "tie_break_at": "6-6",
                "deciding_set_policy": "standard",
            },
        ),
        (
            "padel-standard-golden-point",
            "padel",
            "Padel Best of 3 — Golden Point",
            "set",
            {
                "best_of": 3,
                "segments_to_win": 2,
                "game_scoring_method": "golden_point",
                "games_to_win_set": 6,
                "tie_break_at": "6-6",
                "deciding_set_policy": "standard",
            },
        ),
    )
    rows = []
    profile_ids = {}
    for profile_key, sport_key, name, segment_term, config in definitions:
        profile_id = stable_uuid("rule-profile", profile_key, 1)
        profile_ids[profile_key] = profile_id
        rows.append(
            {
                "id": profile_id,
                "sport_id": sport_ids[sport_key],
                "profile_key": profile_key,
                "version": 1,
                "name": name,
                "segment_term": segment_term,
                "config": config,
            }
        )
    return rows, profile_ids


def _team_member_names(team, participants):
    """Nama pemain 1/2 dari sebuah tim -- baik format lama (player1/player2
    langsung) maupun format roster (members: participant_id + role, dengan
    nama sebenarnya di participants.json)."""
    members = team.get("members")
    if not members:
        return [team.get("player1"), team.get("player2")]
    by_role = {m.get("role"): m.get("participant_id") for m in members}
    names = []
    for role in ("pemain1", "pemain2"):
        pid = by_role.get(role)
        person = participants.get(pid) if pid else None
        names.append(person.get("name") if person else None)
    return names


def build_import_plan(config, teams, matches, source_checksums=None, participants=None):
    participants = participants or {}
    source_checksums = source_checksums or {
        "config.json": _canonical_checksum(config),
        "teams.json": _canonical_checksum(teams),
        "matches.json": _canonical_checksum(matches),
    }
    tournament_slug = slugify(config.get("tournament_short_name") or config.get("tournament_name"))
    tournament_id = stable_uuid("tournament", tournament_slug)
    timezone_name = config.get("timezone", "Asia/Jakarta")
    records = {table: [] for table in TABLE_ORDER}
    warnings = []
    errors = []

    tournament_status = config.get("status", "active")
    if tournament_status not in {"draft", "published", "active", "completed", "cancelled"}:
        warnings.append(
            {
                "code": "unknown_tournament_status",
                "message": f"Status {tournament_status!r} dipetakan ke 'active'.",
            }
        )
        tournament_status = "active"

    records["tournaments"].append(
        {
            "id": tournament_id,
            "slug": tournament_slug,
            "name": config["tournament_name"],
            "short_name": config.get("tournament_short_name", config["tournament_name"]),
            "timezone": timezone_name,
            "locale": config.get("locale", "id-ID"),
            "status": tournament_status,
            "starts_on": config["start_date"],
            "ends_on": config["end_date"],
            "branding_profile": {},
            "source_metadata": {
                "legacy_buffer_dates": config.get("buffer_dates", []),
                "legacy_time_window": config.get("time_window"),
                "legacy_time_window_note": config.get("time_window_note"),
                "legacy_final_date": config.get("final_date"),
                "legacy_closing_date": config.get("closing_date"),
                "legacy_final_note": config.get("final_note"),
                "ga_measurement_id": config.get("ga_measurement_id", ""),
            },
        }
    )

    sport_ids = {}
    tournament_sport_ids = {}
    for order, (sport_key, name, icon) in enumerate(SPORT_DEFINITIONS, start=1):
        sport_id = stable_uuid("sport", sport_key)
        tournament_sport_id = stable_uuid(
            "tournament-sport", tournament_id, sport_key
        )
        sport_ids[sport_key] = sport_id
        tournament_sport_ids[sport_key] = tournament_sport_id
        records["sports"].append(
            {
                "id": sport_id,
                "sport_key": sport_key,
                "slug": sport_key,
                "name": name,
                "icon": icon,
            }
        )
        enabled = sport_key == "table-tennis"
        records["tournament_sports"].append(
            {
                "id": tournament_sport_id,
                "tournament_id": tournament_id,
                "sport_id": sport_id,
                "enabled": enabled,
                "display_order": order,
                "feature_flags": {
                    "schedule": enabled,
                    "standings": enabled,
                    "comments": enabled,
                    "reactions": enabled,
                    "media": enabled,
                    "streaming": False,
                },
            }
        )

    rule_rows, profile_ids = _rule_profile_rows(sport_ids)
    records["rule_profiles"].extend(rule_rows)

    standing_policy_id = stable_uuid("standing-policy", "legacy-table-tennis", 1)
    records["standing_policies"].append(
        {
            "id": standing_policy_id,
            "policy_key": "legacy-table-tennis",
            "version": 1,
            "name": "InterSport Table Tennis Group Policy",
            "config": {
                "win_points": 2,
                "played_loss_points": 1,
                "walkover_loss_points": 0,
                "tie_break_order": [
                    "competition_points",
                    "head_to_head",
                    "mini_table",
                    "segment_difference",
                    "point_difference",
                    "deciding_match",
                ],
            },
        }
    )

    category_config = {item["key"]: item for item in config.get("categories", [])}
    division_ids = {}
    stage_ids = {}
    group_ids = {}
    for order, category in enumerate(config.get("categories", []), start=1):
        category_key = category["key"]
        division_id = stable_uuid("division", tournament_id, "table-tennis", category_key)
        division_ids[category_key] = division_id
        records["divisions"].append(
            {
                "id": division_id,
                "tournament_sport_id": tournament_sport_ids["table-tennis"],
                "division_key": category_key,
                "name": category.get("label", category_key),
                "entrant_type": "team",
                "min_team_size": 2,
                "max_team_size": 2,
                "default_rule_profile_id": profile_ids["table-tennis-bo3"],
                "standing_policy_id": standing_policy_id,
                "enabled": True,
                "display_order": order,
            }
        )

        group_stage_id = stable_uuid("stage", division_id, "group-stage")
        stage_ids[(category_key, "group")] = group_stage_id
        records["stages"].append(
            {
                "id": group_stage_id,
                "division_id": division_id,
                "stage_key": "group-stage",
                "stage_type": "group",
                "name": "Babak Grup",
                "sequence": 1,
                "qualification_policy": (
                    {"qualifiers_per_group": 1, "destination_stage": "final"}
                    if category.get("has_final")
                    else {"champion_from_standings": True}
                ),
            }
        )
        for group_order, group_key in enumerate(category.get("groups", []), start=1):
            group_id = stable_uuid("group", group_stage_id, group_key)
            group_ids[(category_key, group_key)] = group_id
            records["groups"].append(
                {
                    "id": group_id,
                    "stage_id": group_stage_id,
                    "group_key": group_key,
                    "name": f"Group {group_key}",
                    "display_order": group_order,
                }
            )
        if category.get("has_final"):
            final_stage_id = stable_uuid("stage", division_id, "final")
            stage_ids[(category_key, "final")] = final_stage_id
            records["stages"].append(
                {
                    "id": final_stage_id,
                    "division_id": division_id,
                    "stage_key": "final",
                    "stage_type": "final",
                    "name": "Final",
                    "sequence": 2,
                    "qualification_policy": {
                        "source": "group-stage",
                        "entrants": "group-winners",
                    },
                }
            )

    entrant_ids = {}
    for entrant_order, (code, team) in enumerate(teams.items(), start=1):
        category_key = team.get("category")
        division_id = division_ids.get(category_key)
        if not division_id:
            errors.append(
                {
                    "code": "unknown_team_division",
                    "entity": code,
                    "message": f"Tim {code} memakai kategori yang tidak dikenal: {category_key}.",
                }
            )
            continue
        entrant_id = stable_uuid("entrant", division_id, code)
        entrant_ids[code] = entrant_id
        member_names = _team_member_names(team, participants)
        display_name = " / ".join(name for name in member_names if name) or code
        records["entrants"].append(
            {
                "id": entrant_id,
                "division_id": division_id,
                "code": code,
                "display_name": display_name,
                "seed": entrant_order,
                "status": "active",
                "branding": {
                    "background_color": team.get("color"),
                    "text_color": team.get("text"),
                },
                "source_metadata": {"legacy_group": team.get("group")},
            }
        )
        for member_order, name in enumerate(member_names, start=1):
            if not name:
                continue
            person_id = stable_uuid("person", entrant_id, member_order, name)
            records["people"].append(
                {
                    "id": person_id,
                    "display_name": name,
                    "employee_reference": None,
                    "privacy_flags": {},
                    "source_metadata": {
                        "legacy_team_code": code,
                        "legacy_member_order": member_order,
                    },
                }
            )
            records["entrant_members"].append(
                {
                    "id": stable_uuid("entrant-member", entrant_id, person_id),
                    "entrant_id": entrant_id,
                    "person_id": person_id,
                    "member_role": "player",
                    "member_order": member_order,
                }
            )

    venue_id = stable_uuid("venue", tournament_id, config.get("venue", "Venue"))
    records["venues"].append(
        {
            "id": venue_id,
            "tournament_id": tournament_id,
            "name": config.get("venue", "Venue"),
            "address": None,
            "timezone": timezone_name,
        }
    )
    court_ids = {}
    for court_name in sorted({match.get("court") for match in matches if match.get("court")}):
        court_key = slugify(court_name)
        court_id = stable_uuid("court", venue_id, "table-tennis", court_key)
        court_ids[court_name] = court_id
        records["courts"].append(
            {
                "id": court_id,
                "venue_id": venue_id,
                "sport_id": sport_ids["table-tennis"],
                "court_key": court_key,
                "name": court_name,
                "enabled": True,
            }
        )

    match_ids = {}
    for legacy_match in matches:
        display_code = legacy_match.get("id")
        match_id = stable_uuid("match", tournament_id, display_code)
        match_ids[display_code] = match_id
        category_key = legacy_match.get("category")
        division_id = division_ids.get(category_key)
        if not division_id:
            errors.append(
                {
                    "code": "unknown_match_division",
                    "entity": display_code,
                    "message": f"Match {display_code} memakai kategori tidak dikenal: {category_key}.",
                }
            )
            continue

        is_final = legacy_match.get("group") == "FINAL"
        stage_id = stage_ids.get((category_key, "final" if is_final else "group"))
        group_id = None if is_final else group_ids.get((category_key, legacy_match.get("group")))
        if not stage_id or (not is_final and not group_id):
            errors.append(
                {
                    "code": "unknown_match_stage",
                    "entity": display_code,
                    "message": f"Stage/group match {display_code} tidak dapat dipetakan.",
                }
            )
            continue

        try:
            scheduled_at = _iso_scheduled_at(
                legacy_match["date"], legacy_match["time"], timezone_name
            )
        except (KeyError, ValueError) as exc:
            errors.append(
                {
                    "code": "invalid_match_schedule",
                    "entity": display_code,
                    "message": f"Jadwal match {display_code} tidak valid: {exc}.",
                }
            )
            scheduled_at = None

        entrant_a_id = entrant_ids.get(legacy_match.get("team_a"))
        entrant_b_id = entrant_ids.get(legacy_match.get("team_b"))
        if legacy_match.get("team_a") and not entrant_a_id:
            errors.append(
                {
                    "code": "unknown_match_entrant",
                    "entity": display_code,
                    "message": f"Tim A match {display_code} tidak ditemukan.",
                }
            )
        if legacy_match.get("team_b") and not entrant_b_id:
            errors.append(
                {
                    "code": "unknown_match_entrant",
                    "entity": display_code,
                    "message": f"Tim B match {display_code} tidak ditemukan.",
                }
            )

        best_of = 5 if is_final else 3
        score = validate_table_tennis_score(
            legacy_match.get("sets") or [], best_of=best_of
        )
        result_errors = list(score.errors)
        legacy_status = legacy_match.get("status", "scheduled")
        walkover = bool(legacy_match.get("walkover"))
        normalized_status = legacy_status
        result_valid = True
        winner_id = entrant_ids.get(legacy_match.get("winner"))
        if legacy_status == "completed":
            if walkover:
                if winner_id not in (entrant_a_id, entrant_b_id):
                    result_errors.append("Pemenang WO tidak sesuai dengan peserta.")
            else:
                if not score.is_complete:
                    result_errors.append("Status selesai belum memiliki skor sah.")
                else:
                    expected_winner = entrant_a_id if score.winner_side == "a" else entrant_b_id
                    if winner_id != expected_winner:
                        result_errors.append("Pemenang tersimpan tidak sesuai skor.")
            if result_errors:
                normalized_status = "suspended"
                result_valid = False
                winner_id = None
                warnings.append(
                    {
                        "code": "invalid_completed_result",
                        "entity": display_code,
                        "message": f"Match {display_code} dikarantina sebagai suspended: {' '.join(result_errors)}",
                    }
                )
        elif legacy_status not in {
            "draft", "scheduled", "check_in", "live", "postponed", "suspended", "cancelled"
        }:
            warnings.append(
                {
                    "code": "unknown_match_status",
                    "entity": display_code,
                    "message": f"Status {legacy_status!r} pada {display_code} dipetakan ke scheduled.",
                }
            )
            normalized_status = "scheduled"

        rule_profile_key = "table-tennis-bo5" if is_final else "table-tennis-bo3"
        records["matches"].append(
            {
                "id": match_id,
                "tournament_id": tournament_id,
                "division_id": division_id,
                "stage_id": stage_id,
                "group_id": group_id,
                "display_code": display_code,
                "round_number": legacy_match.get("round"),
                "round_label": legacy_match.get("round_label"),
                "entrant_a_id": entrant_a_id,
                "entrant_b_id": entrant_b_id,
                "court_id": court_ids.get(legacy_match.get("court")),
                "rule_profile_id": profile_ids[rule_profile_key],
                "scheduled_at": scheduled_at,
                "status": normalized_status,
                "result_type": "walkover" if walkover else "normal",
                "winner_entrant_id": winner_id,
                "result_valid": result_valid,
                "version": int(legacy_match.get("version", 0)),
                "notes": legacy_match.get("notes", ""),
                "source_metadata": {
                    "legacy_id": display_code,
                    "legacy_status": legacy_status,
                    "legacy_category": category_key,
                    "legacy_group": legacy_match.get("group"),
                    "legacy_winner": legacy_match.get("winner"),
                    "import_errors": result_errors,
                },
            }
        )

        for sequence, segment in enumerate(legacy_match.get("sets") or [], start=1):
            if not isinstance(segment, list) or len(segment) != 2:
                errors.append(
                    {
                        "code": "invalid_segment_shape",
                        "entity": display_code,
                        "message": f"Segmen {sequence} pada {display_code} tidak berisi dua skor.",
                    }
                )
                continue
            records["match_segments"].append(
                {
                    "id": stable_uuid("match-segment", match_id, sequence),
                    "match_id": match_id,
                    "sequence": sequence,
                    "segment_type": "game",
                    "score_a": segment[0],
                    "score_b": segment[1],
                    "status": "invalid" if result_errors else "completed",
                    "metadata": {"legacy_field": "sets"},
                }
            )

        for comment_index, comment in enumerate(legacy_match.get("comments") or [], start=1):
            created_at = comment.get("at") or scheduled_at
            records["comments"].append(
                {
                    "id": stable_uuid("comment", match_id, comment_index, created_at),
                    "match_id": match_id,
                    "author_name": comment.get("name", "Anonim"),
                    "body": comment.get("comment", ""),
                    "moderation_status": "pending",
                    "source_metadata": {"legacy_index": comment_index},
                    "created_at": created_at,
                }
            )

        for side in ("a", "b"):
            for reaction, count in (legacy_match.get("votes", {}).get(side, {}) or {}).items():
                if not count:
                    continue
                records["legacy_reaction_totals"].append(
                    {
                        "id": stable_uuid("legacy-reaction", match_id, side, reaction),
                        "match_id": match_id,
                        "side": side,
                        "reaction": reaction,
                        "reaction_count": int(count),
                    }
                )

        for media_index, document in enumerate(legacy_match.get("docs") or [], start=1):
            source_url = document.get("url")
            if not source_url:
                continue
            records["media_assets"].append(
                {
                    "id": stable_uuid("match-media", match_id, media_index, source_url),
                    "tournament_id": tournament_id,
                    "owner_type": "match",
                    "owner_id": match_id,
                    "storage_key": None,
                    "source_url": source_url,
                    "mime_type": None,
                    "width": None,
                    "height": None,
                    "moderation_status": "approved",
                    "metadata": {
                        "legacy_uploaded_at": document.get("uploaded_at"),
                    },
                }
            )

        for history_index, change in enumerate(
            legacy_match.get("reschedule_history") or [], start=1
        ):
            records["audit_logs"].append(
                {
                    "id": stable_uuid("legacy-reschedule", match_id, history_index),
                    "tournament_id": tournament_id,
                    "actor_user_id": None,
                    "action": "match.rescheduled.imported",
                    "entity_type": "match",
                    "entity_id": match_id,
                    "before_data": {
                        "date": change.get("from_date"),
                        "time": change.get("from_time"),
                        "court": change.get("from_court"),
                    },
                    "after_data": {
                        "date": change.get("to_date"),
                        "time": change.get("to_time"),
                        "court": change.get("to_court"),
                    },
                    "reason": change.get("reason"),
                    "request_id": None,
                    "metadata": {"legacy_at": change.get("at")},
                }
            )

        if result_errors:
            records["audit_logs"].append(
                {
                    "id": stable_uuid("import-quarantine", match_id),
                    "tournament_id": tournament_id,
                    "actor_user_id": None,
                    "action": "match.result.quarantined",
                    "entity_type": "match",
                    "entity_id": match_id,
                    "before_data": {
                        "status": legacy_status,
                        "winner": legacy_match.get("winner"),
                        "sets": legacy_match.get("sets") or [],
                    },
                    "after_data": {"status": normalized_status, "winner": None},
                    "reason": "Legacy result failed scoring validation during import.",
                    "request_id": None,
                    "metadata": {"errors": result_errors},
                }
            )

    final_match_dates = {
        match.get("date") for match in matches if match.get("group") == "FINAL"
    }
    configured_final_date = config.get("final_date")
    if final_match_dates and configured_final_date not in final_match_dates:
        warnings.append(
            {
                "code": "final_date_mismatch",
                "message": (
                    f"config.final_date={configured_final_date} berbeda dari tanggal match final "
                    f"{sorted(final_match_dates)}. Nilai sumber dipertahankan untuk rekonsiliasi manual."
                ),
            }
        )

    announcement_title = (config.get("announcement_title") or "").strip()
    announcement_body = (config.get("announcement_text") or "").strip()
    if announcement_title or announcement_body:
        records["announcements"].append(
            {
                "id": stable_uuid("announcement", tournament_id, 1),
                "tournament_id": tournament_id,
                "sport_id": None,
                "title": announcement_title or "Pengumuman",
                "body": announcement_body,
                "priority": 0,
                "status": "published",
                "starts_at": None,
                "ends_at": None,
            }
        )

    for champion_key, champion in (config.get("champions") or {}).items():
        photo_url = champion.get("photo_url")
        if not photo_url:
            continue
        records["media_assets"].append(
            {
                "id": stable_uuid("champion-media", tournament_id, champion_key, photo_url),
                "tournament_id": tournament_id,
                "owner_type": "legacy_champion",
                "owner_id": None,
                "storage_key": None,
                "source_url": photo_url,
                "mime_type": None,
                "width": None,
                "height": None,
                "moderation_status": "approved",
                "metadata": {
                    "legacy_champion_key": champion_key,
                    "legacy_uploaded_at": champion.get("uploaded_at"),
                },
            }
        )

    _validate_relationships(records, errors)

    import_run_id = stable_uuid(
        "legacy-import-run",
        tournament_id,
        *[f"{name}:{checksum}" for name, checksum in sorted(source_checksums.items())],
    )
    preliminary_counts = {
        table: len(rows) for table, rows in records.items() if table != "import_runs"
    }
    records["import_runs"].append(
        {
            "id": import_run_id,
            "tournament_id": tournament_id,
            "source_kind": "legacy-json-v1",
            "source_checksums": source_checksums,
            "report": {
                "counts": preliminary_counts,
                "warnings": warnings,
                "errors": errors,
            },
        }
    )

    return ImportPlan(
        tournament_id=tournament_id,
        tournament_slug=tournament_slug,
        records=records,
        source_checksums=source_checksums,
        warnings=warnings,
        errors=errors,
    )


def _validate_relationships(records, errors):
    ids = {
        table: {row["id"] for row in rows}
        for table, rows in records.items()
    }
    checks = (
        ("tournament_sports", "tournament_id", "tournaments"),
        ("tournament_sports", "sport_id", "sports"),
        ("divisions", "tournament_sport_id", "tournament_sports"),
        ("entrants", "division_id", "divisions"),
        ("entrant_members", "entrant_id", "entrants"),
        ("entrant_members", "person_id", "people"),
        ("stages", "division_id", "divisions"),
        ("groups", "stage_id", "stages"),
        ("courts", "venue_id", "venues"),
        ("matches", "division_id", "divisions"),
        ("matches", "stage_id", "stages"),
        ("match_segments", "match_id", "matches"),
        ("comments", "match_id", "matches"),
        ("legacy_reaction_totals", "match_id", "matches"),
    )
    for table, field_name, parent_table in checks:
        for row in records.get(table, []):
            value = row.get(field_name)
            if value is not None and value not in ids.get(parent_table, set()):
                errors.append(
                    {
                        "code": "broken_import_relationship",
                        "entity": row.get("id"),
                        "message": (
                            f"{table}.{field_name}={value} tidak ditemukan di {parent_table}."
                        ),
                    }
                )


def load_legacy_import_plan(data_dir):
    data_dir = Path(data_dir)
    payloads = {}
    checksums = {}
    for name in ("config.json", "teams.json", "matches.json"):
        raw = (data_dir / name).read_bytes()
        checksums[name] = sha256(raw).hexdigest()
        payloads[name] = json.loads(raw.decode("utf-8"))
    participants_path = data_dir / "participants.json"
    participants = (
        json.loads(participants_path.read_bytes().decode("utf-8"))
        if participants_path.exists() else {}
    )
    return build_import_plan(
        payloads["config.json"],
        payloads["teams.json"],
        payloads["matches.json"],
        source_checksums=checksums,
        participants=participants,
    )
