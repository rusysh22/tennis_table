# P1 Stage-Driven Competition Slice

This slice removes the remaining Table Tennis-specific competition rendering
from the public standings, bracket, champion, rules, and Home event-hub flows.
It works with both `STORAGE_BACKEND=legacy` and `STORAGE_BACKEND=normalized`.

## Runtime model

The UI consumes one competition structure:

```text
Tournament -> Sport -> Division -> Stage -> Group -> Match
```

Normalized storage loads this structure from PostgreSQL. The rollback-safe
legacy adapter derives the same shape from `config.categories`, mapping regular
groups to `group-stage` and the old `FINAL` match to a terminal `final` stage.
Templates do not branch on `ganda_putra`, `ganda_campuran`, or a hardcoded final.

## Behavior delivered

- Home shows an event hub for enabled and planned sports with live, completed,
  match, division, and next-match summaries.
- Standings loop through configured divisions, stages, and groups and expose the
  immutable standing-policy version used for ranking.
- Brackets render configured qualification sources and elimination stages.
- Champion resolution comes from the terminal configured stage. A single
  round-robin group may declare `champion_from_standings`.
- Rules list the configured, versioned scoring profiles per sport and the stage
  format/default profile per division.
- `/api/v1/standings` accepts `sport`, `division`, `stage`, and `group` filters,
  returns policy metadata, and supports conditional requests with ETag.
- Admin entrant selection is limited to elimination stages and entrants from
  the same sport/division.
- Schedule or entrant changes reject exact same-slot court and entrant conflicts
  transactionally. Cancelled matches are ignored; reopening one re-runs checks.

## Compatibility and rollback

Existing public URLs and legacy champion-photo keys remain valid. Legacy remains
the default backend, so rollback is still an environment change plus restart;
there is no dual-write path.

Padel and Badminton profiles are visible as planned configuration, but the
importer intentionally leaves their tournament sports disabled until divisions,
courts, stage formats, and event-specific rule choices are confirmed.
