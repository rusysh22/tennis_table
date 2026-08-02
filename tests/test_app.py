import json
import os
import tempfile
import unittest

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("SESSION_COOKIE_SECURE", "0")

import app as application
import utils


class ApplicationSecurityAndScoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_data_dir = utils.DATA_DIR
        utils.DATA_DIR = self.temp_dir.name
        self._write_fixture_data()

        application.app.config.update(
            TESTING=True,
            ADMIN_PASSWORD="correct-horse-battery-staple",
            ADMIN_PASSWORD_HASH=None,
            SESSION_COOKIE_SECURE=False,
            LOGIN_MAX_ATTEMPTS=5,
        )
        application._LOGIN_ATTEMPTS.clear()
        application._LOGIN_LOCKED_UNTIL.clear()
        self.client = application.app.test_client()

    def tearDown(self):
        utils.DATA_DIR = self.original_data_dir
        self.temp_dir.cleanup()

    def _write(self, name, value):
        with open(os.path.join(self.temp_dir.name, name), "w", encoding="utf-8") as output:
            json.dump(value, output)

    def _write_fixture_data(self):
        self._write(
            "teams.json",
            {
                "A": {
                    "player1": "Alpha",
                    "player2": "One",
                    "category": "ganda_putra",
                    "group": "A",
                },
                "B": {
                    "player1": "Beta",
                    "player2": "Two",
                    "category": "ganda_putra",
                    "group": "A",
                },
            },
        )
        self._write(
            "matches.json",
            [
                {
                    "id": "M01",
                    "category": "ganda_putra",
                    "category_label": "Ganda Putra",
                    "group": "A",
                    "round": 1,
                    "round_label": "Babak 1",
                    "team_a": "A",
                    "team_b": "B",
                    "date": "2026-01-01",
                    "time": "18:00",
                    "court": "Meja 1",
                    "status": "scheduled",
                    "sets": [],
                    "winner": None,
                    "walkover": False,
                    "notes": "",
                    "comments": [],
                    "votes": {"a": {}, "b": {}},
                    "reschedule_history": [],
                }
            ],
        )
        self._write(
            "config.json",
            {
                "tournament_name": "Test Tournament",
                "tournament_short_name": "Test",
                "status": "active",
                "start_date": "2026-01-01",
                "end_date": "2026-01-02",
                "buffer_dates": [],
                "final_date": "2026-01-02",
                "closing_date": "2026-01-02",
                "time_window": "18.00 - 20.00 WIB",
                "time_window_note": "Test",
                "venue": "Test Hall",
                "final_note": "",
                "categories": [
                    {
                        "key": "ganda_putra",
                        "label": "Ganda Putra",
                        "groups": ["A"],
                        "has_final": False,
                    }
                ],
                "ga_measurement_id": "",
            },
        )

    def _csrf_token(self):
        with self.client.session_transaction() as current_session:
            return current_session[application.CSRF_SESSION_KEY]

    def _login(self, next_url=None):
        self.client.get("/admin/login")
        path = "/admin/login"
        if next_url:
            path += f"?next={next_url}"
        return self.client.post(
            path,
            data={
                "password": "correct-horse-battery-staple",
                "csrf_token": self._csrf_token(),
            },
        )

    def _post_score(self, **overrides):
        data = {
            "csrf_token": self._csrf_token(),
            "version": "0",
            "action": "save_score",
            "status": "live",
            "notes": "",
            "set1_a": "11",
            "set1_b": "5",
            "set2_a": "11",
            "set2_b": "7",
        }
        data.update(overrides)
        return self.client.post("/admin/pertandingan/M01", data=data)

    def _scorekeeper_action(self, action, version, **fields):
        data = {
            "csrf_token": self._csrf_token(),
            "action": action,
            "version": str(version),
        }
        data.update(fields)
        return self.client.post("/admin/scorekeeper/M01/action", data=data)

    def test_security_headers_are_present(self):
        response = self.client.get("/")

        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
        self.assertNotIn('href="/admin/login"', response.get_data(as_text=True))

    def test_csrf_rejects_missing_token(self):
        response = self.client.post("/admin/login", data={"password": "anything"})

        self.assertEqual(response.status_code, 400)

    def test_external_next_redirect_is_rejected(self):
        response = self._login("https://evil.example/phishing")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/admin")

    def test_repeated_failed_logins_are_temporarily_locked(self):
        self.client.get("/admin/login")
        for _ in range(5):
            response = self.client.post(
                "/admin/login",
                data={"password": "wrong", "csrf_token": self._csrf_token()},
            )
            self.assertEqual(response.status_code, 200)

        locked = self.client.post(
            "/admin/login",
            data={"password": "wrong", "csrf_token": self._csrf_token()},
        )

        self.assertEqual(locked.status_code, 429)

    def test_incomplete_past_match_does_not_mark_tournament_complete(self):
        response = self.client.get("/")
        page = response.get_data(as_text=True)

        self.assertNotIn("Seluruh jadwal turnamen telah selesai", page)
        self.assertIn("1 pertandingan masih menunggu pembaruan", page)

    def test_invalid_score_is_rejected_without_mutating_match(self):
        self._login()
        response = self._post_score(set1_a="10", set1_b="8")

        self.assertEqual(response.status_code, 302)
        match = utils.load_matches()[0]
        self.assertEqual(match["sets"], [])
        self.assertNotIn("version", match)

    def test_valid_score_completes_match_and_increments_version(self):
        self._login()
        response = self._post_score()

        self.assertEqual(response.status_code, 302)
        match = utils.load_matches()[0]
        self.assertEqual(match["sets"], [[11, 5], [11, 7]])
        self.assertEqual(match["winner"], "A")
        self.assertEqual(match["status"], "completed")
        self.assertEqual(match["version"], 1)

    def test_stale_version_cannot_overwrite_newer_score(self):
        self._login()
        self._post_score()
        self._post_score(
            set1_a="5", set1_b="11", set2_a="7", set2_b="11"
        )

        match = utils.load_matches()[0]
        self.assertEqual(match["winner"], "A")
        self.assertEqual(match["version"], 1)

    def test_v1_sports_exposes_enabled_and_planned_sports(self):
        response = self.client.get("/api/v1/sports")

        self.assertEqual(response.status_code, 200)
        sports = response.get_json()["data"]
        self.assertEqual([sport["key"] for sport in sports], [
            "table-tennis", "padel", "badminton",
        ])
        self.assertTrue(sports[0]["enabled"])
        self.assertFalse(sports[1]["enabled"])

    def test_v1_matches_filters_and_returns_stable_etag(self):
        response = self.client.get(
            "/api/v1/matches?sport=table-tennis&status=scheduled&limit=1"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["meta"]["count"], 1)
        self.assertEqual(payload["data"][0]["sport"]["key"], "table-tennis")
        self.assertEqual(payload["data"][0]["id"], "M01")
        self.assertIn("ETag", response.headers)

        cached = self.client.get(
            "/api/v1/matches?sport=table-tennis&status=scheduled&limit=1",
            headers={"If-None-Match": response.headers["ETag"]},
        )
        self.assertEqual(cached.status_code, 304)

    def test_v1_matches_uses_consistent_validation_errors(self):
        response = self.client.get("/api/v1/matches?limit=101")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"]["code"], "invalid_request")
        self.assertEqual(
            response.get_json()["error"]["fields"]["limit"], "out_of_range"
        )

    def test_sport_switcher_filters_public_schedule(self):
        response = self.client.get("/jadwal?sport=table-tennis")
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Semua Cabang", page)
        self.assertIn("Table Tennis", page)
        self.assertIn("Padel", page)
        self.assertIn("1 pertandingan ditemukan", page)

    def test_live_page_polls_the_versioned_sport_aware_api(self):
        matches = utils.load_matches()
        matches[0]["status"] = "live"
        utils.save_matches(matches)
        response = self.client.get("/live?sport=table-tennis")
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("/api/v1/matches?sport=table-tennis&amp;limit=100", page)
        self.assertNotIn('data-live-api="/api/matches"', page)

    def test_stage_driven_public_views_and_event_hub_render(self):
        home = self.client.get("/").get_data(as_text=True)
        standings = self.client.get("/klasemen").get_data(as_text=True)
        bracket = self.client.get("/bracket").get_data(as_text=True)

        self.assertIn("Cabang Olahraga", home)
        self.assertIn("Badminton", home)
        self.assertIn("Segera", home)
        self.assertIn("Klasemen per Divisi dan Grup", standings)
        self.assertIn("InterSport Table Tennis Group Policy", standings)
        self.assertIn("belum memiliki stage eliminasi", bracket)

    def test_rules_are_selected_from_the_sport_profiles(self):
        response = self.client.get("/aturan?sport=padel")
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Padel Best of 3", page)
        self.assertIn("Golden Point", page)
        self.assertNotIn("Pedoman Aturan Mini Round", page)

    def test_v1_standings_filters_and_returns_stable_etag(self):
        path = (
            "/api/v1/standings?sport=table-tennis"
            "&division=ganda_putra&stage=group-stage&group=A"
        )
        response = self.client.get(path)

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["meta"]["count"], 1)
        self.assertEqual(payload["data"][0]["division"]["key"], "ganda_putra")
        self.assertEqual(payload["data"][0]["group"]["key"], "A")
        self.assertEqual(len(payload["data"][0]["rows"]), 2)
        self.assertEqual(payload["data"][0]["policy"]["version"], 1)
        self.assertIn("ETag", response.headers)

        cached = self.client.get(
            path, headers={"If-None-Match": response.headers["ETag"]}
        )
        self.assertEqual(cached.status_code, 304)

    def test_reschedule_rejects_court_and_entrant_conflicts_atomically(self):
        teams = utils.load_teams()
        teams["C"] = {
            "player1": "Gamma", "player2": "Three",
            "category": "ganda_putra", "group": "A",
        }
        self._write("teams.json", teams)
        matches = utils.load_matches()
        matches.append({
            **matches[0],
            "id": "M02",
            "team_a": "A",
            "team_b": "C",
            "date": "2026-01-02",
            "time": "19:00",
            "court": "Meja 2",
        })
        utils.save_matches(matches)
        self._login()

        response = self.client.post(
            "/admin/pertandingan/M01",
            data={
                "csrf_token": self._csrf_token(),
                "version": "0",
                "action": "reschedule",
                "new_date": "2026-01-02",
                "new_time": "19:00",
                "new_court": "Meja 2",
                "reason": "Conflict test",
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Bentrok lapangan", response.get_data(as_text=True))
        self.assertIn("Bentrok peserta", response.get_data(as_text=True))
        stored = utils.get_match(utils.load_matches(), "M01")
        self.assertEqual(
            (stored["date"], stored["time"], stored["court"]),
            ("2026-01-01", "18:00", "Meja 1"),
        )
        self.assertEqual(stored.get("reschedule_history"), [])
        self.assertNotIn("version", stored)

    def test_mobile_scorekeeper_routes_render_after_login(self):
        self._login()

        index = self.client.get("/admin/scorekeeper")
        console = self.client.get("/admin/scorekeeper/M01")

        self.assertEqual(index.status_code, 200)
        self.assertIn("Mode operasional", index.get_data(as_text=True))
        self.assertIn("M01", index.get_data(as_text=True))
        self.assertEqual(console.status_code, 200)
        self.assertIn("setiap aksi disimpan otomatis", console.get_data(as_text=True))
        self.assertIn('data-score-action="start"', console.get_data(as_text=True))
        self.assertIn("scorekeeper.js", console.get_data(as_text=True))

    def test_scorekeeper_actions_use_optimistic_lock_and_return_latest_state(self):
        self._login()
        started = self._scorekeeper_action("start", 0)

        self.assertEqual(started.status_code, 200)
        self.assertTrue(started.get_json()["ok"])
        self.assertEqual(started.get_json()["data"]["version"], 1)
        self.assertEqual(started.get_json()["data"]["match"]["status"], "live")

        stale = self._scorekeeper_action("point", 0, side="a")
        self.assertEqual(stale.status_code, 409)
        self.assertTrue(stale.get_json()["reload_required"])
        self.assertEqual(stale.get_json()["data"]["state"]["current"], [0, 0])

        scored = self._scorekeeper_action("point", 1, side="a")
        self.assertEqual(scored.status_code, 200)
        self.assertEqual(scored.get_json()["data"]["version"], 2)
        self.assertEqual(scored.get_json()["data"]["state"]["current"], [1, 0])
        stored = utils.get_match(utils.load_matches(), "M01")
        self.assertEqual(stored["version"], 2)
        self.assertEqual(len(stored["scorekeeper_events"]), 2)


if __name__ == "__main__":
    unittest.main()
