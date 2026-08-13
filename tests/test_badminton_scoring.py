import unittest

from domain.scoring import BadmintonProfile, validate_badminton_score


class BadmintonScoringTests(unittest.TestCase):
    def test_standard_best_of_three_result(self):
        result = validate_badminton_score([[21, 17], [18, 21], [21, 15]])

        self.assertTrue(result.is_complete)
        self.assertEqual(result.winner_side, "a")

    def test_deuce_and_cap_results(self):
        deuce = validate_badminton_score([[22, 20]])
        cap = validate_badminton_score([[30, 29]])

        self.assertTrue(deuce.is_valid)
        self.assertTrue(cap.is_valid)

    def test_impossible_scores_and_scores_over_cap_are_rejected(self):
        impossible = validate_badminton_score([[30, 27]])
        over_cap = validate_badminton_score([[31, 29]])

        self.assertFalse(impossible.is_valid)
        self.assertFalse(over_cap.is_valid)

    def test_game_after_match_win_is_rejected(self):
        result = validate_badminton_score([[21, 10], [21, 12], [10, 21]])

        self.assertFalse(result.is_valid)
        self.assertIn("sudah selesai", " ".join(result.errors))

    def test_alternate_profile_is_parameterized(self):
        profile = BadmintonProfile(
            profile_key="badminton-15-bo3",
            version=2,
            points_to_win=15,
            point_cap=21,
        )

        result = validate_badminton_score([[15, 8], [17, 15]], profile)

        self.assertTrue(result.is_complete)

    def test_rubber_game_uses_sudden_victory_race_to_eleven(self):
        profile = BadmintonProfile(
            decider_points_to_win=11, decider_win_by=1, decider_point_cap=11,
        )

        result = validate_badminton_score([[21, 17], [18, 21], [11, 10]], profile)

        self.assertTrue(result.is_complete)
        self.assertEqual(result.winner_side, "a")

    def test_rubber_game_still_rejects_scores_below_eleven(self):
        profile = BadmintonProfile(
            decider_points_to_win=11, decider_win_by=1, decider_point_cap=11,
        )

        result = validate_badminton_score([[21, 17], [18, 21], [10, 9]], profile)

        self.assertFalse(result.is_complete)

    def test_games_one_and_two_keep_the_full_deuce_rule_when_decider_is_set(self):
        profile = BadmintonProfile(
            decider_points_to_win=11, decider_win_by=1, decider_point_cap=11,
        )

        # Game 2 at 11-10 is only valid for the rubber game, not game 1/2.
        result = validate_badminton_score([[11, 10]], profile)

        self.assertFalse(result.is_valid)


if __name__ == "__main__":
    unittest.main()
