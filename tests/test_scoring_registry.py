import unittest

from domain.scoring import RuleProfile, UnsupportedScoringProfile, validate_score


class ScoringRegistryTests(unittest.TestCase):
    def test_selects_each_engine_from_profile(self):
        profiles_and_scores = (
            (
                RuleProfile(
                    "table-tennis", "tt-bo3", 1,
                    {"best_of": 3, "points_to_win": 11, "win_by": 2},
                ),
                [[11, 8], [11, 7]],
            ),
            (
                RuleProfile(
                    "badminton", "bwf-21", 1,
                    {"best_of": 3, "points_to_win": 21, "win_by": 2, "point_cap": 30},
                ),
                [[21, 15], [21, 18]],
            ),
            (
                RuleProfile(
                    "padel", "padel-standard", 1,
                    {
                        "best_of": 3,
                        "games_to_win_set": 6,
                        "tie_break_at": "6-6",
                        "game_scoring_method": "advantage",
                        "deciding_set_policy": "standard",
                    },
                ),
                [[6, 3], [6, 4]],
            ),
        )

        for profile, scores in profiles_and_scores:
            with self.subTest(sport=profile.sport_key):
                self.assertTrue(validate_score(profile, scores).is_complete)

    def test_unknown_sport_is_rejected(self):
        profile = RuleProfile("pickleball", "unknown", 1, {})

        with self.assertRaises(UnsupportedScoringProfile):
            validate_score(profile, [])


if __name__ == "__main__":
    unittest.main()
