"""Transactional writer for a validated normalized import plan."""

from psycopg2.extras import Json, execute_values

from .legacy_import import TABLE_ORDER


TABLE_COLUMNS = {
    "tournaments": (
        "id", "slug", "name", "short_name", "timezone", "locale", "status",
        "starts_on", "ends_on", "branding_profile", "source_metadata",
    ),
    "sports": ("id", "sport_key", "slug", "name", "icon"),
    "tournament_sports": (
        "id", "tournament_id", "sport_id", "enabled", "display_order", "feature_flags",
    ),
    "rule_profiles": (
        "id", "sport_id", "profile_key", "version", "name", "segment_term", "config",
    ),
    "standing_policies": ("id", "policy_key", "version", "name", "config"),
    "divisions": (
        "id", "tournament_sport_id", "division_key", "name", "entrant_type",
        "min_team_size", "max_team_size", "default_rule_profile_id",
        "standing_policy_id", "enabled", "display_order",
    ),
    "people": (
        "id", "display_name", "employee_reference", "privacy_flags", "source_metadata",
    ),
    "entrants": (
        "id", "division_id", "code", "display_name", "seed", "status", "branding",
        "source_metadata",
    ),
    "entrant_members": (
        "id", "entrant_id", "person_id", "member_role", "member_order",
    ),
    "stages": (
        "id", "division_id", "stage_key", "stage_type", "name", "sequence",
        "qualification_policy",
    ),
    "groups": ("id", "stage_id", "group_key", "name", "display_order"),
    "venues": ("id", "tournament_id", "name", "address", "timezone"),
    "courts": ("id", "venue_id", "sport_id", "court_key", "name", "enabled"),
    "matches": (
        "id", "tournament_id", "division_id", "stage_id", "group_id", "display_code",
        "round_number", "round_label", "entrant_a_id", "entrant_b_id", "court_id",
        "rule_profile_id", "scheduled_at", "status", "result_type", "winner_entrant_id",
        "result_valid", "version", "notes", "source_metadata",
    ),
    "match_segments": (
        "id", "match_id", "sequence", "segment_type", "score_a", "score_b", "status",
        "metadata",
    ),
    "comments": (
        "id", "match_id", "author_name", "body", "moderation_status", "source_metadata",
        "created_at",
    ),
    "legacy_reaction_totals": (
        "id", "match_id", "side", "reaction", "reaction_count",
    ),
    "media_assets": (
        "id", "tournament_id", "owner_type", "owner_id", "storage_key", "source_url",
        "mime_type", "width", "height", "moderation_status", "metadata",
    ),
    "announcements": (
        "id", "tournament_id", "sport_id", "title", "body", "priority", "status",
        "starts_at", "ends_at",
    ),
    "audit_logs": (
        "id", "tournament_id", "actor_user_id", "action", "entity_type", "entity_id",
        "before_data", "after_data", "reason", "request_id", "metadata",
    ),
    "import_runs": (
        "id", "tournament_id", "source_kind", "source_checksums", "report",
    ),
}

JSON_COLUMNS = {
    "branding_profile", "source_metadata", "feature_flags", "config", "privacy_flags",
    "branding", "qualification_policy", "metadata", "playback_config", "before_data",
    "after_data", "permissions", "source_checksums", "report",
}


def _adapt_value(column, value):
    if column in JSON_COLUMNS and value is not None:
        return Json(value)
    return value


def _insert_rows(cursor, table, rows):
    if not rows:
        return
    columns = TABLE_COLUMNS[table]
    values = [
        tuple(_adapt_value(column, row.get(column)) for column in columns)
        for row in rows
    ]
    column_sql = ", ".join(columns)
    update_sql = ", ".join(
        f"{column} = EXCLUDED.{column}" for column in columns if column != "id"
    )
    execute_values(
        cursor,
        (
            f"INSERT INTO intersport.{table} ({column_sql}) VALUES %s "
            f"ON CONFLICT (id) DO UPDATE SET {update_sql}"
        ),
        values,
        page_size=500,
    )


def apply_import_plan(database_url, plan, *, replace_existing=False):
    """Apply an import in one transaction.

    Existing tournament data is never overwritten unless replace_existing is
    explicitly true. Global catalog rows use deterministic IDs and are upserted.
    """
    if not database_url:
        raise ValueError("DATABASE_URL wajib diisi untuk menerapkan import plan.")
    plan.assert_valid()

    import psycopg2

    connection = psycopg2.connect(database_url)
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 FROM intersport.tournaments WHERE id = %s",
                    (plan.tournament_id,),
                )
                exists = cursor.fetchone() is not None
                if exists and not replace_existing:
                    raise RuntimeError(
                        "Tournament normalized sudah ada. Gunakan --replace hanya setelah backup dan dry-run diperiksa."
                    )
                if exists:
                    cursor.execute(
                        "DELETE FROM intersport.tournaments WHERE id = %s",
                        (plan.tournament_id,),
                    )

                for table in TABLE_ORDER:
                    _insert_rows(cursor, table, plan.records.get(table, []))
    finally:
        connection.close()
    return plan.counts
