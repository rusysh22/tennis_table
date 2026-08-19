import unittest

from domain.scoring import PadelProfile, validate_padel_score


class PadelScoringTests(unittest.TestCase):
    def test_standard_sets_and_six_all_tiebreak_set(self):
        result = validate_padel_score([[6, 4], [4, 6], [7, 6]])

        self.assertTrue(result.is_complete)
        self.assertEqual(result.winner_side, "a")

    def test_six_five_is_not_a_completed_set(self):
        result = validate_padel_score([[6, 5]])

        self.assertFalse(result.is_valid)

    def test_deciding_match_tiebreak_profile(self):
        profile = PadelProfile(
            profile_key="padel-match-tiebreak",
            version=2,
            game_scoring_method="golden_point",
            deciding_set_policy="match_tiebreak",
        )

        result = validate_padel_score([[6, 4], [4, 6], [12, 10]], profile)

        self.assertTrue(result.is_complete)
        self.assertEqual(result.winner_side, "a")

    def test_short_deciding_match_tiebreak_is_rejected(self):
        profile = PadelProfile(deciding_set_policy="match_tiebreak")

        result = validate_padel_score([[6, 4], [4, 6], [9, 7]], profile)

        self.assertFalse(result.is_valid)

    def test_set_after_match_win_is_rejected(self):
        result = validate_padel_score([[6, 2], [6, 3], [1, 6]])

        self.assertFalse(result.is_valid)
        self.assertIn("sudah selesai", " ".join(result.errors))


if __name__ == "__main__":
    unittest.main()
