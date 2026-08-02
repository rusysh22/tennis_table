from pathlib import Path
import unittest

from intersport_core.migrations import discover_migrations


ROOT = Path(__file__).resolve().parents[1]


class NormalizedMigrationTests(unittest.TestCase):
    def test_migrations_are_ordered_and_have_stable_checksums(self):
        migrations = discover_migrations(ROOT / "migrations")

        self.assertGreaterEqual(len(migrations), 1)
        self.assertEqual(
            [migration.version for migration in migrations],
            sorted(migration.version for migration in migrations),
        )
        self.assertTrue(all(len(migration.checksum) == 64 for migration in migrations))

    def test_core_schema_contains_required_hierarchy_and_neutral_namespace(self):
        sql = "\n".join(
            migration.sql for migration in discover_migrations(ROOT / "migrations")
        ).lower()

        for table in (
            "tournaments",
            "sports",
            "divisions",
            "stages",
            "groups",
            "matches",
            "match_segments",
            "score_events",
            "stream_sessions",
            "audit_logs",
        ):
            self.assertIn(f"create table intersport.{table}", sql)
        self.assertNotIn("create table tennis.", sql)
        self.assertIn("rule_profiles_immutable", sql)
        self.assertIn("standing_policies_immutable", sql)


if __name__ == "__main__":
    unittest.main()
