"""Additive-only rollout of Capsa Susun into the LIVE database.

Unlike migrate_db.py (which upserts whole-file blobs and would overwrite
every other match/config field with whatever is in the local JSON files),
this script only *adds* what Capsa Susun needs on top of whatever is
already live:

  - config.json: append the "capsa_susun" category and "capsa-susun" to
    enabled_sports, if not already present. Every other key is left
    byte-for-byte as it is live.
  - matches.json: append any CAPSA-* match from the local data/matches.json
    file whose id is not already present live. Existing matches (Capsa or
    otherwise) are never modified, reordered, or removed.
  - teams.json is never touched by this script.

Must run with the app's real environment (DATABASE_URL set, i.e. inside
the running container) so utils.load_config()/load_matches() read the
LIVE data, not the local files.

Usage (on the VPS):
    docker compose exec web python scripts/deploy_capsa_susun.py            # dry run
    docker compose exec web python scripts/deploy_capsa_susun.py --apply    # write changes
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import utils  # noqa: E402

CAPSA_CATEGORY = {
    "key": "capsa_susun",
    "label": "Capsa Susun — Eksibisi Berpasangan",
    "sport_key": "capsa-susun",
    "entrant_type": "pair",
    "groups": [],
    "has_final": True,
    "bracket_format": "single_elimination",
}


def _local_matches():
    local_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "matches.json")
    with open(local_path, "r", encoding="utf-8") as f:
        return json.load(f)


def plan_config_changes(live_config):
    changes = []
    enabled_sports = list(live_config.get("enabled_sports", []))
    if "capsa-susun" not in enabled_sports:
        changes.append("enabled_sports += 'capsa-susun'")
        enabled_sports.append("capsa-susun")

    categories = list(live_config.get("categories", []))
    if not any(c.get("key") == "capsa_susun" for c in categories):
        changes.append("categories += 'capsa_susun'")
        categories.append(dict(CAPSA_CATEGORY))

    if not changes:
        return live_config, changes

    updated = dict(live_config)
    updated["enabled_sports"] = enabled_sports
    updated["categories"] = categories
    return updated, changes


def plan_match_changes(live_matches, local_matches):
    live_ids = {m.get("id") for m in live_matches}
    to_add = []
    skipped = []
    for m in local_matches:
        mid = m.get("id", "")
        if not mid.startswith("CAPSA-"):
            continue
        if mid in live_ids:
            skipped.append(mid)
            continue
        to_add.append(m)

    if not to_add:
        return live_matches, [], skipped

    updated = list(live_matches) + to_add
    return updated, [m["id"] for m in to_add], skipped


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write changes. Default is dry-run.")
    args = parser.parse_args()

    if not utils.USE_DB:
        sys.exit(
            "utils.USE_DB is False -- DATABASE_URL is not set in this environment. "
            "Run this from the deployed container (docker compose exec web ...)."
        )

    live_config = utils.load_config()
    live_matches = utils.load_matches()
    local_matches = _local_matches()

    new_config, config_changes = plan_config_changes(live_config)
    new_matches, added_ids, skipped_ids = plan_match_changes(live_matches, local_matches)

    print("=== Capsa Susun additive deploy plan ===")
    print(f"Live matches count before: {len(live_matches)}")
    print(f"Config changes: {config_changes or '(none -- already present)'}")
    print(f"Matches to add ({len(added_ids)}): {added_ids}")
    print(f"Matches already live, left untouched ({len(skipped_ids)}): {skipped_ids}")
    print(f"Live matches count after: {len(new_matches)}")

    if not config_changes and not added_ids:
        print("Nothing to do -- live DB already has Capsa Susun config and matches.")
        return

    if not args.apply:
        print("\nDry run only -- no changes written. Re-run with --apply to write.")
        return

    if config_changes:
        utils.save_config(new_config)
        print("Config updated.")
    if added_ids:
        utils.save_matches(new_matches)
        print("Matches updated.")

    print("Done.")


if __name__ == "__main__":
    main()
