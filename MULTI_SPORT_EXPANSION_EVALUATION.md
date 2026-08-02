# Multi-Sport Expansion, UX, Configuration, and Live Streaming Evaluation

Audit date: 2 August 2026  
Application reviewed: Mini-Round Table Tennis InterSport 2026  
Target sports: Table Tennis, Padel, and Badminton  
Document language: English  

## 1. Executive conclusion

The current application is usable for a small, single table-tennis tournament, but it should not be expanded by simply adding `padel` and `badminton` values to the existing `category` field.

The present domain model treats Table Tennis divisions (`ganda_putra` and `ganda_campuran`) as if they were sports. Table-tennis rules, one-table assumptions, a specific two-group final, dates, Indonesian labels, and red/pink presentation are embedded across Python, JSON seed data, Jinja templates, CSS, JavaScript, generated Open Graph images, and static artwork.

The recommended solution is an incremental refactor, not a complete rewrite:

1. Keep Flask and server-rendered Jinja for now.
2. Introduce a real `Sport -> Division -> Stage -> Group -> Match` hierarchy.
3. Replace whole-document JSON/JSONB persistence with normalized PostgreSQL records and transactions.
4. Add one validated scoring engine per sport, selected through a rule profile.
5. Rebuild the public navigation around an event hub and a persistent sport selector.
6. Build a focused mobile scorekeeper interface instead of asking administrators to type raw scores into generic fields.
7. Introduce a provider-independent streaming model; use an external video platform for ingest, transcoding, delivery, and recording.
8. Replace the red/pink theme with a centralized green, blue, white, and neutral design system.

The highest-priority work is domain and data correction, score validation, security, and concurrency. Live streaming and the visual redesign should be built on top of that foundation.

## 2. Audit scope and method

The review covered:

- All Python application, utility, data-generation, migration, and image-generation code.
- All public and admin routes.
- All Jinja templates.
- The complete CSS and JavaScript bundles.
- Current `teams.json`, `matches.json`, and `config.json` data.
- Desktop and 390 x 844 mobile layouts.
- Keyboard/modal behavior and basic accessibility contracts.
- Login, scheduling, live score, completion, recap, and standings behavior.
- Current hardcoded values and configuration boundaries.
- Data integrity and security headers.
- A full isolated operational cycle using a temporary copy of the application data.

The isolated cycle was:

1. Sign in as an administrator.
2. Open a scheduled match.
3. Change it to Live.
4. Verify that it appears on the public Live page.
5. Enter two winning games.
6. Verify automatic completion.
7. Verify the public match detail, recap, standings, and removal from the Live page.

The cycle passed functionally, but it exposed validation, accessibility, state, and usability problems documented below. The original application data was not changed by this cycle.

## 3. Current system map

### 3.1 Technology and structure

- Flask monolith in `app.py` (approximately 970 lines).
- Business and persistence helpers in `utils.py`.
- Tournament-specific schedule generation in `generate_data.py`.
- Jinja templates with server-side rendering and small JavaScript enhancements.
- One large CSS file with approximately 1,383 lines.
- One JavaScript file with approximately 443 lines, plus page-level inline scripts.
- JSON files for local persistence.
- Optional PostgreSQL storage, but each JSON document is stored as one JSONB value in `tennis.app_data`.
- Supabase-compatible S3 storage for match and champion photos.
- Polling of the entire `/api/matches` collection every 15 seconds on live-score surfaces.

### 3.2 Existing public surfaces

- Home
- Schedule list
- Calendar
- Live score
- Group standings
- Table-tennis-specific final bracket
- Completed-match recap
- Gallery
- Table-tennis rules
- Match detail with comments, voting, sharing, and documentation

### 3.3 Existing admin surfaces

- Shared-password login
- Match dashboard
- Score entry
- Status change
- Walkover
- Reschedule
- Finalist assignment
- Photo upload, deletion, and rotation
- Champion photo management
- Announcement editing
- Table-tennis-specific group shuffling
- Full data reset

## 4. Critical and high-priority findings

| ID | Severity | Finding | Impact | Evidence |
|---|---|---|---|---|
| F-01 | Critical | There is no `sport` entity. `category` contains Table Tennis divisions. | Padel and Badminton cannot have independent rules, stages, courts, labels, or standings without more hardcoding. | `data/config.json`, `data/teams.json`, `generate_data.py` |
| F-02 | Critical | Score input is not validated against the published rules. | Invalid results can be completed and can corrupt standings. | `app.py:829`, `utils.py:263`, `templates/aturan.html:52` |
| F-03 | Critical | Read-modify-write updates are not transactional. | Concurrent score, vote, or comment writes can silently overwrite each other. This becomes much more likely with three sports and live traffic. | `utils.py:119`, `utils.py:138` |
| F-04 | Critical | Admin authentication uses one shared password with a production fallback value. | Anyone who knows the fallback has full destructive access; there is no accountability or role separation. | `app.py:38`, `README.md` |
| F-05 | Critical | State-changing forms have no CSRF protection. | A signed-in administrator can be tricked into changing scores, shuffling teams, deleting photos, or resetting data. | All admin POST forms and routes |
| F-06 | High | Home incorrectly reports the tournament as finished when no incomplete match is in the future. | The reviewed data has 18 unfinished matches but the home page says all matches are finished. | `app.py:239`, `app.py:273`, `templates/index.html:56` |
| F-07 | High | Current match data violates the published scoring rules. | M01 contains three winning games, including 21-point games, although the UI says first to 11 and Best of 3. | `data/matches.json`, `templates/aturan.html:54` |
| F-08 | High | The configured final date differs from the actual final match date. | Calendar labels, bracket copy, countdowns, and operations can disagree. | `config.final_date = 2026-07-29`; M19 is `2026-07-28` |
| F-09 | High | Published standings tie-break rules and implemented rules differ. | A group champion can be wrong. The rule page includes head-to-head, while code sorts only points, game difference, and point difference. | `templates/aturan.html:158`, `utils.py:345` |
| F-10 | High | Table Tennis final and champion logic is hardcoded in multiple routes and templates. | Other formats cannot reuse bracket and champion features safely. | `app.py:276`, `app.py:405`, `app.py:475`, `templates/bracket.html` |
| F-11 | High | The public API returns the full enriched match collection without sport filtering, pagination, versioning, or delta updates. | Payload and database cost grow with every sport; live polling scales poorly. | `app.py:721`, `static/js/main.js:64` |
| F-12 | High | The mobile home page has overlapping fixed UI. | The comment widget and announcement bell cover statistics and content. | Browser audit at 390 x 844; `.floating-comments`, `.mobile-floating-bell` |
| F-13 | High | Match modals do not move focus, trap focus, mark background inert, or reliably restore focus. | Keyboard and screen-reader users can interact behind the modal. | `static/js/main.js:199`, `templates/base.html:121` |
| F-14 | High | Closed mobile navigation links remain focusable and the menu button label remains “Open menu” after opening. | Keyboard and assistive-technology behavior does not match the visible state. | `static/js/main.js:4`, mobile browser audit |
| F-15 | High | Score fields have no accessible name. | A screen reader announces generic spin buttons without team or game context. | `templates/admin/edit_match.html:83`, mobile browser audit |
| F-16 | High | Login accepts an unvalidated `next` URL. | Verified open redirect after login to an external origin. | `app.py:744` |
| F-17 | High | No security headers are returned and session cookies are not Secure or SameSite-protected by default. | Increased clickjacking, content injection, cross-site, and session exposure risk. | Runtime header audit and Flask defaults |
| F-18 | Medium | The admin dashboard is a wide table requiring horizontal scrolling on mobile. | Finding and managing a match is slow for on-court scorekeepers. | `templates/admin/dashboard.html`, mobile browser audit |
| F-19 | Medium | Public comments promise committee review, but no moderation queue exists. | Inappropriate content cannot be reviewed, hidden, approved, or audited through the UI. | `app.py:594`, `templates/_match_detail_content.html:146` |
| F-20 | Medium | CSS contains more than 200 inline style attributes and six undefined custom properties. | Theme replacement will be inconsistent and fragile. | CSS/template audit |
| F-21 | Medium | A Google-hosted font is requested although a local font file exists. | Avoidable third-party dependency, privacy request, and rendering delay. | `static/css/style.css:1`, `static/fonts/PlusJakartaSans.ttf` |
| F-22 | Medium | Media download/rotation has no request timeout and upload size is not globally limited. | A slow source or oversized image can hold workers or exhaust memory. | `app.py:46`, `app.py:923` |
| F-23 | Medium | Current schedules, generated schedules, config, and presentation copy have drifted. | Resetting data can produce a different tournament than the currently published one. | `generate_data.py`, `data/matches.json`, `data/config.json`, `templates/bracket.html:31` |
| F-24 | Medium | There is no automated test suite. | Multi-sport changes have no regression protection. | Repository inventory |

## 5. Correct domain model

### 5.1 Required hierarchy

Use the following hierarchy consistently in backend data, URLs, APIs, and UI:

```text
Event / Tournament
  Sport
    Division
      Stage
        Group or Bracket
          Match
            Score segments and score events
```

Definitions:

- **Tournament**: the overall InterSport event, dates, timezone, branding, and organization.
- **Sport**: Table Tennis, Padel, or Badminton.
- **Division**: for example Men’s Doubles, Women’s Doubles, Mixed Doubles, Men’s Singles, or Open Doubles.
- **Stage**: round robin, group stage, knockout, semifinal, final, or classification stage.
- **Group**: optional pool within a stage.
- **Match**: one contest between two entrants.
- **Entrant**: an individual or team registered in a division.
- **Score segment**: sport-specific unit such as a Table Tennis game, Badminton game, or Padel set.
- **Score event**: optional point/game-level event used for undo, audit history, and live updates.

Do not use `category` to mean both sport and division. Do not use `FINAL` as a magic group name. A final is a stage or round type.

### 5.2 Recommended database records

| Entity | Important fields |
|---|---|
| `tournaments` | id, slug, name, timezone, locale, start/end, status, branding profile |
| `sports` | id, slug, name, icon, enabled |
| `tournament_sports` | tournament_id, sport_id, ordering, feature flags |
| `divisions` | id, tournament_sport_id, name, entrant type, team-size limits, rule_profile_id |
| `people` | id, display name, optional employee reference, privacy flags |
| `entrants` | id, division_id, code, display name, seed, status |
| `entrant_members` | entrant_id, person_id, role, order |
| `stages` | id, division_id, type, name, sequence, qualification policy |
| `groups` | id, stage_id, name |
| `venues` | id, name, address/room, timezone |
| `courts` | id, venue_id, sport_id, name, enabled |
| `matches` | id, stage/group, entrant A/B, court, scheduled time, status, winner, version |
| `match_segments` | match_id, sequence, type, score A/B, status, metadata |
| `score_events` | match_id, sequence, event type, side, value, actor, timestamp, reversal reference |
| `standing_policies` | win/loss/WO points and ordered tie-break rules |
| `stream_sessions` | match/court, provider, provider reference, status, privacy, schedule |
| `media_assets` | owner type/id, storage key, mime, dimensions, moderation state |
| `announcements` | scope, title, body, start/end, priority, status |
| `comments` | match, author, body, moderation status, timestamps |
| `reactions` | match, side, reaction, actor/session hash |
| `users` | account, password hash or SSO id, status |
| `roles` / `user_roles` | admin, tournament manager, scorekeeper, media moderator, viewer |
| `audit_logs` | actor, action, entity, before/after, request id, timestamp |

Use UUIDs or stable opaque IDs internally. Human-readable match numbers can remain separate display fields.

## 6. Backend adjustments

### 6.1 Application structure

Keep Flask, but split the monolith into explicit layers:

```text
app/
  blueprints/
    public.py
    admin.py
    api.py
    webhooks.py
  domain/
    scoring/
      base.py
      table_tennis.py
      badminton.py
      padel.py
    standings.py
    scheduling.py
    transitions.py
  services/
    match_service.py
    stream_service.py
    media_service.py
    notification_service.py
  repositories/
  models/
  schemas/
  templates/
  static/
```

Routes should orchestrate requests; they should not contain tournament-specific winner, bracket, upload, or scoring logic.

### 6.2 Persistence

Move to normalized PostgreSQL before enabling three sports in production.

Required properties:

- One database row per mutable entity.
- Transactions for every match update.
- Optimistic locking through a `version` column, or row locking for score operations.
- Unique constraint on court and scheduled time where appropriate.
- Foreign keys between matches, entrants, stages, and sports.
- Check constraints for statuses and sequences.
- Alembic or an equivalent migration mechanism; do not create schema at module import time.
- Automated backups and tested restore procedures.
- Idempotency keys for score writes and streaming webhooks.

The current thread lock only serializes a single file operation. It does not protect the full load-modify-save cycle and does not work across multiple application processes. The current JSONB document has the same lost-update problem.

### 6.3 Match state machine

Use explicit allowed transitions:

```text
draft -> scheduled -> check_in -> live -> completed
                    -> postponed -> scheduled
                    -> cancelled
check_in/live -> suspended -> live
scheduled/check_in/live -> walkover -> completed
```

Rules:

- Only eligible roles can perform each transition.
- A match cannot go Live without both entrants and a court.
- A completed match requires a valid winner or an explicit walkover/cancellation result.
- Editing a completed score requires a correction reason and audit entry.
- A walkover must clear or explicitly preserve partial score metadata according to policy; partial games must not accidentally count in standings.
- Schedule conflicts must be checked before saving.
- Final/knockout entrants should advance automatically from qualification rules, with an audited manual override.

### 6.4 Sport-specific scoring engines

The scoring engine should be code, not arbitrary executable configuration. A rule profile selects validated parameters supported by that engine.

| Sport | Recommended initial profile | Required validation |
|---|---|---|
| Table Tennis | Best of 3 or 5 games; game to 11; win by 2 | Reject ties, reject a non-winning final score, stop after decisive game, allow deuce with no fixed cap unless event policy says otherwise |
| Badminton | Best of 3 games; selectable approved profile | For the current 21-point profile: win by 2 from 20-all, cap at 30, stop after two games won. Keep alternate profiles versioned rather than hardcoding one permanent rule. |
| Padel | Best of 3 sets; advantage or golden-point game profile | Track games within sets, set win at six with required margin, tie-break policy at 6-6, match win after two sets, and configured deciding-set behavior |

Recommended profile fields:

- `profile_key` and immutable `version`.
- `sport_key`.
- `segments_to_win`.
- `points_to_win_segment` where appropriate.
- `win_by`.
- `point_cap` where appropriate.
- Padel game scoring method: advantage, star point, or golden point.
- Tie-break trigger and tie-break target.
- Deciding-segment policy.
- Walkover score representation.
- Display terminology.

Store the selected profile version on the match. A later rule change must not reinterpret historical matches.

### 6.5 Standings engine

Standings must use a policy attached to the division/stage.

Example ordered policy:

1. Competition points.
2. Head-to-head result when exactly two entrants are tied.
3. Mini-table among tied entrants when three or more are tied.
4. Segment/game difference.
5. Point difference.
6. Additional deciding match or declared lot policy.

Every tie-break should return an explanation that the UI can display, such as “Ranked second by head-to-head result.” This makes standings auditable and reduces disputes.

### 6.6 API design

Introduce versioned endpoints:

```text
GET  /api/v1/tournaments/{tournament}
GET  /api/v1/sports
GET  /api/v1/matches?sport=&division=&date=&status=&cursor=
GET  /api/v1/matches/{id}
POST /api/v1/matches/{id}/transitions
POST /api/v1/matches/{id}/score-events
POST /api/v1/matches/{id}/corrections
GET  /api/v1/standings?stage=&group=
GET  /api/v1/streams?status=live&sport=
POST /api/v1/streams/{id}/actions
GET  /api/v1/events/stream?match_id=
```

Requirements:

- Validate request and response schemas.
- Return only fields needed by the client.
- Filter by sport and date.
- Paginate collection endpoints.
- Use ETag/version headers.
- Use consistent error objects and field errors.
- Require idempotency keys on score actions.
- Add rate limits for login, comments, reactions, and public API calls.

For live score, use Server-Sent Events when only the server pushes updates to viewers. It is simpler than a full bidirectional WebSocket channel. Keep a polling fallback for restricted networks.

## 7. Security and governance

Complete these items before exposing the expanded application broadly:

1. Remove the default admin password.
2. Use named accounts with Argon2/bcrypt password hashes, or corporate SSO.
3. Add role-based permissions.
4. Add CSRF tokens to every state-changing browser form.
5. Validate `next` redirects against an internal-path allowlist.
6. Configure Secure, HttpOnly, and SameSite session cookies.
7. Rotate sessions after login and enforce expiry.
8. Add login throttling and temporary lockout.
9. Add audit logs for score, schedule, stream, media, user, and destructive operations.
10. Require typed confirmation for reset/shuffle or replace them with versioned tournament operations.
11. Add Content Security Policy, frame policy, HSTS, content-type, referrer, and permissions headers.
12. When embedding streaming providers, allow only the selected provider origins in CSP.
13. Validate uploaded media by decoded content, not filename; enforce byte, pixel, and count limits.
14. Add request timeouts and maximum response sizes for server-side downloads.
15. Keep storage credentials, stream keys, webhook secrets, and API tokens server-side only.
16. Store object keys rather than hardcoded public Supabase URLs.
17. Define participant-name, comment, reaction, recording, and media retention policies.
18. Provide a moderation queue with approve, hide, delete, and audit actions.

## 8. Frontend information architecture

### 8.1 Recommended global navigation

Use this primary navigation:

- Home
- Schedule
- Live
- Standings
- Media
- Rules
- Admin, only when authorized

Add a persistent sport switcher directly below the header or inside the page header:

- All Sports
- Table Tennis
- Padel
- Badminton

The selected sport must persist through Schedule, Live, Standings, Media, and Rules. Store it in the URL, not only browser storage, so pages remain shareable.

### 8.2 Recommended URLs

```text
/
/schedule?sport=table-tennis
/live?sport=padel
/standings?sport=badminton&division=mixed-doubles
/sports/table-tennis
/sports/table-tennis/rules
/matches/{id}
/admin
/admin/matches/{id}/score
/admin/streams
```

Existing Indonesian URLs can redirect to the new routes during migration.

### 8.3 Home page

The home page should be an event hub, not a Table Tennis promotional page.

Recommended order:

1. Compact event header with dates, venue, and current event status.
2. “Live now” area containing the active stream or active matches.
3. Three sport cards with next match, live count, and standings shortcut.
4. Today’s cross-sport schedule.
5. Recent results.
6. Announcements.
7. Optional media highlights.

Do not infer “tournament completed” from the absence of future matches. Use explicit tournament status plus the count of incomplete matches.

### 8.4 Schedule

Required filters:

- Sport
- Division
- Date
- Venue/court
- Stage/group
- Status
- Entrant/player search

Use compact day sections and cards on mobile. Do not force scorekeepers or spectators to horizontally scroll a 12-column table.

Show conflict and change indicators:

- Rescheduled
- Court changed
- Delayed
- Stream available
- Check-in required

### 8.5 Live page

Desktop layout:

- Video player as the primary element.
- Live scoreboard and match metadata beside the player.
- Court/stream switcher when multiple streams are active.
- Today’s matches and upcoming stream schedule below.

Mobile layout:

- 16:9 player at the top.
- Sticky compact scoreboard below the player, not on top of video controls.
- Court switcher as horizontal chips.
- Connection state, muted/autoplay explanation, and “open in provider” fallback.
- No floating widget may cover the player, score, or primary actions.

### 8.6 Standings and brackets

- Select Sport, Division, and Stage.
- Render group standings or bracket based on the stage type.
- Do not maintain a dedicated hardcoded Table Tennis bracket page.
- Show qualification lines and tie-break explanations.
- Use horizontally scrollable tables only as a last resort; provide a mobile card/list alternative.

### 8.7 Rules

Replace the single static Table Tennis document with:

- Event-wide rules.
- One rule page per sport.
- One competition-format summary per division.
- A visible rule-profile version and effective date.
- Admin-editable event-specific exceptions, with change history.

### 8.8 Admin dashboard

Prioritize operational tasks:

- Live now
- Starting in the next 30 minutes
- Awaiting result confirmation
- Delayed or conflicted
- Stream offline
- Comments/media awaiting moderation

Add persistent Sport and Court filters. Replace the mobile table with match-operation cards.

### 8.9 Scorekeeper mode

Build a dedicated mobile-first route rather than reusing the full admin edit page.

Required behaviors:

- Large named score controls.
- Sport-aware labels: Game, Set, Point, Tie-break.
- Start, pause, resume, undo, and finish actions.
- Validation before every transition.
- Immediate, visible save state: Saving, Saved, Offline, Conflict.
- Undo through score events instead of overwriting raw arrays.
- Confirmation and reason for final correction.
- Unsaved-change protection.
- Optimistic concurrency conflict recovery.

For Padel, provide game-level controls and optional point-level scoring. Do not represent a Padel match with the current generic three numeric “Set” rows.

## 9. Green, blue, and white design system

### 9.1 Recommended palette

| Token | Value | Use |
|---|---|---|
| `--green-900` | `#073B2A` | Dark brand surfaces and high-contrast text |
| `--green-700` | `#0B5D3B` | Primary brand and completed state |
| `--green-500` | `#148A5B` | Accents, selected items, success icons |
| `--green-100` | `#E4F5EC` | Completed cards and soft sections |
| `--blue-900` | `#0B2E59` | Header/footer, destructive-neutral surface |
| `--blue-700` | `#15518A` | Primary links and buttons |
| `--blue-500` | `#1D70B7` | Live and interactive highlights |
| `--blue-100` | `#DDEEFF` | Scheduled cards and filters |
| `--white` | `#FFFFFF` | Main surface and inverse text |
| `--surface` | `#F6FAFD` | Page background |
| `--ink` | `#10233D` | Primary text |
| `--muted` | `#5C7088` | Secondary text |
| `--border` | `#C9DAEA` | Dividers and input borders |

Suggested sport accents, all within the requested palette:

- Table Tennis: deep green.
- Padel: royal blue.
- Badminton: blue-green/teal.

Never identify a sport or status by color alone. Always include a name, icon, and text status.

### 9.2 Status treatment without red

- Live: strong blue badge, white “LIVE” text, dot, and optional pulse.
- Completed: green badge and check icon.
- Scheduled: pale blue badge and calendar icon.
- Postponed: blue-gray badge and pause icon.
- Walkover: dark navy badge and flag icon.
- Destructive admin action: dark navy outlined panel, warning icon, explicit text, and typed confirmation.
- Validation error: dark navy text, strong border, error icon, and field-level explanation. Do not rely on hue alone.

### 9.3 Required implementation changes

1. Replace semantic names such as `--red-*`, `--pink-*`, and `--maroon-*` with role-based tokens.
2. Remove hardcoded red values from CSS, templates, canvas confetti, theme-color metadata, and Open Graph image generation.
3. Replace Table Tennis hero and footer artwork with event-neutral artwork or sport-specific artwork selected by the active sport.
4. Move the 202 inline styles into reusable component classes.
5. Define or remove `--brand-red`, `--font-sans`, `--gray-200`, `--gray-50`, `--radius-md`, and `--slate-800`.
6. Use the bundled local font through `@font-face`; remove the Google Fonts import.
7. Test all text/background pairs against WCAG AA contrast.
8. Respect reduced-motion settings for all animation, not only selected effects.

## 10. Live streaming architecture

### 10.1 Recommended principle

Do not ingest, transcode, record, and distribute video directly from this Flask application. Those functions require specialized media infrastructure and would compete with score and admin requests.

Use this flow:

```text
Camera / phone / OBS
  -> RTMPS or provider application
  -> Managed streaming provider
  -> Adaptive player embedded in this web application

Scorekeeper
  -> Match API
  -> Score event store
  -> SSE live-score updates
  -> Public scoreboard and optional OBS browser overlay
```

### 10.2 Provider recommendation

| Option | Best for | Benefits | Limitations |
|---|---|---|---|
| YouTube Live embed | Fastest and lowest-complexity MVP | Familiar player, simple iframe/API integration, external operational tooling | Unlisted is link-private, not true authenticated access; less UI/control ownership |
| Cloudflare Stream | Controlled production streaming | RTMPS/SRT ingest, provider player or HLS/DASH, recordings, origin controls, signed access options | Paid service and integration work |
| Mux | Product-grade video and observability | RTMP/RTMPS ingest, low/reduced latency profiles, webhooks, playback APIs, player and analytics | Paid service and integration work |
| Self-hosted streaming | Only for a dedicated media team | Maximum control | Highest reliability, security, bandwidth, player, recording, and operational burden; not recommended here |

Recommended default:

- If streams may be publicly accessible or unlisted: begin with YouTube Live behind a provider adapter.
- If the event must be restricted to authenticated employees: use Cloudflare Stream or Mux with signed playback from the first release.

### 10.3 Stream data model

Each `stream_session` should contain:

- Tournament, sport, court, and optional match.
- Provider key.
- Provider resource ID and playback ID.
- Never expose the ingest stream key.
- Scheduled start/end.
- State: draft, scheduled, ready, live, reconnecting, ended, failed.
- Privacy: public, unlisted, authenticated.
- Recording policy and recording asset ID.
- Poster/thumbnail.
- Health timestamps and last webhook event.
- Created/updated user and audit metadata.

### 10.4 Streaming workflow

1. Tournament manager creates or selects a court stream.
2. Backend creates/retrieves the provider resource.
3. Stream key is shown only to an authorized operator and is never sent to public pages.
4. Operator configures OBS or the approved phone application.
5. Provider webhook marks the stream ready/live.
6. Scorekeeper links the correct match and starts the match.
7. Public Live page activates the player and synchronized scoreboard.
8. Reconnect state is shown during short interruptions.
9. Match completion does not immediately terminate a court stream if another match follows.
10. Provider webhook marks the stream ended and recording available.
11. Recording is linked to match media after moderation.

### 10.5 Required resilience and privacy behavior

- Idempotently verify webhook signatures.
- Do not trust client-supplied provider status.
- Show “Stream has not started,” “Reconnecting,” and “Stream ended” states.
- Provide score-only fallback when video fails.
- Provide an “Open in provider” fallback for unsupported browsers.
- Disable autoplay with sound; use `playsinline` on mobile.
- Add captions when operationally possible.
- Document whether employee/participant consent covers live broadcast and recordings.
- Define recording retention and deletion.
- Do not expose viewer identity to analytics without a documented privacy basis.
- Monitor ingest health, player errors, startup time, rebuffering, and end-to-end latency.

### 10.6 Score overlay for the broadcast

If the broadcast needs a visible scoreboard, add a read-only overlay route:

```text
/overlays/matches/{id}?theme=broadcast
```

OBS can load it as a browser source. It should subscribe to the same score event stream as the website, use a transparent background, have no admin controls, and require a revocable overlay token when the event is private.

## 11. Hardcoded versus configuration evaluation

### 11.1 Values that must become mutable database configuration

| Current value | Current location | Target owner |
|---|---|---|
| Enabled sports | Not represented | `tournament_sports` |
| Divisions/categories | `config.json`, seed data, templates | `divisions` |
| Groups and stages | `config.json`, `FINAL` string, templates | `stages`, `groups` |
| Tournament name and dates | `config.json`, templates, seed generator | `tournaments` |
| Timezone and locale | Fixed UTC+7 and `WIB` strings | tournament IANA timezone and locale |
| Venues and courts | `Synergy Room`, `Meja 1` | `venues`, `courts` |
| Competition and scoring profile | `group == FINAL` and static rules | versioned rule profile |
| Standings points and tie-breaks | `utils.py` and prose | standing policy |
| Bracket/qualification logic | Table Tennis route/template logic | stage qualification configuration |
| Feature availability | Always-on comments/voting/gallery | feature flags per tournament/sport |
| Comments/vote cutoffs and limits | Python constants | moderation/engagement policy |
| Announcement lifetime and scope | one global JSON value | announcements table |
| Streaming provider and playback reference | absent | stream session/provider config |
| Branding and hero artwork | CSS and Table Tennis images | branding profile and asset records |
| Per-team colors | team JSON | optional entrant branding with validated contrast |

### 11.2 Values that belong in environment/secret management

- `DATABASE_URL`.
- Flask secret key.
- Initial bootstrap administrator credentials, only for first-run provisioning.
- S3 endpoint, region, bucket, access key, and secret.
- Public asset base URL.
- Streaming provider API credentials.
- Streaming webhook secret.
- Signed-playback secret.
- Email/notification provider credentials if added.
- Analytics measurement ID by deployment environment.
- Error-monitoring DSN.

No secret should have a usable source-code default.

### 11.3 Values that should remain code

- Allowed state-machine transitions.
- Permission checks.
- Input validation and sanitization.
- Scoring-engine algorithms.
- Provider adapter interfaces.
- Webhook verification algorithms.
- Database transaction boundaries.
- Audit behavior.
- Accessibility behavior for dialogs and navigation.
- Error-handling and retry rules.

Business values may select a supported code path; configuration must not contain executable logic.

### 11.4 Current hardcoding hotspots to remove

- `ganda_putra` and `ganda_campuran` checks throughout `app.py`.
- Table-tennis-only `bracket()` route.
- Fixed champion blocks on Home and Standings.
- Fixed two-category Home statistic.
- Fixed category options in Schedule and Recap.
- Static Table Tennis rules page.
- `Meja 1` disabled court fields.
- July-only Home date formatting.
- Fixed UTC+7 timezone and `WIB` suffixes.
- Fixed vote emojis, vote count, and one-hour cutoff.
- Fixed comment count and length.
- Fixed maximum three match photos.
- Fixed 1,200-pixel/75-quality media processing.
- Supabase host repeated in upload and delete functions.
- PostgreSQL schema named `tennis`.
- Table Tennis-specific group shuffle routes.
- Red/pink variables, status colors, canvas colors, metadata, and Open Graph generator colors.
- Absolute local paths in `_make_favicon.py`.

## 12. Complete user-cycle evaluation

### 12.1 Current cycle

| Step | Result | Observation |
|---|---|---|
| Discover event | Partial | Navigation is clear on desktop, but the Home status is incorrect and the page is Table Tennis-specific. |
| Find schedule | Pass | Search and filters work, but sport does not exist and category options are hardcoded. |
| Open match | Pass | Cards and modal open correctly. Modal keyboard focus management fails. |
| Admin login | Functional, insecure | Shared default password, no rate limit, no CSRF, open redirect. |
| Find admin match | Partial | Desktop table works; mobile needs horizontal scrolling and truncated search. |
| Set match Live | Pass | Public Live page updates after save. There is no schedule/status consistency validation. |
| Enter score | Functional, unsafe | Raw numeric fields work but allow rule-invalid values and have no accessible names. |
| Complete match | Pass | Winner and Completed status are calculated. Invalid extra games are still accepted. |
| Update recap | Pass | Completed match appears. |
| Update standings | Functional, incomplete | Basic totals update; tie-break algorithm disagrees with published rules. |
| Remove from Live | Pass | Match disappears from current-live list. |
| Audit who changed it | Fail | No named user or audit log. |
| Correct an error safely | Fail | No event history, reasoned correction, or optimistic lock. |
| Stream video | Fail | No player, stream model, provider integration, or operator controls. |

### 12.2 Recommended future cycle

1. Manager creates the tournament and enables three sports.
2. Manager creates divisions and selects versioned rule/standings profiles.
3. Entrants and members are registered once and assigned to divisions.
4. Scheduler generates or imports matches and runs participant/court conflict checks.
5. Manager reviews and publishes the schedule.
6. Stream operator prepares court streams and verifies ingest readiness.
7. Participants check in; scorekeeper opens a filtered “Today / My Court” screen.
8. Scorekeeper starts the match; state changes to Live and activates the correct stream/scoreboard.
9. Scorekeeper records validated events with immediate save/conflict feedback and undo.
10. Viewers receive live score events and video independently; one can fail without breaking the other.
11. Scorekeeper finishes the match; the engine validates the result.
12. Winner, standings, qualification, bracket, recap, and next-match state update in one transaction.
13. A correction requires permission, reason, and audit history.
14. Stream ends or moves to the next court match; recording enters moderation.
15. Tournament completion is explicit and allowed only when incomplete-match checks pass.

## 13. Usability, accessibility, and responsive requirements

### 13.1 Current usability problems

- Mobile Home hero text is difficult to read against sport-specific artwork.
- Fixed comments and bell overlap content.
- Multiple links and controls are below the recommended 44 x 44 CSS pixel target.
- Calendar match rows are approximately 15 pixels high on mobile.
- Filter controls are compact and wrap into a visually dense block.
- Admin table requires significant horizontal scrolling.
- Scorekeeper has no “saved” state or protection from accidental navigation.
- Empty Live page emphasizes “today” even when a manually-live past-dated match can exist.
- Live animation and red dot appear even when nothing is live.
- “Admin” remains part of public primary navigation for all users.
- English `Group` and Indonesian labels are mixed inconsistently.

### 13.2 Accessibility acceptance requirements

- Add a skip link and semantic main heading on every page.
- All inputs have programmatic labels and errors linked with `aria-describedby`.
- Score controls announce sport unit, entrant, and sequence.
- Dialogs set initial focus, trap focus, close on Escape, make background inert, and restore focus.
- Mobile menu changes label between Open and Close, closes on Escape, and removes hidden links from tab order.
- Announcement and score changes use appropriate live regions without excessive announcements.
- All interactive controls meet minimum target size and visible focus requirements.
- Tables include captions and correctly scoped headers.
- Color is never the sole signal.
- Motion can be reduced globally.
- Video includes accessible title, captions where available, keyboard controls, and a non-video fallback.
- Run automated accessibility checks plus manual keyboard and screen-reader tests.

## 14. Performance, reliability, and observability

### 14.1 Performance

- Query only the current sport/date/status rather than loading all teams, matches, and config on every request.
- Remove duplicate config loads caused by both route context and the global context processor.
- Cache stable tournament/sport/rule metadata.
- Use pagination for archive, gallery, and comments.
- Generate and cache Open Graph images by match version.
- Use thumbnails and responsive images.
- Replace full-collection 15-second polling with SSE/delta updates and polling fallback.
- Lazy-load the video player only on Live or match pages.
- Avoid loading analytics and provider scripts when the feature is disabled.

### 14.2 Reliability

- Add database health and migration checks.
- Add background jobs for media transforms and provider operations.
- Add retry policies with limits and dead-letter handling for webhooks.
- Use idempotent writes.
- Maintain score and schedule audit history.
- Define backup retention and perform restore drills.
- Support graceful degradation when video, analytics, object storage, or real-time delivery is unavailable.

### 14.3 Observability

Track:

- Request error rate and latency by route.
- Database transaction failures and version conflicts.
- Score-event write latency.
- Live-viewer SSE connection count and reconnects.
- Stream webhook age, ingest health, and playback failures.
- Player startup time and rebuffering.
- Login failures and rate-limit events.
- Moderation backlog.
- Media processing failures.
- Audit events for destructive operations.

## 15. Test strategy

### 15.1 Unit tests

- Valid and invalid Table Tennis games, deuce, decisive-game stop, and Best of 3/5.
- Current and alternate Badminton profiles, deuce, cap, and decisive-game stop.
- Padel advantage/golden-point games, sets, tie-breaks, and deciding-set variants.
- Walkover after no score and partial score.
- Two-way and multi-way standings ties.
- Qualification and bracket advancement.
- State-machine permissions.
- Date/timezone formatting around midnight and daylight rules where relevant.

### 15.2 Integration tests

- Named-user login/logout/session expiry.
- CSRF rejection.
- Score event -> match completion -> standings -> bracket transaction.
- Concurrent score/comment/reaction writes.
- Schedule conflict rejection.
- Media size/type rejection.
- Signed stream playback and webhook verification.
- Backup and restore.

### 15.3 Browser tests

- Public discovery through result on desktop and mobile.
- Admin/scorekeeper full match cycle for all three sports.
- Reschedule and walkover.
- Multiple simultaneous streams/courts.
- Keyboard navigation, dialogs, mobile menu, filters, and tables.
- Screen sizes at 320, 390, 768, 1024, and desktop widths.
- Reduced motion and high zoom.
- Offline/reconnect and optimistic-lock conflict states.

### 15.4 Load and failure tests

- Expected peak viewers on the Live page.
- SSE reconnect storm.
- Simultaneous score and reaction events.
- Database failover/timeout.
- Provider webhook duplication and reordering.
- Stream unavailable while score remains live.
- Object storage unavailable during photo upload.

## 16. Ordered implementation plan

### P0 — Correctness and safety foundation

1. Freeze new tournament-specific hardcoding.
2. Back up and reconcile current config, generated data, dates, and match results.
3. Fix explicit tournament completion logic.
4. Add score validation to the existing Table Tennis flow immediately.
5. Fix the standings tie-break implementation or correct the published rules; they must match.
6. Remove default admin credentials and open redirect.
7. Add CSRF, secure cookies, rate limits, security headers, and upload limits.
8. Add named users, roles, and audit logs.
9. Introduce migrations and normalized PostgreSQL entities.
10. Add baseline automated tests before migrating behavior.

### P1 — Multi-sport core

1. Add Sport, Division, Stage, Group, Entrant, Court, Match, and Rule Profile entities.
2. Import the current Table Tennis data with preserved match IDs and history.
3. Implement Table Tennis, Badminton, and Padel scoring engines.
4. Implement policy-based standings and qualification.
5. Add sport-aware schedule and match APIs.
6. Replace hardcoded bracket/champion logic with stage-driven rendering.
7. Build the event hub, sport switcher, sport-aware Schedule, Standings, and Rules.
8. Build mobile scorekeeper mode.
9. Add schedule and participant conflict checks.

### P2 — Design system and live delivery

1. Apply the green/blue/white token system.
2. Remove inline styles and undefined variables.
3. Replace Table Tennis-only artwork and metadata.
4. Complete responsive and accessibility remediation.
5. Add provider-independent stream sessions and admin controls.
6. Integrate the selected streaming provider and webhooks.
7. Build the Live player, court switcher, score-only fallback, and OBS overlay.
8. Add recordings to moderated Media.
9. Add stream/player observability.

### P3 — Operational maturity

1. Add notification/reminder integrations if required.
2. Add check-in and court assignment workflows.
3. Add CSV import/export and tournament cloning.
4. Add richer analytics with documented privacy controls.
5. Run restore drills, load tests, and production incident exercises.

## 17. Migration approach

1. Create a read-only snapshot of all JSON data and uploaded object references.
2. Reconcile the known final-date and score inconsistencies before import.
3. Create normalized tables and migrations in a separate schema with neutral naming, not `tennis`.
4. Import the current Table Tennis divisions and stages, entrants, matches, comments, reactions, media, and reschedule history into one tournament.
5. Record the exact source JSON checksum and import report.
6. Validate counts, all round-robin pairings, winner calculations, date ranges, and standings.
7. Run the existing public pages against the new repository layer.
8. Introduce sport-aware pages behind a feature flag.
9. Add Padel and Badminton in staging.
10. Run one complete cycle per sport, including corrections, reschedule, walkover, and live delivery.
11. Cut over during a controlled maintenance window.
12. Keep the source snapshot immutable for rollback; do not dual-write indefinitely.

## 18. Release acceptance criteria

The multi-sport release is acceptable only when:

- Table Tennis, Padel, and Badminton are separate sports in data and UI.
- Each sport has at least one configured division and a versioned scoring profile.
- Invalid sport-specific scores cannot be completed.
- Standings and tie-break explanations match published event rules.
- No date/court/player scheduling conflict can be published without an explicit authorized override.
- Public pages can be filtered and shared by sport.
- The mobile scorekeeper can start, score, undo, finish, and correct a match without horizontal scrolling.
- Concurrent writes cannot silently overwrite each other.
- Every admin change identifies the user and appears in an audit log.
- No source-code default grants admin access.
- CSRF, rate limiting, secure cookies, redirect validation, security headers, and upload limits are active.
- The Home page never reports completion while incomplete matches exist unless an authorized tournament status explicitly explains cancellation.
- The interface uses the approved green/blue/white design tokens and contains no unintended red/pink brand styling.
- Keyboard and screen-reader tests pass for navigation, filters, dialogs, score controls, tables, and video.
- Live video failure does not prevent live score viewing.
- Stream keys and signed-playback secrets never reach public clients.
- A completed stream can produce a moderated recording when recording is enabled.
- Automated unit, integration, browser, and concurrency tests pass.
- Backup restore and rollback are tested before production cutover.

## 19. Recommended product defaults and decisions to confirm

Recommended defaults:

- Keep one overall InterSport tournament with three sport modules.
- Allow a person to enter multiple sports/divisions while enforcing schedule conflict checks.
- Use IANA timezone `Asia/Jakarta` rather than raw UTC+7 and hardcoded `WIB` strings.
- Use sport-aware doubles teams, but keep the model capable of singles.
- Use named scorekeeper accounts restricted to assigned sports/courts.
- Disable public comments/reactions by default until moderation and rate limiting are complete.
- Use YouTube Live for the first non-private pilot; use signed Cloudflare Stream or Mux playback when authenticated employee-only access is required.
- Keep recording disabled until consent and retention policies are approved.
- Use English domain keys and localized Indonesian display labels.

Product decisions that must be confirmed before build completion:

- Divisions required for Padel and Badminton.
- Number and location of courts per sport.
- Round-robin, knockout, or mixed stage format per division.
- Event-specific Padel scoring variant.
- Badminton profile approved for the event date.
- Standings point and tie-break policy per division.
- Whether streams are public, unlisted, or authenticated.
- Whether recordings, comments, reactions, and participant names may be publicly visible.
- Who can correct completed results and how long the correction window remains open.
- Required Indonesian/English localization scope.

## 20. Reference sources for rule and streaming design

- [ITTF Statutes 2026 — Laws of Table Tennis](https://documents.ittf.sport/sites/default/files/public/2026-02/2026_Statutes_v1_consolidated_clean.pdf)
- [BWF Laws of Badminton](https://system.bwfbadminton.com/documents/folder_1_81/Statutes/CHAPTER-4---RULES-OF-THE-GAME/SECTION%204.1-%20Laws%20of%20Badminton.pdf)
- [BWF Alternative Laws of Badminton](https://system.bwfbadminton.com/documents/folder_1_81/Statutes/CHAPTER-4---RULES-OF-THE-GAME/Section%204.1.4%20-%20Alternative%20Laws%20of%20Badminton.pdf)
- [FIP Rules of Padel](https://www.padelfip.com/wp-content/uploads/2025/12/FIP_Rules-of-Padel-1.pdf)
- [YouTube IFrame Player API](https://developers.google.com/youtube/iframe_api_reference)
- [YouTube Live Streaming API](https://developers.google.com/youtube/v3/live/docs)
- [Cloudflare Stream live video](https://developers.cloudflare.com/stream/stream-live/)
- [Mux live streaming guide](https://www.mux.com/docs/guides/start-live-streaming)

## 21. Final recommendation

Do not begin with the color change or with iframe insertion alone. First establish the neutral multi-sport model, valid score engines, transactional writes, permissions, and auditability. Then rebuild the public and scorekeeper interfaces using the green/blue/white design system. Add live streaming through a provider adapter after match, court, and status data are trustworthy.

This order prevents a visually improved interface from hiding incorrect results, insecure administration, or a data model that still assumes every contest is Table Tennis.
