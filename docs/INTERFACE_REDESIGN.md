# Interface Redesign — Blue, Green, and White

## Direction

The interface uses a modern tournament command-center aesthetic: deep blue provides structure,
green signals active and successful states, white glass surfaces keep dense tournament information
light and readable, and restrained blur separates layers without hiding content.

## Core palette

| Role | Token | Value |
|---|---|---|
| Deep canvas | `--navy-950` | `#03202f` |
| Primary blue | `--blue-800` | `#075985` |
| Action blue | `--blue-700` | `#0369a1` |
| Primary green | `--green-700` | `#047857` |
| Live accent | `--green-500` | `#10b981` |
| Soft blue | `--blue-100` | `#e0f2fe` |
| Soft green | `--green-100` | `#d1fae5` |
| Main text | `--text` | `#102a43` |
| Muted text | `--muted` | `#607d8b` |

Primary buttons use the darker `--blue-700` to `--green-700` gradient so white button labels keep
strong contrast. Red is no longer part of the brand system; live states use green and warnings use
amber only when their meaning requires it.

## Component rules

- Navigation is sticky translucent glass with an explicit active route and a 44 px mobile menu target.
- Hero panels use blue/green depth, a subtle grid, concise tournament status, and responsive metadata.
- Cards, tables, filters, forms, brackets, dialogs, and admin surfaces use the same border, radius,
  blur, and shadow language.
- Tables scroll inside their own container on narrow screens; the page itself must never overflow.
- Scorekeeper point targets stay at least 104 px high on a 390 px viewport.
- Hidden controls remain hidden even when component display rules use flex or grid.
- Focus rings, a skip link, reduced-motion behavior, and solid-background blur fallbacks are included.

## Signature arena header

The shared header uses an **Arena Command Bar** concept so the product has a recognizable identity
before the page content begins:

- A slim navy signal rail identifies the competition system, venue context, and connected-arena
  state without competing with the main navigation.
- The asymmetric logo frame, compact `26` edition marker, and tournament-series typography create a
  repeatable brand signature without introducing a new image asset.
- Desktop navigation behaves like an operator console: numbered routes sit inside one translucent
  control deck, while the active route uses the blue-to-green competition gradient and a small
  illuminated state marker.
- On mobile, the header remains compact and the navigation opens as a two-column arena panel with a
  dimmed page scrim. Outside click, route selection, viewport changes, and Escape all close it safely.
- The active route exposes `aria-current`, menu items are removed from keyboard order while collapsed,
  and the original announcement, admin, logout, and sport-switcher contracts remain intact.
- The sticky sport switcher uses the actual two-level header height at desktop and mobile breakpoints,
  preventing overlap as the user scrolls between competition views.

## Closing arena footer

The footer closes every public page as a functional arena surface instead of a legal-text block:

- Tournament identity, event dates, venue, and playing session form the primary information zone.
- Public competition and exploration links are grouped separately for faster navigation at the end of
  long schedule, standings, and recap pages.
- A dedicated Tournament Command Center card identifies the separate organizer channel without
  exposing its login URL on public pages. When authenticated, it changes to dashboard and scorekeeper
  shortcuts.
- The final system rail combines ownership context, a restrained disclaimer, and an active-system state.
- Desktop uses a three-zone grid; tablet reorganizes navigation into a horizontal directory; phone
  layouts stack into large, readable touch targets.

## Admin gateway

The login screen continues the command-center language with a protected-access introduction, concise
capability overview, clear password field, visibility toggle, lockout notice, and route back to the
public tournament. Local credentials load from the Git-ignored `.env`; only a Werkzeug password hash is
stored, while production credentials remain the responsibility of the hosting secret manager.

## Schedule experience

The schedule is designed as a competition operations board rather than a plain list:

- The masthead summarizes total, upcoming, live, and completed matches and visualizes tournament
  progress without requiring the user to scan every card.
- Search and filters live in one glass workbench, with an active-filter counter and a clear result
  summary. Existing query-string filter behavior is preserved.
- Matches are grouped into dated timeline sections. Each section exposes its match count and keeps
  the date visible as a strong orientation marker.
- Cards use a symmetric team-versus-team composition, prominent scores, compact stage/status labels,
  court and time metadata, and a clear detail affordance. Live patch targets and voting controls keep
  their existing data attributes.
- The desktop grid presents three cards when space permits; tablet and phone views collapse cleanly
  to two and one column without page-level overflow.

## Match center

The match popup is a focused match center shared with the full match-detail page:

- A blue/green arena header presents competition context, teams, scores, status, and venue metadata.
- Score breakdowns, documents, notes, and match history use distinct content sections instead of one
  dense block. Scheduled matches receive an intentional pre-match waiting state.
- The fan zone remains visible as a supporting column on desktop and moves below match information on
  narrow screens.
- The dialog reports loading and failure states, moves focus to the close control, traps keyboard focus
  while open, closes with Escape, and restores focus to the match card that opened it.
- The modal becomes an edge-to-edge mobile sheet at phone widths while keeping its content scrollable
  and the underlying page locked.

## Architecture

- `static/css/style.css`: existing component structure and behavior contracts.
- `static/css/redesign.css`: palette, glass system, responsive refinements, and component overrides.
- `templates/base.html`: theme metadata, stylesheet loading, skip-navigation target, and modal shell.
- `templates/index.html`: redesigned hero hierarchy and semantic tournament-status elements.
- `templates/jadwal.html`: schedule masthead, filter workbench, day timeline, and responsive result grid.
- `templates/_match_card.html`: reusable competition card and live-update targets.
- `templates/_match_detail_content.html`: shared match-center composition for modal and full-page views.
- `static/js/main.js`: modal loading, keyboard handling, focus restoration, and AJAX form refresh.

Keeping the visual layer separate makes it possible to tune or replace the brand without risking
scoring, filtering, live polling, modal, or admin behavior.

## Verification baseline

The redesign is checked at 1280×720 and 390×844 across the home page, schedule, live, standings,
bracket, calendar, recap, gallery, rules, match detail, 404 page, admin dashboard, match editor,
scorekeeper list, and scorekeeper console. The baseline requires:

- no document-level horizontal overflow;
- controlled inner scrolling for wide tables;
- no visible browser-console errors;
- responsive navigation that opens and closes correctly;
- schedule filters and exact result-count feedback remain compatible with server-side tests;
- match-center loading, close, Escape, focus-trap, and focus-restoration behavior;
- usable touch targets and focus states;
- all existing automated application tests remaining green.
