"""Live normalized repository with a temporary legacy-template view adapter."""

from contextlib import contextmanager
from collections import Counter
from copy import deepcopy
from datetime import datetime
import base64
import json
import uuid
from zoneinfo import ZoneInfo

import psycopg2
from psycopg2.extras import Json, RealDictCursor, register_uuid

from domain.scoring import RuleProfile, validate_score


class NormalizedRepositoryError(RuntimeError):
    pass


class NormalizedMatchNotFound(LookupError):
    pass


class NormalizedVersionConflict(RuntimeError):
    pass


class NormalizedRepository:
    def __init__(self, database_url, tournament_slug=None):
        if not database_url:
            raise ValueError("DATABASE_URL is required for the normalized backend.")
        self.database_url = database_url
        self.tournament_slug = tournament_slug

    @contextmanager
    def connection(self):
        try:
            from flask import g, has_app_context
        except ImportError:
            has_app_context = lambda: False

        if has_app_context():
            connection = getattr(g, "_normalized_pg_conn", None)
            if connection is None or connection.closed:
                connection = psycopg2.connect(self.database_url)
                register_uuid(conn_or_curs=connection)
                g._normalized_pg_conn = connection
            yield connection
            return

        connection = psycopg2.connect(self.database_url)
        register_uuid(conn_or_curs=connection)
        try:
            yield connection
        finally:
            connection.close()

    @staticmethod
    def close_request_connection():
        try:
            from flask import g
        except ImportError:
            return
        connection = g.pop("_normalized_pg_conn", None)
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass

    def _request_cache(self):
        try:
            from flask import g, has_app_context
        except ImportError:
            return None
        if not has_app_context():
            return None
        cache = getattr(g, "_normalized_repository_cache", None)
        if cache is None:
            cache = {}
            g._normalized_repository_cache = cache
        return cache

    def _tournament(self, cursor):
        if self.tournament_slug:
            cursor.execute(
                "SELECT * FROM intersport.tournaments WHERE slug = %s",
                (self.tournament_slug,),
            )
        else:
            cursor.execute(
                """
                SELECT * FROM intersport.tournaments
                ORDER BY (status = 'active') DESC, created_at DESC
                LIMIT 2
                """
            )
        rows = cursor.fetchall()
        if not rows:
            raise NormalizedRepositoryError("No normalized tournament was found.")
        if not self.tournament_slug and len(rows) > 1:
            raise NormalizedRepositoryError(
                "Multiple normalized tournaments exist; set TOURNAMENT_SLUG explicitly."
            )
        return rows[0]

    def snapshot(self, force=False):
        cache = self._request_cache()
        if cache is not None and not force and "snapshot" in cache:
            return cache["snapshot"]
        if force:
            self.invalidate_cache()
        snapshot = {
            "config": self.load_config(),
            "teams": self.load_teams(),
            "matches": self.load_matches(),
        }
        if cache is not None:
            cache["snapshot"] = snapshot
        return snapshot

    def invalidate_cache(self):
        cache = self._request_cache()
        if cache is not None:
            cache.clear()

    def load_config(self):
        return self._load_component(
            "config", lambda cursor, tournament: self._load_config(cursor, tournament)
        )

    def load_teams(self):
        return self._load_component(
            "teams", lambda cursor, tournament: self._load_teams(
                cursor, tournament["id"]
            )
        )

    def load_matches(self):
        return self._load_component("matches", self._load_matches)

    def _load_component(self, cache_key, loader):
        cache = self._request_cache()
        if cache is not None and cache_key in cache:
            return deepcopy(cache[cache_key])
        with self.connection() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                tournament = self._tournament(cursor)
                value = loader(cursor, tournament)
            connection.commit()
        if cache is not None:
            cache[cache_key] = value
        return deepcopy(value)

    def list_sports(self):
        cache = self._request_cache()
        if cache is not None and "sports" in cache:
            return deepcopy(cache["sports"])
        with self.connection() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                tournament = self._tournament(cursor)
                cursor.execute(
                    """
                    SELECT s.sport_key AS key, s.name, s.icon, ts.enabled,
                           ts.display_order,
                           count(d.id)::int AS division_count
                    FROM intersport.tournament_sports ts
                    JOIN intersport.sports s ON s.id = ts.sport_id
                    LEFT JOIN intersport.divisions d
                      ON d.tournament_sport_id = ts.id AND d.enabled
                    WHERE ts.tournament_id = %s
                    GROUP BY s.sport_key, s.name, s.icon, ts.enabled, ts.display_order
                    ORDER BY ts.display_order
                    """,
                    (tournament["id"],),
                )
                sports = [dict(row) for row in cursor.fetchall()]
            connection.commit()
        if cache is not None:
            cache["sports"] = sports
        return deepcopy(sports)

    def load_competition_structure(self):
        return self._load_component(
            "competition_structure", self._load_competition_structure
        )

    def _load_competition_structure(self, cursor, tournament):
        cursor.execute(
            """
            SELECT d.id, d.division_key, d.name, d.entrant_type,
                   d.min_team_size, d.max_team_size, d.enabled,
                   d.display_order, s.sport_key, s.name AS sport_name,
                   s.icon AS sport_icon, ts.enabled AS sport_enabled,
                   ts.feature_flags,
                   rp.profile_key, rp.version AS profile_version,
                   rp.name AS profile_name, rp.segment_term,
                   rp.config AS profile_config,
                   sp.policy_key, sp.version AS policy_version,
                   sp.name AS policy_name, sp.config AS policy_config
            FROM intersport.divisions d
            JOIN intersport.tournament_sports ts
              ON ts.id = d.tournament_sport_id
            JOIN intersport.sports s ON s.id = ts.sport_id
            JOIN intersport.rule_profiles rp
              ON rp.id = d.default_rule_profile_id
            LEFT JOIN intersport.standing_policies sp
              ON sp.id = d.standing_policy_id
            WHERE ts.tournament_id = %s
            ORDER BY ts.display_order, d.display_order, d.division_key
            """,
            (tournament["id"],),
        )
        division_rows = cursor.fetchall()
        division_ids = [row["id"] for row in division_rows]
        stages_by_division = {}
        if division_ids:
            cursor.execute(
                """
                SELECT st.id, st.division_id, st.stage_key, st.stage_type,
                       st.name, st.sequence, st.qualification_policy,
                       g.group_key, g.name AS group_name,
                       g.display_order AS group_display_order
                FROM intersport.stages st
                LEFT JOIN intersport.groups g ON g.stage_id = st.id
                WHERE st.division_id = ANY(%s::uuid[])
                ORDER BY st.division_id, st.sequence,
                         g.display_order, g.group_key
                """,
                (division_ids,),
            )
            for row in cursor.fetchall():
                stages = stages_by_division.setdefault(row["division_id"], {})
                stage = stages.setdefault(
                    row["id"],
                    {
                        "id": str(row["id"]),
                        "key": row["stage_key"],
                        "type": row["stage_type"],
                        "name": row["name"],
                        "sequence": row["sequence"],
                        "qualification_policy": row["qualification_policy"] or {},
                        "groups": [],
                    },
                )
                if row["group_key"]:
                    stage["groups"].append(
                        {
                            "key": row["group_key"],
                            "name": row["group_name"],
                            "display_order": row["group_display_order"],
                        }
                    )

        cursor.execute(
            """
            SELECT s.sport_key, rp.profile_key, rp.version, rp.name,
                   rp.segment_term, rp.config
            FROM intersport.rule_profiles rp
            JOIN intersport.sports s ON s.id = rp.sport_id
            JOIN intersport.tournament_sports ts
              ON ts.sport_id = s.id AND ts.tournament_id = %s
            ORDER BY s.sport_key, rp.profile_key, rp.version
            """,
            (tournament["id"],),
        )
        profiles_by_sport = {}
        for row in cursor.fetchall():
            profiles_by_sport.setdefault(row["sport_key"], []).append(
                {
                    "key": row["profile_key"],
                    "version": row["version"],
                    "name": row["name"],
                    "segment_term": row["segment_term"],
                    "config": row["config"],
                }
            )

        divisions = []
        for row in division_rows:
            policy = None
            if row["policy_key"]:
                policy = {
                    "key": row["policy_key"],
                    "version": row["policy_version"],
                    "name": row["policy_name"],
                    "config": row["policy_config"],
                }
            divisions.append(
                {
                    "id": str(row["id"]),
                    "key": row["division_key"],
                    "name": row["name"],
                    "sport_key": row["sport_key"],
                    "sport_name": row["sport_name"],
                    "sport_icon": row["sport_icon"],
                    "sport_enabled": row["sport_enabled"],
                    "feature_flags": row["feature_flags"] or {},
                    "entrant_type": row["entrant_type"],
                    "min_team_size": row["min_team_size"],
                    "max_team_size": row["max_team_size"],
                    "enabled": row["enabled"],
                    "display_order": row["display_order"],
                    "standing_policy": policy,
                    "default_rule_profile": {
                        "key": row["profile_key"],
                        "version": row["profile_version"],
                        "name": row["profile_name"],
                        "segment_term": row["segment_term"],
                        "config": row["profile_config"],
                    },
                    "stages": list(
                        stages_by_division.get(row["id"], {}).values()
                    ),
                }
            )
        return {
            "tournament": {
                "slug": tournament["slug"],
                "name": tournament["name"],
                "timezone": tournament["timezone"],
            },
            "divisions": divisions,
            "rule_profiles_by_sport": profiles_by_sport,
        }

    def _load_config(self, cursor, tournament):
        source = tournament.get("source_metadata") or {}
        cursor.execute(
            """
            SELECT v.name
            FROM intersport.venues v
            WHERE v.tournament_id = %s
            ORDER BY v.created_at
            LIMIT 1
            """,
            (tournament["id"],),
        )
        venue_row = cursor.fetchone()
        cursor.execute(
            """
            SELECT a.title, a.body
            FROM intersport.announcements a
            WHERE a.tournament_id = %s AND a.status = 'published'
              AND (a.starts_at IS NULL OR a.starts_at <= now())
              AND (a.ends_at IS NULL OR a.ends_at >= now())
            ORDER BY a.priority DESC, a.created_at DESC
            LIMIT 1
            """,
            (tournament["id"],),
        )
        announcement = cursor.fetchone() or {}
        cursor.execute(
            """
            SELECT d.division_key, d.name, s.sport_key, d.display_order,
                   bool_or(st.stage_type = 'final') AS has_final,
                   COALESCE(
                     jsonb_agg(DISTINCT g.group_key) FILTER (WHERE g.id IS NOT NULL),
                     '[]'::jsonb
                   ) AS groups
            FROM intersport.divisions d
            JOIN intersport.tournament_sports ts ON ts.id = d.tournament_sport_id
            JOIN intersport.sports s ON s.id = ts.sport_id
            LEFT JOIN intersport.stages st ON st.division_id = d.id
            LEFT JOIN intersport.groups g ON g.stage_id = st.id
            WHERE ts.tournament_id = %s AND d.enabled
            GROUP BY d.id, s.sport_key
            ORDER BY d.display_order
            """,
            (tournament["id"],),
        )
        categories = []
        for row in cursor.fetchall():
            groups = sorted(row.get("groups") or [])
            categories.append(
                {
                    "key": row["division_key"],
                    "label": row["name"],
                    "groups": groups,
                    "has_final": bool(row["has_final"]),
                    "sport_key": row["sport_key"],
                }
            )
        cursor.execute(
            """
            SELECT source_url, metadata
            FROM intersport.media_assets
            WHERE tournament_id = %s
              AND owner_type = 'legacy_champion'
              AND moderation_status <> 'deleted'
            """,
            (tournament["id"],),
        )
        champions = {}
        for row in cursor.fetchall():
            metadata = row.get("metadata") or {}
            key = metadata.get("legacy_champion_key")
            if key:
                champions[key] = {
                    "photo_url": row["source_url"],
                    "uploaded_at": metadata.get("legacy_uploaded_at", ""),
                }
        return {
            "tournament_name": tournament["name"],
            "tournament_short_name": tournament["short_name"],
            "status": tournament["status"],
            "timezone": tournament["timezone"],
            "locale": tournament["locale"],
            "start_date": tournament["starts_on"].isoformat(),
            "end_date": tournament["ends_on"].isoformat(),
            "buffer_dates": source.get("legacy_buffer_dates", []),
            "final_date": source.get("legacy_final_date"),
            "closing_date": source.get("legacy_closing_date"),
            "time_window": source.get("legacy_time_window", ""),
            "time_window_note": source.get("legacy_time_window_note", ""),
            "venue": venue_row["name"] if venue_row else "",
            "final_note": source.get("legacy_final_note", ""),
            "ga_measurement_id": source.get("ga_measurement_id", ""),
            "categories": categories,
            "announcement_title": announcement.get("title", ""),
            "announcement_text": announcement.get("body", ""),
            "champions": champions,
        }

    def _load_teams(self, cursor, tournament_id):
        cursor.execute(
            """
            SELECT e.id, e.code, e.branding, e.source_metadata,
                   d.division_key, s.sport_key,
                   COALESCE(
                     jsonb_agg(
                       jsonb_build_object('name', p.display_name, 'member_order', em.member_order)
                       ORDER BY em.member_order
                     ) FILTER (WHERE p.id IS NOT NULL),
                     '[]'::jsonb
                   ) AS members
            FROM intersport.entrants e
            JOIN intersport.divisions d ON d.id = e.division_id
            JOIN intersport.tournament_sports ts ON ts.id = d.tournament_sport_id
            JOIN intersport.sports s ON s.id = ts.sport_id
            LEFT JOIN intersport.entrant_members em ON em.entrant_id = e.id
            LEFT JOIN intersport.people p ON p.id = em.person_id
            WHERE ts.tournament_id = %s
            GROUP BY e.id, d.division_key, d.display_order, s.sport_key
            ORDER BY d.display_order, e.seed NULLS LAST, e.code
            """,
            (tournament_id,),
        )
        rows = cursor.fetchall()
        code_counts = Counter(row["code"] for row in rows)
        teams = {}
        for row in rows:
            adapter_key = row["code"]
            if code_counts[row["code"]] > 1:
                adapter_key = (
                    f"{row['sport_key']}:{row['division_key']}:{row['code']}"
                )
            members = row.get("members") or []
            branding = row.get("branding") or {}
            source = row.get("source_metadata") or {}
            teams[adapter_key] = {
                "code": row["code"],
                "category": row["division_key"],
                "group": source.get("legacy_group", ""),
                "player1": members[0]["name"] if members else "",
                "player2": members[1]["name"] if len(members) > 1 else "",
                "color": branding.get("background_color", "#9c9c9c"),
                "text": branding.get("text_color", "#ffffff"),
                "sport_key": row["sport_key"],
                "_normalized_id": str(row["id"]),
            }
        return teams

    def _match_base_rows(
        self, cursor, tournament_id, display_code=None, match_ids=None,
        for_update=False,
    ):
        conditions = ["m.tournament_id = %s"]
        parameters = [tournament_id]
        if display_code is not None:
            conditions.append("m.display_code = %s")
            parameters.append(display_code)
        if match_ids is not None:
            conditions.append("m.id = ANY(%s::uuid[])")
            parameters.append(match_ids)
        lock = " FOR UPDATE OF m" if for_update else ""
        cursor.execute(
            f"""
            SELECT m.*, d.division_key, d.name AS division_name,
                   s.id AS sport_id, s.sport_key, st.stage_key,
                   st.stage_type, st.name AS stage_name,
                   g.group_key, ea.code AS team_a_code, eb.code AS team_b_code,
                   ew.code AS winner_code, c.name AS court_name,
                   rp.profile_key, rp.version AS profile_version,
                   rp.config AS profile_config, rp.segment_term
            FROM intersport.matches m
            JOIN intersport.divisions d ON d.id = m.division_id
            JOIN intersport.tournament_sports ts ON ts.id = d.tournament_sport_id
            JOIN intersport.sports s ON s.id = ts.sport_id
            JOIN intersport.stages st ON st.id = m.stage_id
            LEFT JOIN intersport.groups g ON g.id = m.group_id
            LEFT JOIN intersport.entrants ea ON ea.id = m.entrant_a_id
            LEFT JOIN intersport.entrants eb ON eb.id = m.entrant_b_id
            LEFT JOIN intersport.entrants ew ON ew.id = m.winner_entrant_id
            LEFT JOIN intersport.courts c ON c.id = m.court_id
            JOIN intersport.rule_profiles rp ON rp.id = m.rule_profile_id
            WHERE {' AND '.join(conditions)}
            ORDER BY m.scheduled_at NULLS LAST, m.display_code
            {lock}
            """,
            parameters,
        )
        return cursor.fetchall()

    def _load_matches(
        self, cursor, tournament, display_code=None, match_ids=None,
        for_update=False,
    ):
        base_rows = self._match_base_rows(
            cursor, tournament["id"], display_code=display_code,
            match_ids=match_ids, for_update=for_update,
        )
        if not base_rows:
            return []
        match_ids = [row["id"] for row in base_rows]
        attachments = self._load_match_attachments(cursor, match_ids)
        event_timezone = ZoneInfo(tournament["timezone"])
        # Count against the whole tournament, not only the current API page.
        cursor.execute(
            """
            SELECT e.code, count(*)::int AS code_count
            FROM intersport.entrants e
            JOIN intersport.divisions d ON d.id = e.division_id
            JOIN intersport.tournament_sports ts ON ts.id = d.tournament_sport_id
            WHERE ts.tournament_id = %s
            GROUP BY e.code
            """,
            (tournament["id"],),
        )
        code_counts = {row["code"]: row["code_count"] for row in cursor.fetchall()}

        def entrant_key(row, field):
            code = row.get(field)
            if not code or code_counts.get(code, 0) < 2:
                return code
            return f"{row['sport_key']}:{row['division_key']}:{code}"

        matches = []
        for row in base_rows:
            scheduled = row["scheduled_at"]
            if scheduled:
                scheduled = scheduled.astimezone(event_timezone)
            match_id = row["id"]
            source = row.get("source_metadata") or {}
            segments = attachments["segments"].get(match_id, [])
            group_key = "FINAL" if row["stage_type"] == "final" else row["group_key"]
            matches.append(
                {
                    "id": row["display_code"],
                    "category": row["division_key"],
                    "category_label": row["division_name"],
                    "sport_key": row["sport_key"],
                    "group": group_key,
                    "stage_type": row["stage_type"],
                    "stage_key": row["stage_key"],
                    "stage_label": row["stage_name"],
                    "round": row["round_number"],
                    "round_label": row["round_label"] or row["stage_name"],
                    "team_a": entrant_key(row, "team_a_code"),
                    "team_b": entrant_key(row, "team_b_code"),
                    "date": scheduled.strftime("%Y-%m-%d") if scheduled else "",
                    "time": scheduled.strftime("%H:%M") if scheduled else "",
                    "court": row["court_name"] or "",
                    "status": row["status"],
                    "sets": [[item["score_a"], item["score_b"]] for item in segments],
                    "winner": entrant_key(row, "winner_code"),
                    "walkover": row["result_type"] == "walkover",
                    "notes": row["notes"],
                    "version": row["version"],
                    "comments": attachments["comments"].get(match_id, []),
                    "votes": attachments["votes"].get(match_id, {"a": {}, "b": {}}),
                    "docs": attachments["docs"].get(match_id, []),
                    "reschedule_history": attachments["reschedules"].get(match_id, []),
                    "score_corrections": attachments["corrections"].get(match_id, []),
                    "scorekeeper_events": attachments["score_events"].get(match_id, []),
                    "_normalized_id": str(match_id),
                    "_division_id": str(row["division_id"]),
                    "_stage_id": str(row["stage_id"]),
                    "_sport_id": str(row["sport_id"]) if row.get("sport_id") else None,
                    "_rule_profile_id": str(row["rule_profile_id"]),
                    "_profile_key": row["profile_key"],
                    "_profile_version": row["profile_version"],
                    "_profile_config": row["profile_config"],
                    "_segment_term": row["segment_term"],
                    "_timezone": tournament["timezone"],
                    "_result_valid": row["result_valid"],
                    "_source_metadata": source,
                }
            )
        return matches

    def list_api_matches(
        self, *, sport=None, division=None, status=None, match_date=None,
        limit=25, cursor_value=None,
    ):
        """Return one stable, cursor-paginated page of normalized matches."""
        conditions = ["m.tournament_id = %s"]
        parameters = []
        with self.connection() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                tournament = self._tournament(cursor)
                parameters.append(tournament["id"])
                if sport:
                    conditions.append("s.sport_key = %s")
                    parameters.append(sport)
                if division:
                    conditions.append("d.division_key = %s")
                    parameters.append(division)
                if status:
                    conditions.append("m.status = %s")
                    parameters.append(status)
                if match_date:
                    conditions.append(
                        "(m.scheduled_at AT TIME ZONE t.timezone)::date = %s::date"
                    )
                    parameters.append(match_date)
                if cursor_value:
                    scheduled_at, match_id = self.decode_cursor(cursor_value)
                    conditions.append(
                        "(COALESCE(m.scheduled_at, 'infinity'::timestamptz), m.id) "
                        "> (COALESCE(%s::timestamptz, 'infinity'::timestamptz), %s)"
                    )
                    parameters.extend((scheduled_at, match_id))
                parameters.append(limit + 1)
                cursor.execute(
                    f"""
                    SELECT m.id, m.scheduled_at
                    FROM intersport.matches m
                    JOIN intersport.tournaments t ON t.id = m.tournament_id
                    JOIN intersport.divisions d ON d.id = m.division_id
                    JOIN intersport.tournament_sports ts
                      ON ts.id = d.tournament_sport_id
                    JOIN intersport.sports s ON s.id = ts.sport_id
                    WHERE {' AND '.join(conditions)}
                    ORDER BY COALESCE(m.scheduled_at, 'infinity'::timestamptz), m.id
                    LIMIT %s
                    """,
                    parameters,
                )
                page_rows = cursor.fetchall()
                has_more = len(page_rows) > limit
                visible_rows = page_rows[:limit]
                ids = [row["id"] for row in visible_rows]
                matches = self._load_matches(
                    cursor, tournament, match_ids=ids
                ) if ids else []
            connection.commit()

        by_id = {item["_normalized_id"]: item for item in matches}
        ordered = [by_id[str(match_id)] for match_id in ids]
        next_cursor = None
        if has_more and visible_rows:
            last = visible_rows[-1]
            scheduled = last["scheduled_at"]
            next_cursor = self.encode_cursor(
                scheduled.isoformat() if scheduled else None, last["id"]
            )
        return ordered, next_cursor

    def get_api_match(self, display_code):
        with self.connection() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                tournament = self._tournament(cursor)
                matches = self._load_matches(
                    cursor, tournament, display_code=display_code
                )
            connection.commit()
        return matches[0] if matches else None

    def _load_match_attachments(self, cursor, match_ids):
        result = {
            "segments": {}, "comments": {}, "votes": {}, "docs": {},
            "reschedules": {}, "corrections": {}, "score_events": {},
        }
        cursor.execute(
            """
            SELECT * FROM intersport.match_segments
            WHERE match_id = ANY(%s::uuid[]) ORDER BY match_id, sequence
            """,
            (match_ids,),
        )
        for row in cursor.fetchall():
            result["segments"].setdefault(row["match_id"], []).append(row)
        cursor.execute(
            """
            SELECT * FROM intersport.score_events
            WHERE match_id = ANY(%s::uuid[])
            ORDER BY match_id, sequence
            """,
            (match_ids,),
        )
        for row in cursor.fetchall():
            result["score_events"].setdefault(row["match_id"], []).append(
                {
                    "id": str(row["id"]),
                    "sequence": int(row["sequence"]),
                    "event_type": row["event_type"],
                    "side": row["side"],
                    "value": row["value"],
                    "reversal_of": (
                        str(row["reversal_of_id"])
                        if row.get("reversal_of_id") else None
                    ),
                    "metadata": row.get("metadata") or {},
                    "at": row["occurred_at"].isoformat(timespec="seconds"),
                    "_persisted": True,
                }
            )
        cursor.execute(
            """
            SELECT * FROM intersport.comments
            WHERE match_id = ANY(%s::uuid[])
              AND moderation_status NOT IN ('hidden', 'deleted')
            ORDER BY created_at
            """,
            (match_ids,),
        )
        for row in cursor.fetchall():
            result["comments"].setdefault(row["match_id"], []).append(
                {
                    "name": row["author_name"],
                    "comment": row["body"],
                    "at": row["created_at"].isoformat(timespec="seconds"),
                    "_id": str(row["id"]),
                    "_moderation_status": row["moderation_status"],
                }
            )
        cursor.execute(
            """
            SELECT match_id, side, reaction, sum(reaction_count)::int AS reaction_count
            FROM intersport.legacy_reaction_totals
            WHERE match_id = ANY(%s::uuid[])
            GROUP BY match_id, side, reaction
            UNION ALL
            SELECT match_id, side, reaction, count(*)::int
            FROM intersport.reactions
            WHERE match_id = ANY(%s::uuid[])
            GROUP BY match_id, side, reaction
            """,
            (match_ids, match_ids),
        )
        for row in cursor.fetchall():
            votes = result["votes"].setdefault(row["match_id"], {"a": {}, "b": {}})
            votes[row["side"]][row["reaction"]] = (
                votes[row["side"]].get(row["reaction"], 0) + row["reaction_count"]
            )
        cursor.execute(
            """
            SELECT * FROM intersport.media_assets
            WHERE owner_type = 'match' AND owner_id = ANY(%s::uuid[])
              AND moderation_status NOT IN ('hidden', 'deleted')
            ORDER BY created_at
            """,
            (match_ids,),
        )
        for row in cursor.fetchall():
            result["docs"].setdefault(row["owner_id"], []).append(
                {
                    "url": row["source_url"],
                    "uploaded_at": (row.get("metadata") or {}).get(
                        "legacy_uploaded_at", row["created_at"].isoformat(timespec="seconds")
                    ),
                    "_id": str(row["id"]),
                }
            )
        cursor.execute(
            """
            SELECT * FROM intersport.audit_logs
            WHERE entity_type = 'match' AND entity_id = ANY(%s::uuid[])
              AND action IN ('match.rescheduled', 'match.rescheduled.imported', 'match.score.corrected')
            ORDER BY created_at
            """,
            (match_ids,),
        )
        for row in cursor.fetchall():
            if row["action"].startswith("match.rescheduled"):
                before = row.get("before_data") or {}
                after = row.get("after_data") or {}
                result["reschedules"].setdefault(row["entity_id"], []).append(
                    {
                        "from_date": before.get("date"),
                        "from_time": before.get("time"),
                        "from_court": before.get("court"),
                        "to_date": after.get("date"),
                        "to_time": after.get("time"),
                        "to_court": after.get("court"),
                        "reason": row.get("reason", ""),
                        "at": (row.get("metadata") or {}).get(
                            "legacy_at", row["created_at"].isoformat(timespec="seconds")
                        ),
                        "_id": str(row["id"]),
                    }
                )
            elif row["action"] == "match.score.corrected":
                result["corrections"].setdefault(row["entity_id"], []).append(
                    {
                        "before": (row.get("before_data") or {}).get("sets", []),
                        "after": (row.get("after_data") or {}).get("sets", []),
                        "reason": row.get("reason", ""),
                        "actor": "admin",
                        "at": row["created_at"].isoformat(timespec="seconds"),
                        "_id": str(row["id"]),
                    }
                )
        return result

    def update_match(self, display_code, updater, expected_version=None):
        with self.connection() as connection:
            try:
                with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                    tournament = self._tournament(cursor)
                    loaded = self._load_matches(
                        cursor, tournament, display_code=display_code, for_update=True
                    )
                    if not loaded:
                        raise NormalizedMatchNotFound(display_code)
                    current = loaded[0]
                    current_version = int(current.get("version", 0))
                    if expected_version is not None and current_version != expected_version:
                        raise NormalizedVersionConflict(
                            f"Match {display_code} changed from version {expected_version} "
                            f"to {current_version}."
                        )
                    before = deepcopy(current)
                    updater(current)
                    core_changed = self._core_match_changed(before, current)
                    self._persist_match_changes(
                        cursor, tournament, before, current, increment_version=core_changed
                    )
                    current["version"] = current_version + (1 if core_changed else 0)
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        self.invalidate_cache()
        return current

    @staticmethod
    def _core_match_changed(before, after):
        fields = (
            "team_a", "team_b", "date", "time", "court", "status", "sets",
            "winner", "walkover", "notes", "docs", "reschedule_history",
            "score_corrections", "scorekeeper_events",
        )
        return any(before.get(field) != after.get(field) for field in fields)

    def _persist_match_changes(self, cursor, tournament, before, after, increment_version):
        match_uuid = uuid.UUID(after["_normalized_id"])
        division_uuid = uuid.UUID(after["_division_id"])
        if not increment_version:
            self._persist_new_comments(
                cursor, match_uuid, after, tournament["timezone"]
            )
            self._persist_votes(cursor, match_uuid, after)
            return

        entrant_ids = {}
        for side in ("team_a", "team_b", "winner"):
            code = after.get(side)
            if not code:
                entrant_ids[side] = None
                continue
            adapter_prefix = f"{after['sport_key']}:{after['category']}:"
            stored_code = (
                code[len(adapter_prefix):]
                if code.startswith(adapter_prefix)
                else code
            )
            cursor.execute(
                "SELECT id FROM intersport.entrants WHERE division_id = %s AND code = %s",
                (division_uuid, stored_code),
            )
            row = cursor.fetchone()
            if not row:
                raise NormalizedRepositoryError(
                    f"Entrant {code!r} does not belong to this match division."
                )
            entrant_ids[side] = row["id"]
        court_id = None
        if after.get("court"):
            cursor.execute(
                """
                SELECT c.id
                FROM intersport.courts c
                JOIN intersport.venues v ON v.id = c.venue_id
                WHERE v.tournament_id = %s AND c.sport_id = %s AND c.name = %s
                LIMIT 1
                """,
                (
                    tournament["id"], uuid.UUID(after["_sport_id"]),
                    after["court"],
                ),
            )
            row = cursor.fetchone()
            if not row:
                raise NormalizedRepositoryError(f"Court {after['court']!r} was not found.")
            court_id = row["id"]
        scheduled_at = None
        if after.get("date") and after.get("time"):
            scheduled_at = datetime.strptime(
                f"{after['date']} {after['time']}", "%Y-%m-%d %H:%M"
            ).replace(tzinfo=ZoneInfo(tournament["timezone"]))

        schedule_changed = any(
            before.get(field) != after.get(field)
            for field in ("date", "time", "court", "team_a", "team_b")
        ) or (
            before.get("status") == "cancelled"
            and after.get("status") != "cancelled"
        )
        if schedule_changed and after.get("status") != "cancelled" and scheduled_at:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (str(tournament["id"]),),
            )
            entrant_list = [
                entrant_id for entrant_id in (
                    entrant_ids["team_a"], entrant_ids["team_b"]
                ) if entrant_id
            ]
            cursor.execute(
                """
                SELECT display_code,
                       (court_id = %s) AS court_conflict,
                       (ARRAY[entrant_a_id, entrant_b_id] && %s::uuid[])
                         AS entrant_conflict
                FROM intersport.matches
                WHERE tournament_id = %s AND id <> %s
                  AND status <> 'cancelled' AND scheduled_at = %s
                  AND (
                    (%s IS NOT NULL AND court_id = %s)
                    OR ARRAY[entrant_a_id, entrant_b_id] && %s::uuid[]
                  )
                ORDER BY display_code
                """,
                (
                    court_id, entrant_list, tournament["id"], match_uuid,
                    scheduled_at, court_id, court_id, entrant_list,
                ),
            )
            conflict_messages = []
            for row in cursor.fetchall():
                reasons = []
                if row["court_conflict"]:
                    reasons.append("lapangan")
                if row["entrant_conflict"]:
                    reasons.append("peserta")
                conflict_messages.append(
                    f"{row['display_code']} ({' dan '.join(reasons)})"
                )
            if conflict_messages:
                raise NormalizedRepositoryError(
                    "Jadwal bentrok dengan " + ", ".join(conflict_messages) + "."
                )

        result_type = "walkover" if after.get("walkover") else "normal"
        result_valid = self._validate_persisted_result(after)
        version_expression = "version + 1" if increment_version else "version"
        cursor.execute(
            f"""
            UPDATE intersport.matches
            SET entrant_a_id = %s, entrant_b_id = %s, court_id = %s,
                scheduled_at = %s, status = %s, result_type = %s,
                winner_entrant_id = %s, result_valid = %s, notes = %s,
                version = {version_expression}, updated_at = now()
            WHERE id = %s
            """,
            (
                entrant_ids["team_a"], entrant_ids["team_b"], court_id,
                scheduled_at, after["status"], result_type, entrant_ids["winner"],
                result_valid, after.get("notes", ""), match_uuid,
            ),
        )

        if before.get("sets") != after.get("sets"):
            cursor.execute(
                "DELETE FROM intersport.match_segments WHERE match_id = %s",
                (match_uuid,),
            )
            for sequence, scores in enumerate(after.get("sets") or [], start=1):
                cursor.execute(
                    """
                    INSERT INTO intersport.match_segments
                      (id, match_id, sequence, segment_type, score_a, score_b, status, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, 'completed', '{}'::jsonb)
                    """,
                    (
                        uuid.uuid4(), match_uuid, sequence, after.get("_segment_term", "game"),
                        scores[0], scores[1],
                    ),
                )

        self._persist_new_comments(
            cursor, match_uuid, after, tournament["timezone"]
        )
        self._persist_votes(cursor, match_uuid, after)
        self._persist_docs(cursor, tournament["id"], match_uuid, after)
        self._persist_score_events(cursor, match_uuid, before, after)
        self._persist_new_audits(cursor, tournament["id"], match_uuid, before, after)

    @staticmethod
    def _validate_persisted_result(match):
        profile = RuleProfile(
            sport_key=match["sport_key"],
            profile_key=match["_profile_key"],
            version=int(match["_profile_version"]),
            config=match["_profile_config"],
        )
        validation = validate_score(profile, match.get("sets") or [])
        if not validation.is_valid:
            # A quarantined legacy record may deliberately retain its original
            # invalid segment data until an administrator corrects it.
            if match.get("status") == "suspended":
                return False
            raise NormalizedRepositoryError(" ".join(validation.errors))
        if match.get("status") == "completed":
            if match.get("walkover"):
                if match.get("winner") not in (match.get("team_a"), match.get("team_b")):
                    raise NormalizedRepositoryError("A walkover requires a valid winner.")
            else:
                if not validation.is_complete:
                    raise NormalizedRepositoryError("A completed match requires a valid final score.")
                expected = match.get("team_a") if validation.winner_side == "a" else match.get("team_b")
                if match.get("winner") != expected:
                    raise NormalizedRepositoryError("Stored winner does not match the validated score.")
        return True

    @staticmethod
    def _persist_new_comments(cursor, match_uuid, after, timezone_name):
        for comment in after.get("comments") or []:
            if comment.get("_id"):
                continue
            created_at = comment.get("at") or datetime.now(
                tz=ZoneInfo(timezone_name)
            ).isoformat()
            cursor.execute(
                """
                INSERT INTO intersport.comments
                  (id, match_id, author_name, body, moderation_status, source_metadata, created_at)
                VALUES (%s, %s, %s, %s, 'pending', '{}'::jsonb, %s)
                """,
                (uuid.uuid4(), match_uuid, comment["name"], comment["comment"], created_at),
            )

    @staticmethod
    def _persist_votes(cursor, match_uuid, match):
        cursor.execute(
            """
            SELECT side, reaction, count(*)::int AS reaction_count
            FROM intersport.reactions
            WHERE match_id = %s
            GROUP BY side, reaction
            """,
            (match_uuid,),
        )
        actor_counts = {
            (row["side"], row["reaction"]): row["reaction_count"]
            for row in cursor.fetchall()
        }
        for side in ("a", "b"):
            for reaction, count in (match.get("votes", {}).get(side, {}) or {}).items():
                legacy_count = max(
                    int(count) - actor_counts.get((side, reaction), 0), 0
                )
                reaction_id = uuid.uuid5(
                    uuid.UUID("de19a263-e3df-4e0a-b6a2-00a3ad143b56"),
                    f"live-reaction/{match_uuid}/{side}/{reaction}",
                )
                cursor.execute(
                    """
                    INSERT INTO intersport.legacy_reaction_totals
                      (id, match_id, side, reaction, reaction_count)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (match_id, side, reaction)
                    DO UPDATE SET reaction_count = EXCLUDED.reaction_count
                    """,
                    (reaction_id, match_uuid, side, reaction, legacy_count),
                )

    @staticmethod
    def _persist_docs(cursor, tournament_id, match_uuid, match):
        desired_ids = {
            uuid.UUID(document["_id"])
            for document in match.get("docs") or []
            if document.get("_id")
        }
        if desired_ids:
            cursor.execute(
                """
                DELETE FROM intersport.media_assets
                WHERE owner_type = 'match' AND owner_id = %s AND NOT (id = ANY(%s::uuid[]))
                """,
                (match_uuid, list(desired_ids)),
            )
        else:
            cursor.execute(
                "DELETE FROM intersport.media_assets WHERE owner_type = 'match' AND owner_id = %s",
                (match_uuid,),
            )
        for document in match.get("docs") or []:
            if document.get("_id"):
                cursor.execute(
                    """
                    UPDATE intersport.media_assets
                    SET source_url = %s, metadata = %s
                    WHERE id = %s AND tournament_id = %s
                      AND owner_type = 'match' AND owner_id = %s
                    """,
                    (
                        document["url"],
                        Json({"legacy_uploaded_at": document.get("uploaded_at")}),
                        uuid.UUID(document["_id"]), tournament_id, match_uuid,
                    ),
                )
                continue
            cursor.execute(
                """
                INSERT INTO intersport.media_assets
                  (id, tournament_id, owner_type, owner_id, source_url,
                   moderation_status, metadata)
                VALUES (%s, %s, 'match', %s, %s, 'approved', %s)
                """,
                (
                    uuid.uuid4(), tournament_id, match_uuid, document["url"],
                    Json({"legacy_uploaded_at": document.get("uploaded_at")}),
                ),
            )

    @staticmethod
    def _persist_score_events(cursor, match_uuid, before, after):
        existing_ids = {
            event.get("id") for event in before.get("scorekeeper_events") or []
            if event.get("id")
        }
        for event in after.get("scorekeeper_events") or []:
            event_id = event.get("id")
            if not event_id or event_id in existing_ids:
                continue
            reversal_of = event.get("reversal_of")
            cursor.execute(
                """
                INSERT INTO intersport.score_events
                  (id, match_id, sequence, event_type, side, value,
                   idempotency_key, reversal_of_id, metadata, occurred_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    uuid.UUID(event_id), match_uuid, int(event["sequence"]),
                    event["event_type"], event.get("side"), event.get("value"),
                    event.get("idempotency_key") or f"scorekeeper:{event_id}",
                    uuid.UUID(reversal_of) if reversal_of else None,
                    Json(event.get("metadata") or {}), event.get("at") or datetime.now(
                        tz=ZoneInfo("UTC")
                    ),
                ),
            )

    @staticmethod
    def _persist_new_audits(cursor, tournament_id, match_uuid, before, after):
        existing_reschedules = {item.get("_id") for item in before.get("reschedule_history") or []}
        for change in after.get("reschedule_history") or []:
            if change.get("_id") in existing_reschedules:
                continue
            cursor.execute(
                """
                INSERT INTO intersport.audit_logs
                  (id, tournament_id, action, entity_type, entity_id,
                   before_data, after_data, reason, metadata)
                VALUES (%s, %s, 'match.rescheduled', 'match', %s, %s, %s, %s, %s)
                """,
                (
                    uuid.uuid4(), tournament_id, match_uuid,
                    Json({
                        "date": change.get("from_date"), "time": change.get("from_time"),
                        "court": change.get("from_court"),
                    }),
                    Json({
                        "date": change.get("to_date"), "time": change.get("to_time"),
                        "court": change.get("to_court"),
                    }),
                    change.get("reason"), Json({"legacy_at": change.get("at")}),
                ),
            )
        existing_corrections = {item.get("_id") for item in before.get("score_corrections") or []}
        for correction in after.get("score_corrections") or []:
            if correction.get("_id") in existing_corrections:
                continue
            cursor.execute(
                """
                INSERT INTO intersport.audit_logs
                  (id, tournament_id, action, entity_type, entity_id,
                   before_data, after_data, reason, metadata)
                VALUES (%s, %s, 'match.score.corrected', 'match', %s, %s, %s, %s, %s)
                """,
                (
                    uuid.uuid4(), tournament_id, match_uuid,
                    Json({"sets": correction.get("before", [])}),
                    Json({"sets": correction.get("after", [])}),
                    correction.get("reason"), Json({"legacy_at": correction.get("at")}),
                ),
            )
        core_fields = ("status", "winner", "sets", "date", "time", "court", "team_a", "team_b")
        changed = {
            field: {"before": before.get(field), "after": after.get(field)}
            for field in core_fields if before.get(field) != after.get(field)
        }
        if changed:
            cursor.execute(
                """
                INSERT INTO intersport.audit_logs
                  (id, tournament_id, action, entity_type, entity_id, before_data, after_data, metadata)
                VALUES (%s, %s, 'match.updated', 'match', %s, %s, %s, '{}'::jsonb)
                """,
                (
                    uuid.uuid4(), tournament_id, match_uuid,
                    Json({key: value["before"] for key, value in changed.items()}),
                    Json({key: value["after"] for key, value in changed.items()}),
                ),
            )

    def update_announcement(self, title, body):
        with self.connection() as connection:
            try:
                with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                    tournament = self._tournament(cursor)
                    cursor.execute(
                        """
                        SELECT id FROM intersport.announcements
                        WHERE tournament_id = %s AND sport_id IS NULL
                        ORDER BY created_at DESC LIMIT 1
                        FOR UPDATE
                        """,
                        (tournament["id"],),
                    )
                    row = cursor.fetchone()
                    status = "published" if title or body else "cancelled"
                    if row:
                        cursor.execute(
                            """
                            UPDATE intersport.announcements
                            SET title = %s, body = %s, status = %s
                            WHERE id = %s
                            """,
                            (title or "Pengumuman", body, status, row["id"]),
                        )
                    else:
                        cursor.execute(
                            """
                            INSERT INTO intersport.announcements
                              (id, tournament_id, title, body, status)
                            VALUES (%s, %s, %s, %s, %s)
                            """,
                            (uuid.uuid4(), tournament["id"], title or "Pengumuman", body, status),
                        )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        self.invalidate_cache()

    def set_champion_photo(self, champion_key, photo_url=None, uploaded_at=None):
        with self.connection() as connection:
            try:
                with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                    tournament = self._tournament(cursor)
                    cursor.execute(
                        """
                        DELETE FROM intersport.media_assets
                        WHERE tournament_id = %s AND owner_type = 'legacy_champion'
                          AND metadata->>'legacy_champion_key' = %s
                        """,
                        (tournament["id"], champion_key),
                    )
                    if photo_url:
                        cursor.execute(
                            """
                            INSERT INTO intersport.media_assets
                              (id, tournament_id, owner_type, source_url,
                               moderation_status, metadata)
                            VALUES (%s, %s, 'legacy_champion', %s, 'approved', %s)
                            """,
                            (
                                uuid.uuid4(), tournament["id"], photo_url,
                                Json({
                                    "legacy_champion_key": champion_key,
                                    "legacy_uploaded_at": uploaded_at,
                                }),
                            ),
                        )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        self.invalidate_cache()

    @staticmethod
    def encode_cursor(scheduled_at, match_id):
        payload = json.dumps([scheduled_at, str(match_id)], separators=(",", ":"))
        return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")

    @staticmethod
    def decode_cursor(value):
        try:
            padded = value + "=" * (-len(value) % 4)
            scheduled_at, match_id = json.loads(
                base64.urlsafe_b64decode(padded.encode()).decode()
            )
            if scheduled_at is not None:
                datetime.fromisoformat(scheduled_at)
            return scheduled_at, uuid.UUID(match_id)
        except Exception as exc:
            raise ValueError("Invalid pagination cursor.") from exc
