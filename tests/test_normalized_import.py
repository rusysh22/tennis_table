from pathlib import Path
import unittest
import uuid

from intersport_core.legacy_import import load_legacy_import_plan


ROOT = Path(__file__).resolve().parents[1]


class NormalizedImportPlanTests(unittest.TestCase):
    def setUp(self):
        self.plan = load_legacy_import_plan(ROOT / "tests" / "fixtures" / "legacy")

    def test_current_legacy_data_has_no_structural_import_errors(self):
        self.assertEqual(self.plan.errors, [])
        self.assertEqual(self.plan.counts["tournaments"], 1)
        self.assertEqual(self.plan.counts["sports"], 3)
        self.assertEqual(self.plan.counts["divisions"], 2)
        self.assertEqual(self.plan.counts["entrants"], 12)
        self.assertEqual(self.plan.counts["matches"], 19)

    def test_only_table_tennis_is_enabled_until_product_config_exists(self):
        sports = {row["id"]: row for row in self.plan.records["sports"]}
        enabled_keys = {
            sports[row["sport_id"]]["sport_key"]
            for row in self.plan.records["tournament_sports"]
            if row["enabled"]
        }

        self.assertEqual(enabled_keys, {"table-tennis"})

    def test_invalid_m01_is_quarantined_not_imported_as_completed(self):
        match = next(
            row for row in self.plan.records["matches"] if row["display_code"] == "M01"
        )

        self.assertEqual(match["status"], "suspended")
        self.assertFalse(match["result_valid"])
        self.assertIsNone(match["winner_entrant_id"])
        self.assertIn("invalid_completed_result", {w["code"] for w in self.plan.warnings})

    def test_final_is_a_stage_not_a_magic_group(self):
        match = next(
            row for row in self.plan.records["matches"] if row["display_code"] == "M19"
        )
        stage = next(
            row for row in self.plan.records["stages"] if row["id"] == match["stage_id"]
        )
        rule = next(
            row
            for row in self.plan.records["rule_profiles"]
            if row["id"] == match["rule_profile_id"]
        )

        self.assertEqual(stage["stage_type"], "final")
        self.assertIsNone(match["group_id"])
        self.assertEqual(rule["config"]["best_of"], 5)

    def test_import_uses_iana_timezone_and_reports_date_drift(self):
        first_match = self.plan.records["matches"][0]

        self.assertTrue(first_match["scheduled_at"].endswith("+07:00"))
        self.assertIn("final_date_mismatch", {w["code"] for w in self.plan.warnings})

    def test_ids_and_plan_are_deterministic(self):
        second = load_legacy_import_plan(ROOT / "tests" / "fixtures" / "legacy")

        self.assertEqual(self.plan.records, second.records)
        for rows in self.plan.records.values():
            for row in rows:
                uuid.UUID(row["id"])


if __name__ == "__main__":
    unittest.main()
