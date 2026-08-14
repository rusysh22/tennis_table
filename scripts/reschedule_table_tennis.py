"""Shift the whole Table Tennis (tenis meja) timeline to start at 15:00 WIB.

Moves all 24 table-tennis matches (M49-M72) 60 minutes earlier, keeping the
same date, court and 20-minute spacing between matches. Only the `time`
field is touched (plus a reschedule_history entry per match) -- nothing
else about any match is changed, and no other sport is touched.

Safe to re-run: each match is only shifted if its live `time` still matches
the expected "before" value below; matches already moved (or already
started/finished) are skipped and reported, never silently overwritten.

Must run with the app's real environment (DATABASE_URL set, i.e. inside
the running container) so utils.update_match() writes to the LIVE DB.

Usage (on the VPS):
    docker compose exec web python scripts/reschedule_table_tennis.py            # dry run
    docker compose exec web python scripts/reschedule_table_tennis.py --apply    # write changes
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import utils  # noqa: E402

REASON = "Timeline tenis meja dimajukan, mulai pukul 15.00 WIB."

# match_id -> (expected_current_time, new_time). Every match shifts -60 min.
SHIFTS = {
    "M63": ("16:00", "15:00"),
    "M64": ("16:20", "15:20"),
    "M65": ("16:40", "15:40"),
    "M66": ("17:00", "16:00"),
    "M67": ("17:20", "16:20"),
    "M68": ("17:40", "16:40"),
    "M49": ("18:00", "17:00"),
    "M50": ("18:20", "17:20"),
    "M51": ("18:40", "17:40"),
    "M52": ("19:00", "18:00"),
    "M53": ("19:20", "18:20"),
    "M54": ("19:40", "18:40"),
    "M55": ("20:00", "19:00"),
    "M56": ("20:20", "19:20"),
    "M57": ("20:40", "19:40"),
    "M58": ("21:00", "20:00"),
    "M69": ("21:20", "20:20"),
    "M70": ("21:40", "20:40"),
    "M59": ("22:00", "21:00"),
    "M60": ("22:20", "21:20"),
    "M71": ("22:40", "21:40"),
    "M61": ("23:00", "22:00"),
    "M72": ("23:20", "22:20"),
    "M62": ("23:40", "22:40"),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write changes. Default is dry-run.")
    args = parser.parse_args()

    if not utils.USE_DB:
        sys.exit(
            "utils.USE_DB is False -- DATABASE_URL is not set in this environment. "
            "Run this from the deployed container (docker compose exec web ...)."
        )

    live_matches = {m.get("id"): m for m in utils.load_matches()}

    to_shift = []
    skipped = []
    for match_id, (before, after) in SHIFTS.items():
        m = live_matches.get(match_id)
        if m is None:
            skipped.append(f"{match_id}: not found live")
            continue
        if m.get("status") not in ("scheduled", "postponed"):
            skipped.append(f"{match_id}: status is '{m.get('status')}', not touched")
            continue
        if m.get("time") != before:
            skipped.append(
                f"{match_id}: live time is '{m.get('time')}', expected '{before}' -- not touched"
            )
            continue
        to_shift.append((match_id, before, after))

    print("=== Table Tennis timeline shift -> mulai 15:00 WIB ===")
    print(f"Matches to shift ({len(to_shift)}):")
    for match_id, before, after in to_shift:
        print(f"  {match_id}: {before} -> {after}")
    print(f"Skipped ({len(skipped)}):")
    for line in skipped:
        print(f"  {line}")

    if not to_shift:
        print("Nothing to do.")
        return

    if not args.apply:
        print("\nDry run only -- no changes written. Re-run with --apply to write.")
        return

    for match_id, before, after in to_shift:
        def shift(current, after=after, before=before):
            current.setdefault("reschedule_history", []).append({
                "from_date": current["date"],
                "from_time": current["time"],
                "from_court": current["court"],
                "to_date": current["date"],
                "to_time": after,
                "to_court": current["court"],
                "reason": REASON,
                "at": utils.now_wib().isoformat(timespec="seconds"),
            })
            current["time"] = after

        utils.update_match(match_id, shift)
        print(f"{match_id}: {before} -> {after} written.")

    print("Done.")


if __name__ == "__main__":
    main()
