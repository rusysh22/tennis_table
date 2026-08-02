import unittest

from domain.scoring import validate_match_score


class TableTennisScoringTests(unittest.TestCase):
    def test_best_of_three_completes_after_two_wins(self):
        result = validate_match_score([[11, 7], [12, 10]], best_of=3)

        self.assertTrue(result.is_valid)
        self.assertTrue(result.is_complete)
        self.assertEqual(result.winner_side, "a")

    def test_uncapped_deuce_is_valid(self):
        result = validate_match_score([[17, 15]], best_of=3)

        self.assertTrue(result.is_valid)
        self.assertFalse(result.is_complete)

    def test_impossible_deuce_margin_is_rejected(self):
        result = validate_match_score([[13, 10]], best_of=3)

        self.assertFalse(result.is_valid)
        self.assertIn("Game 1", result.errors[0])

    def test_game_cannot_continue_past_target_before_deuce(self):
        result = validate_match_score([[21, 9]], best_of=3)

        self.assertFalse(result.is_valid)

    def test_tied_or_unfinished_game_is_rejected(self):
        tied = validate_match_score([[10, 10]], best_of=3)
        unfinished = validate_match_score([[10, 8]], best_of=3)

        self.assertFalse(tied.is_valid)
        self.assertFalse(unfinished.is_valid)

    def test_games_after_decisive_win_are_rejected(self):
        result = validate_match_score([[11, 4], [11, 6], [8, 11]], best_of=3)

        self.assertFalse(result.is_valid)
        self.assertIn("sudah selesai", " ".join(result.errors))


if __name__ == "__main__":
    unittest.main()
