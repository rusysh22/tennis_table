"""Additive-only rollout of the Capsa Susun round-1 pairs into the LIVE database.

Registers CAPSA-01..CAPSA-16 in teams.json (if not already present) and
places them into CAPSA-M1..CAPSA-M8 (round 1) in matches.json, without
touching any other team or match. Safe to re-run: anything already live
is left untouched.

Must run with the app's real environment (DATABASE_URL set, i.e. inside
the running container) so utils.load_teams()/load_matches() read the
LIVE data, not the local files.

Usage (on the VPS):
    docker compose exec web python scripts/deploy_capsa_pairs.py            # dry run
    docker compose exec web python scripts/deploy_capsa_pairs.py --apply    # write changes
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import utils  # noqa: E402

CAPSA_CATEGORY_KEY = "capsa_susun"
CAPSA_SPORT_KEY = "capsa-susun"

CAPSA_TEAM_COLORS = [
    ("#475569", "#ffffff"), ("#7c3aed", "#ffffff"), ("#0e7490", "#ffffff"),
    ("#b45309", "#ffffff"), ("#be123c", "#ffffff"), ("#166534", "#ffffff"),
]

# Sequential pairing of the registered participant list (data/config.py's
# CAPSA_PARTICIPANTS in app.py), with the duplicate "Tito - IMU" entry
# (index 24 in the source list) dropped as a typo. 33 participants pair up
# into 16 pairs with one player ("Gusna A - IMN") left over/unplaced.
CAPSA_PAIRS = [
    ("CAPSA-01", "Jannata", "IMN", "Hendra Gunawan", "IMU"),
    ("CAPSA-02", "Pawestri", "IMU", "Casal", "ISB"),
    ("CAPSA-03", "Dody Indra", "IMU", "YIN", "ISB"),
    ("CAPSA-04", "Linda", "ISB", "Indah H", "IMU"),
    ("CAPSA-05", "Mitarani", "IMU", "Rizki Fore", "Indis"),
    ("CAPSA-06", "Steven", "ISB", "Daffa", "ISB"),
    ("CAPSA-07", "Pak Joko", "Indis", "Faisal", "Indis"),
    ("CAPSA-08", "Sades W", "ILSS Babelan", "Januar A", "ILSS Babelan"),
    ("CAPSA-09", "Rendy R Z", "ILSS Babelan", "Rona Kartiko", "ILSS Babelan"),
    ("CAPSA-10", "Tito", "IMU", "Dayat", "EMITS"),
    ("CAPSA-11", "Mughira", "EMITS", "Andre", "EMITS"),
    ("CAPSA-12", "Fajar", "Kalista", "Dino", "INVI"),
    ("CAPSA-13", "Aldi", "INVI", "Raihan", "INVI"),
    ("CAPSA-14", "Galang", "INVI", "Alif", "INVI"),
    ("CAPSA-15", "Kana", "INVI", "Henry", "INVI"),
    ("CAPSA-16", "Billy", "INVI", "Pak Adi Shima", "IMU"),
]

# Round-1 bracket placement: M1 = pair01 vs pair02, M2 = pair03 vs pair04, ...
ROUND1_SLOTS = {
    "CAPSA-M1": ("CAPSA-01", "CAPSA-02"),
    "CAPSA-M2": ("CAPSA-03", "CAPSA-04"),
    "CAPSA-M3": ("CAPSA-05", "CAPSA-06"),
    "CAPSA-M4": ("CAPSA-07", "CAPSA-08"),
    "CAPSA-M5": ("CAPSA-09", "CAPSA-10"),
    "CAPSA-M6": ("CAPSA-11", "CAPSA-12"),
    "CAPSA-M7": ("CAPSA-13", "CAPSA-14"),
    "CAPSA-M8": ("CAPSA-15", "CAPSA-16"),
}


def plan_team_changes(live_teams):
    to_add = {}
    skipped = []
    for idx, (code, p1, e1, p2, e2) in enumerate(CAPSA_PAIRS):
        if code in live_teams:
            skipped.append(code)
            continue
        color, text = CAPSA_TEAM_COLORS[idx % len(CAPSA_TEAM_COLORS)]
        to_add[code] = {
            "category": CAPSA_CATEGORY_KEY,
            "sport_key": CAPSA_SPORT_KEY,
            "group": "EXHIBITION",
            "color": color,
            "text": text,
            "player1": f"{p1} ({e1})" if e1 else p1,
            "player2": f"{p2} ({e2})" if e2 else p2,
        }
    if not to_add:
        return live_teams, [], skipped
    updated = dict(live_teams)
    updated.update(to_add)
    return updated, list(to_add.keys()), skipped


def plan_match_changes(live_matches):
    by_id = {m.get("id"): m for m in live_matches}
    placed = []
    skipped = []
    updated = [dict(m) for m in live_matches]
    for match_id, (code_a, code_b) in ROUND1_SLOTS.items():
        m = by_id.get(match_id)
        if m is None:
            skipped.append(f"{match_id} (not found live)")
            continue
        if m.get("team_a") or m.get("team_b"):
            skipped.append(f"{match_id} (already has teams)")
            continue
        placed.append(match_id)
        for um in updated:
            if um.get("id") == match_id:
                um["team_a"] = code_a
                um["team_b"] = code_b
    if not placed:
        return live_matches, [], skipped
    return updated, placed, skipped


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write changes. Default is dry-run.")
    args = parser.parse_args()

    if not utils.USE_DB:
        sys.exit(
            "utils.USE_DB is False -- DATABASE_URL is not set in this environment. "
            "Run this from the deployed container (docker compose exec web ...)."
        )

    live_teams = utils.load_teams()
    live_matches = utils.load_matches()

    new_teams, added_codes, skipped_codes = plan_team_changes(live_teams)
    new_matches, placed_ids, skipped_ids = plan_match_changes(live_matches)

    print("=== Capsa Susun pairs additive deploy plan ===")
    print(f"Pairs to add ({len(added_codes)}): {added_codes}")
    print(f"Pairs already live, left untouched ({len(skipped_codes)}): {skipped_codes}")
    print(f"Matches to place teams into ({len(placed_ids)}): {placed_ids}")
    print(f"Matches skipped ({len(skipped_ids)}): {skipped_ids}")
    print(
        "NOTE: 'Gusna A (IMN)' from the participant list has no partner and "
        "is not registered as a pair by this script."
    )

    if not added_codes and not placed_ids:
        print("Nothing to do -- live DB already has these pairs/placements.")
        return

    if not args.apply:
        print("\nDry run only -- no changes written. Re-run with --apply to write.")
        return

    if added_codes:
        utils.save_teams(new_teams)
        print("Teams updated.")
    if placed_ids:
        utils.save_matches(new_matches)
        print("Matches updated.")

    print("Done.")


if __name__ == "__main__":
    main()
