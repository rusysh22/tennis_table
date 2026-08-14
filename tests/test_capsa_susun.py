import unittest

from domain.scoring.capsa_susun import (
    ROUNDS_PER_MATCH,
    card_multiplier,
    player_points,
    round_points,
    validate_match_score,
    validate_round_hand,
)


class CardMultiplierTests(unittest.TestCase):
    def test_multiplier_tiers_by_remaining_cards(self):
        self.assertEqual(card_multiplier(0), 0)
        self.assertEqual(card_multiplier(9), 1)
        self.assertEqual(card_multiplier(10), 2)
        self.assertEqual(card_multiplier(12), 2)
        self.assertEqual(card_multiplier(13), 3)


class PlayerPointsTests(unittest.TestCase):
    def test_player_with_empty_hand_scores_zero(self):
        self.assertEqual(player_points(0), 0)

    def test_points_double_per_two_held(self):
        self.assertEqual(player_points(5), 5)
        self.assertEqual(player_points(5, twos_remaining=1), 10)
        self.assertEqual(player_points(5, twos_remaining=2), 20)

    def test_high_card_count_uses_top_multiplier(self):
        self.assertEqual(player_points(13), 39)


class RoundPointsTests(unittest.TestCase):
    def test_aggregates_pair_totals(self):
        points_a, points_b = round_points(a1=0, a2=6, b1=10, b2=3)
        self.assertEqual(points_a, 6)
        self.assertEqual(points_b, 23)


class ValidateRoundHandTests(unittest.TestCase):
    def test_requires_all_four_values(self):
        errors = validate_round_hand(0, None, 5, 3)
        self.assertTrue(any("A2" in e for e in errors))

    def test_rejects_out_of_range_values(self):
        errors = validate_round_hand(0, 14, 5, 3)
        self.assertTrue(any("0 dan 13" in e for e in errors))

    def test_requires_exactly_one_player_to_go_out(self):
        errors = validate_round_hand(1, 2, 3, 4)
        self.assertTrue(any("menghabiskan kartu" in e for e in errors))

    def test_accepts_a_complete_round(self):
        self.assertEqual(validate_round_hand(0, 6, 10, 3), [])


class ValidateMatchScoreTests(unittest.TestCase):
    def test_lower_total_wins(self):
        segments = [[10, 20]] * ROUNDS_PER_MATCH
        result = validate_match_score(segments)

        self.assertTrue(result.is_valid)
        self.assertTrue(result.is_complete)
        self.assertEqual(result.winner_side, "a")
        self.assertEqual(result.points_a, 50)
        self.assertEqual(result.points_b, 100)

    def test_tie_after_five_rounds_is_rejected(self):
        segments = [[10, 10]] * ROUNDS_PER_MATCH
        result = validate_match_score(segments)

        self.assertFalse(result.is_valid)
        self.assertIsNone(result.winner_side)

    def test_incomplete_rounds_have_no_winner_yet(self):
        segments = [[10, 20], [5, 15]]
        result = validate_match_score(segments)

        self.assertTrue(result.is_valid)
        self.assertFalse(result.is_complete)
        self.assertIsNone(result.winner_side)

    def test_negative_points_are_rejected(self):
        result = validate_match_score([[-1, 5]])
        self.assertFalse(result.is_valid)

    def test_more_than_five_rounds_is_rejected(self):
        result = validate_match_score([[1, 2]] * (ROUNDS_PER_MATCH + 1))
        self.assertFalse(result.is_valid)


if __name__ == "__main__":
    unittest.main()
