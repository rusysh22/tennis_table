# P1 Mobile Scorekeeper

The mobile scorekeeper is available at `/admin/scorekeeper` after admin login.
It is a focused operational surface separate from the full match-management
form and works with both legacy and normalized storage.

## Workflow

1. Filter by sport, date, court, or status and open a match.
2. Start a scheduled, checked-in, or postponed match. Both entrants, schedule,
   and court must already exist.
3. Award one scoring unit with the large participant buttons. Every action is
   saved immediately and increments the optimistic-lock version.
4. The active game or set closes automatically when its immutable rule profile
   says the score is valid.
5. Once the match score is complete, review it and explicitly confirm Finish.
6. Undo the latest scoring action. Changing a completed result requires a
   correction reason and returns the match to Live.
7. A completed score entered outside scorekeeper can be opened for correction;
   the final winning unit is restored as the active score.

## Sport-aware scoring units

- Table Tennis: one point per tap; a completed segment is a game.
- Badminton: one point per tap; the configured game target, win-by margin, and
  cap are displayed and enforced.
- Padel: one game per tap; a completed segment is a set. A configured deciding
  match tie-break switches the active unit to tie-break points.

The public match model and standings continue to read only completed segments.
Partial in-progress scores are projected from score events and never count as a
won game/set prematurely.

## Persistence and concurrency

Legacy JSON stores `scorekeeper_events` on the match document. Normalized
PostgreSQL stores the same projection in `intersport.score_events`, including
event sequence, side, value, metadata snapshots, and `reversal_of_id` for undo.

The match row/document remains the concurrency boundary. Each score action
requires the current match version. A stale device receives HTTP 409 with the
latest state so it cannot silently overwrite another scorekeeper.

Completed-result changes also append the existing score-correction audit data.
The normalized adapter writes those corrections to `intersport.audit_logs`.

## Failure behavior

- Controls are disabled while a save is pending.
- Network failures do not apply an optimistic local score.
- Validation errors are announced in an alert region.
- Saved/conflict status is announced through a polite live region.
- Touch controls remain at least 48 CSS pixels, with the scoring controls larger
  than 90 CSS pixels on mobile.
