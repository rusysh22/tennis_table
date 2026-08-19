import unittest

import utils


def scoring_match(sport_key="table-tennis", profile=None):
    profiles = {
        "table-tennis": (
            "table-tennis-bo3",
            {"best_of": 3, "points_to_win": 11, "win_by": 2},
            "game",
        ),
        "badminton": (
            "badminton-21-bo3",
            {
                "best_of": 3,
                "points_to_win": 21,
                "win_by": 2,
                "point_cap": 30,
            },
            "game",
        ),
        "padel": (
            "padel-standard-advantage",
            {
                "best_of": 3,
                "games_to_win_set": 6,
                "set_win_by": 2,
                "tie_break_at": "6-6",
                "game_scoring_method": "advantage",
                "deciding_set_policy": "standard",
            },
            "set",
        ),
    }
    profile_key, profile_config, segment_term = profile or profiles[sport_key]
    return {
        "id": "S01",
        "sport_key": sport_key,
        "category": "open",
        "group": "A",
        "team_a": "A",
        "team_b": "B",
        "date": "2026-08-02",
        "time": "18:00",
        "court": "Court 1",
        "status": "scheduled",
        "sets": [],
        "winner": None,
        "walkover": False,
        "score_corrections": [],
        "scorekeeper_events": [],
        "_profile_key": profile_key,
        "_profile_version": 1,
        "_profile_config": profile_config,
        "_segment_term": segment_term,
    }


def award(match, side, count):
    for _ in range(count):
        utils.apply_scorekeeper_action(match, "point", side=side)


class ScorekeeperStateTests(unittest.TestCase):
    def test_table_tennis_start_score_undo_finish_and_correct(self):
        match = scoring_match()
        utils.apply_scorekeeper_action(match, "start")
        self.assertEqual(match["status"], "live")

        award(match, "b", 5)
        award(match, "a", 11)
        self.assertEqual(match["sets"], [[11, 5]])
        self.assertEqual(utils.scorekeeper_state(match)["current"], [0, 0])

        utils.apply_scorekeeper_action(match, "undo")
        self.assertEqual(match["sets"], [])
        self.assertEqual(utils.scorekeeper_state(match)["current"], [10, 5])
        award(match, "a", 1)

        award(match, "b", 7)
        award(match, "a", 11)
        state = utils.scorekeeper_state(match)
        self.assertTrue(state["ready_to_finish"])
        self.assertEqual(state["segments_won"], {"a": 2, "b": 0})

        utils.apply_scorekeeper_action(match, "finish")
        self.assertEqual(match["status"], "completed")
        self.assertEqual(match["winner"], "A")

        with self.assertRaisesRegex(ValueError, "Alasan koreksi"):
            utils.apply_scorekeeper_action(match, "undo")
        utils.apply_scorekeeper_action(
            match, "undo", reason="Poin terakhir salah diberikan"
        )
        self.assertEqual(match["status"], "live")
        self.assertEqual(match["sets"], [[11, 5]])
        self.assertEqual(utils.scorekeeper_state(match)["current"], [10, 7])
        self.assertEqual(match["score_corrections"][-1]["actor"], "scorekeeper")

    def test_badminton_and_padel_use_profile_specific_units(self):
        badminton = scoring_match("badminton")
        utils.apply_scorekeeper_action(badminton, "start")
        award(badminton, "b", 10)
        award(badminton, "a", 21)
        badminton_state = utils.scorekeeper_state(badminton)
        self.assertEqual(badminton["sets"], [[21, 10]])
        self.assertEqual(badminton_state["terms"]["unit_label"], "Poin")
        self.assertEqual(badminton_state["terms"]["cap"], 30)

        padel = scoring_match("padel")
        utils.apply_scorekeeper_action(padel, "start")
        award(padel, "b", 4)
        award(padel, "a", 6)
        padel_state = utils.scorekeeper_state(padel)
        self.assertEqual(padel["sets"], [[6, 4]])
        self.assertEqual(padel_state["terms"]["segment_label"], "Set")
        self.assertEqual(padel_state["terms"]["unit_label"], "Game")

    def test_completed_manual_score_can_be_opened_for_correction(self):
        match = scoring_match()
        match.update(
            status="completed",
            sets=[[11, 5], [11, 7]],
            winner="A",
        )

        utils.apply_scorekeeper_action(
            match, "open_correction", reason="Verifikasi ulang skor akhir"
        )

        self.assertEqual(match["status"], "live")
        self.assertEqual(match["sets"], [[11, 5]])
        self.assertEqual(utils.scorekeeper_state(match)["current"], [10, 7])


if __name__ == "__main__":
    unittest.main()
