import unittest

import utils


def team(code):
    return {
        "player1": code,
        "player2": f"{code}2",
        "category": "open",
        "group": "A",
    }


def match(match_id, side_a, side_b, sets, winner, walkover=False):
    return {
        "id": match_id,
        "category": "open",
        "group": "A",
        "team_a": side_a,
        "team_b": side_b,
        "status": "completed",
        "sets": sets,
        "winner": winner,
        "walkover": walkover,
    }


class StandingsTests(unittest.TestCase):
    def test_group_without_active_matches_has_no_champion(self):
        teams = {code: team(code) for code in ("A", "B")}

        self.assertIsNone(utils.group_champion([], teams, "open", "A"))

    def test_points_are_loaded_from_the_division_policy(self):
        teams = {code: team(code) for code in ("A", "B")}
        matches = [
            match("M1", "A", "B", [[11, 8], [11, 9]], "A"),
        ]

        rows = utils.compute_standings(
            matches,
            teams,
            "open",
            "A",
            policy_config={
                "win_points": 3,
                "played_loss_points": 0,
                "walkover_loss_points": -1,
            },
        )

        self.assertEqual([(row["code"], row["points"]) for row in rows], [
            ("A", 3), ("B", 0),
        ])

    def test_invalid_completed_result_is_excluded_until_corrected(self):
        teams = {code: team(code) for code in ("A", "B")}
        matches = [
            match("M1", "A", "B", [[21, 10], [21, 11], [12, 10]], "A"),
        ]

        rows = utils.compute_standings(matches, teams, "open", "A")

        self.assertTrue(all(row["played"] == 0 for row in rows))
        self.assertFalse(utils.is_valid_completed_match(matches[0]))

    def test_two_way_tie_uses_head_to_head_before_game_difference(self):
        teams = {code: team(code) for code in ("A", "B", "C")}
        matches = [
            match("M1", "A", "B", [[11, 8], [8, 11], [11, 9]], "A"),
            match("M2", "A", "C", [[8, 11], [7, 11]], "C"),
            match("M3", "B", "C", [], "B", walkover=True),
        ]

        rows = utils.compute_standings(matches, teams, "open", "A")

        self.assertEqual([row["code"] for row in rows], ["A", "B", "C"])
        self.assertEqual(rows[0]["tie_break"], "Head-to-head")
        self.assertLess(rows[0]["set_diff"], rows[1]["set_diff"])

    def test_three_way_tie_uses_mini_table(self):
        teams = {code: team(code) for code in ("A", "B", "C")}
        matches = [
            match("M1", "A", "B", [[11, 8], [8, 11], [11, 9]], "A"),
            match("M2", "A", "C", [[8, 11], [7, 11]], "C"),
            match("M3", "B", "C", [[11, 5], [11, 6]], "B"),
        ]

        rows = utils.compute_standings(matches, teams, "open", "A")

        self.assertEqual([row["code"] for row in rows], ["B", "C", "A"])
        self.assertTrue(all(row["tie_break"] == "Mini-table head-to-head" for row in rows))


if __name__ == "__main__":
    unittest.main()
