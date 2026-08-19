# Normalized Multi-Sport Migration

## Current deployment state

The normalized schema, importer, and Flask repository adapter are ready. The
application remains on legacy storage by default; cutover requires the explicit
`STORAGE_BACKEND=normalized` setting. The normalized schema uses the separate,
neutral `intersport` namespace, so both stores can coexist during verification,
but the application never dual-writes them.

## Schema and import guarantees

- Versioned SQL migrations are applied only through `manage.py`; importing a
  Python module never creates database objects.
- Internal IDs are deterministic UUIDs derived from stable legacy keys.
- Human match codes such as `M01` and `M19` are preserved as `display_code`.
- The import records SHA-256 checksums for `config.json`, `teams.json`, and
  `matches.json`.
- The complete import is one PostgreSQL transaction.
- An existing tournament is not overwritten unless `--replace` is explicit.
- Padel and Badminton catalog records are created disabled. No divisions,
  courts, or schedules are invented for them.
- Invalid completed results are imported as `suspended`, without a winner, and
  receive an audit entry.

## Safe workflow

1. Stop score/schedule writes for a controlled maintenance window.
2. Back up the current JSON files, object references, and PostgreSQL database.
3. Run the read-only plan:

   ```powershell
   python manage.py plan-legacy-import
   ```

4. Resolve every item in `errors`. Warnings may be carried forward only when
   explicitly accepted by the tournament manager.
5. Apply the schema:

   ```powershell
   $env:DATABASE_URL = "postgresql://..."
   python manage.py migrate-normalized
   ```

6. Apply the import:

   ```powershell
   python manage.py import-legacy --apply
   ```

7. Verify counts, entrants, schedules, segments, standings, and both warning
   cases before enabling the normalized path.
8. Run the application smoke tests with the normalized backend:

   ```powershell
   $env:STORAGE_BACKEND = "normalized"
   $env:TOURNAMENT_SLUG = "intersport-2026"
   python app.py
   ```

   Verify the event hub, stage-driven standings/bracket/rules pages,
   `/api/v1/sports`, filtered/paginated `/api/v1/matches`, and filtered
   `/api/v1/standings`. Exercise one comment, score update, non-conflicting
   reschedule, and announcement update. Confirm stale match versions and
   same-slot court/entrant schedule conflicts are rejected without mutation.
   From `/admin/scorekeeper`, start one scheduled match, award one score unit,
   undo it, and verify `intersport.score_events` contains the award plus its
   reversal while the match version advances on every action.
9. Keep the source JSON snapshot immutable for rollback.

Legacy reset and shuffle operations are intentionally hidden and rejected while
normalized storage is active. Use a versioned tournament operation or a reviewed
`import-legacy --replace` workflow after a database backup instead.

## Cutover and rollback

Cut over only in a controlled write freeze. Record the final legacy checksums,
apply the import, run the smoke checklist, then restart with
`STORAGE_BACKEND=normalized`. Do not allow either deployment to accept writes
until traffic has moved completely.

For rollback, stop writes, restore the legacy snapshot to the intended point in
time, set `STORAGE_BACKEND=legacy`, and restart. The `intersport` schema is left
intact for diagnosis; no destructive reverse migration is required.

`python manage.py import-legacy` without `--apply` is always a dry run. If a
tournament was already imported, a second apply is rejected. `--replace`
deletes and recreates that normalized tournament inside one transaction, so it
must be used only after a fresh backup and reviewed dry run.

## Current source reconciliation items

- `M01` is stored as completed with `21-10`, `21-11`, `12-10`, which fails the
  Table Tennis profile. The importer maps it to `suspended` and preserves the
  original values in source metadata and audit history.
- `config.final_date` is `2026-07-29`, while `M19` is dated `2026-07-28`. Both
  source values are preserved and the report emits `final_date_mismatch`.

## Required decisions before enabling additional sports

- Padel and Badminton divisions and entrant types.
- Court names, venue assignments, and simultaneous-court capacity.
- Stage format per division.
- Padel advantage, golden-point, or star-point profile and deciding-set policy.
- Approved Badminton profile version.
- Standing and qualification policies.

After those decisions, create normalized configuration records and enable the
relevant `tournament_sports` row. Do not repurpose the legacy `category` field.
