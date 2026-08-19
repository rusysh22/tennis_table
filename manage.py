"""Project management commands for normalized multi-sport migration."""

import argparse
import json
import os
from pathlib import Path

from intersport_core.legacy_import import load_legacy_import_plan
from intersport_core.migrations import apply_migrations
from intersport_core.repository import apply_import_plan


ROOT = Path(__file__).resolve().parent


def _build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    migrate = subparsers.add_parser(
        "migrate-normalized", help="Apply versioned SQL migrations to DATABASE_URL."
    )
    migrate.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))

    plan = subparsers.add_parser(
        "plan-legacy-import", help="Validate JSON data and print a dry-run import report."
    )
    plan.add_argument("--data-dir", type=Path, default=ROOT / "data")
    plan.add_argument("--output", type=Path, help="Optional path for the complete row plan JSON.")

    import_command = subparsers.add_parser(
        "import-legacy", help="Dry-run by default; use --apply to write normalized rows."
    )
    import_command.add_argument("--data-dir", type=Path, default=ROOT / "data")
    import_command.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    import_command.add_argument("--apply", action="store_true")
    import_command.add_argument(
        "--replace",
        action="store_true",
        help="Replace this tournament if already imported. Requires --apply.",
    )
    return parser


def _print_report(plan):
    print(json.dumps(plan.as_report(), ensure_ascii=False, indent=2))


def main(argv=None):
    args = _build_parser().parse_args(argv)
    if args.command == "migrate-normalized":
        applied = apply_migrations(args.database_url)
        if applied:
            print("Applied migrations:", ", ".join(applied))
        else:
            print("Normalized schema is already up to date.")
        return 0

    plan = load_legacy_import_plan(args.data_dir)
    _print_report(plan)
    plan.assert_valid()

    if args.command == "plan-legacy-import":
        if args.output:
            args.output.write_text(
                json.dumps(plan.records, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"Complete row plan written to {args.output.resolve()}")
        return 0

    if args.replace and not args.apply:
        raise SystemExit("--replace hanya boleh dipakai bersama --apply.")
    if not args.apply:
        print("Dry-run only; database was not changed. Add --apply after reviewing this report.")
        return 0

    applied_migrations = apply_migrations(args.database_url)
    counts = apply_import_plan(
        args.database_url, plan, replace_existing=args.replace
    )
    print("Applied migrations:", ", ".join(applied_migrations) or "none")
    print("Imported rows:", json.dumps(counts, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
