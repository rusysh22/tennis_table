# Multi-role admin accounts

The tournament is run by several operators at once — one per sport plus a
general organizer — so a single shared admin password is not enough. Login at
`/admin/login` now offers an account dropdown; each account is scoped to only
the menus/matches its operator needs.

## Account registry

Defined in `app.py` as `ADMIN_ACCOUNTS` (near the top, alongside the
`app.config.update(...)` block):

| Account | `role` | `sport_key` | Hash env var | Plaintext fallback env var |
| --- | --- | --- | --- | --- |
| General (Semua Cabor) | `general` | — | `ADMIN_PASSWORD_HASH` | `ADMIN_PASSWORD` |
| Admin Galeri | `gallery` | — | `ADMIN_PASSWORD_HASH_GALLERY` | `ADMIN_PASSWORD_GALLERY` |
| Admin Tenis Meja | `sport` | `table-tennis` | `ADMIN_PASSWORD_HASH_TABLE_TENNIS` | `ADMIN_PASSWORD_TABLE_TENNIS` |
| Admin Padel | `sport` | `padel` | `ADMIN_PASSWORD_HASH_PADEL` | `ADMIN_PASSWORD_PADEL` |
| Admin Badminton | `sport` | `badminton` | `ADMIN_PASSWORD_HASH_BADMINTON` | `ADMIN_PASSWORD_BADMINTON` |

An account only appears in the login dropdown (`_configured_accounts()` in
app.py) if its hash or plaintext env var is actually set — a deployment that
only sets `ADMIN_PASSWORD_HASH` behaves exactly as before this feature
existed, just with a single-option dropdown. Plaintext vars are a local/dev
fallback only; always use the `_HASH` variant in production (see
`README.md` for how to generate one).

## Login flow

`admin_login()` (app.py) resolves the posted `account_key` against
`_configured_accounts()` and verifies the password with
`_verify_account_password()` — the same `check_password_hash` /
`compare_digest` logic the single-account version used, just parameterized
per account. On success the session stores:

```python
session["is_admin"] = True
session["admin_key"]   # e.g. "padel"
session["admin_role"]  # "general" | "gallery" | "sport"
session["admin_sport"] # sport_key, or None for general/gallery
session["admin_label"] # display label shown in the sidebar
```

The gallery role always redirects to `/galeri` after login, ignoring any
`?next=`. Every other role keeps the existing `next`-redirect behavior
(defaulting to `/admin`). Rate limiting (`_login_client_key` /
`_record_login_failure` / lockout) is unchanged and still IP-based — it
applies per client regardless of which account they're attempting.

## Permission enforcement

Two layers, both in `app.py`:

**1. Endpoint-level, via one `before_request` hook** — `enforce_admin_role_scope()`
blocks by Flask endpoint name using two static sets:
- `GENERAL_ONLY_ENDPOINTS` — Sites, Peserta & Tim, Divisi & Cabor, Aturan
  Pertandingan, Generate Jadwal, Live & Pengumuman, Utilitas & Reset, License.
  A `sport` account hitting any of these is bounced back to `/admin` with a
  flash message.
- `GALLERY_ENDPOINTS` — just the two gallery upload/delete POST routes. A
  `gallery` account hitting anything else under `/admin` is bounced to
  `/galeri`.

This is a single hook rather than per-route decorators, so adding a new
general-only admin route later just means adding its endpoint name to
`GENERAL_ONLY_ENDPOINTS` — no new decorator needed.

**2. Per-record, via `_assert_sport_access(sport_key)`** — endpoint-level
blocking alone doesn't stop a `sport` account from opening another sport's
match by guessing its ID, since Dashboard/Scorekeeper/Edit-Match are shared
endpoints. `_assert_sport_access` aborts 403 (or, in the JSON scorekeeper
action endpoint, returns a 403 JSON body) when the record's `sport_key`
doesn't match `session["admin_sport"]`. Called from:
- `admin_dashboard` — filters the match list itself rather than aborting.
- `scorekeeper_index` — forces the sport filter and hides other sports from
  the filter dropdown.
- `scorekeeper_match`, `scorekeeper_action`, `admin_edit_match` — checked
  against the loaded match's `sport_key`.
- `admin_upload_champion_photo` — checked against the division's `sport_key`.

Also note: `enforce_license_interception` sends inactive-license redirects to
`admin_license` only for the `general` role (since only General can act on
license/billing); `sport`/`gallery` accounts fall through to the normal
public `license_lockout` page instead, avoiding a redirect loop against
`GENERAL_ONLY_ENDPOINTS`.

## Sidebar / UI gating

`templates/admin/_layout.html` wraps every general-only nav group in
`{% if admin_role != 'sport' %}` (Sites, Peserta & Tim, Divisi & Cabor,
Aturan Pertandingan, Generate Jadwal, Live & Pengumuman, Sistem & Lisensi,
Utilitas) and hides the license-status banner from `sport` accounts, since
they can't act on it. `templates/admin/dashboard.html`'s topbar quick actions
("Peserta", "Generate Jadwal") and empty-state CTA are hidden the same way.
`templates/admin/scorekeeper_index.html` disables the sport filter dropdown
entirely for `sport` accounts (server already forces/filters to their one
sport, so the dropdown can't imply a wider view than what's actually
returned). The `gallery` role never reaches this admin shell at all — the
`before_request` hook redirects it to `/galeri` before any admin template
renders.

`admin_role` / `admin_sport` / `admin_label` are available in every template
via `inject_globals()` (app.py context processor), defaulting `admin_role` to
`"general"` whenever `is_admin` is true but the session predates this
feature — so no one gets accidentally locked out on deploy.

## Adding or rotating a password

See the "Login admin" section in `README.md` for the
`generate_password_hash(...)` one-liner and the full env var table. Rotate a
password by generating a new hash and replacing the corresponding
`ADMIN_PASSWORD_HASH_*` value — no code change required.

## Adding a 6th account or a new general-only page

- New account: add an entry to `ADMIN_ACCOUNTS` in app.py with its own
  `key`/`label`/`role`/`sport_key`/env var names, and set its hash env var.
- New general-only admin route: add its endpoint name to
  `GENERAL_ONLY_ENDPOINTS` and wrap its sidebar link in
  `{% if admin_role != 'sport' %}`.
- New sport-scoped route operating on a match/division: call
  `_assert_sport_access(...)` with that record's `sport_key` right after
  loading it.
