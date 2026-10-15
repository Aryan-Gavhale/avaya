# Anvaya Dental Care — clinic site + admin CMS

A dentist website where nothing on the page is hard-coded. Every heading, paragraph,
image, treatment, clinician, clinic, FAQ, colour and menu item is a row in SQLite that
the owner edits from an admin panel. Reviews come live from Google, and the same panel
runs enquiries as a small CRM and EMI as a working ledger with receipts.

Flask 3, stdlib `sqlite3`, Jinja, hand-written CSS and one plain deferred script per
surface. No build step, no JS framework, no npm.

```
python app.py reset      # create the database and load the demo practice
python app.py            # http://127.0.0.1:8120
```

Sign in at `/admin` with `owner@anvayadental.in` / `anvaya2026` and change the password
under **Your account** straight away.

---

## Setup

Python 3.10 or newer (built and checked on 3.12) and three libraries:

```
pip install -r requirements.txt
```

| Command | What it does |
| --- | --- |
| `python app.py` | Dev server on port 8120 with the reloader |
| `python app.py serve --no-reload` | Same, single process (what the check scripts expect) |
| `python app.py seed` | Apply the schema, then load the demo practice only if no pages exist |
| `python app.py seed --force` | Clear the content, enquiry and EMI tables and reload the demo. Keeps users and settings |
| `python app.py reset` | Delete the database file, then seed |
| `python app.py user <email> <name> <password> [role]` | Add or update an admin account |

### Configuration

Defaults live in `DEFAULT_CONFIG` in `app.py`, are overridden by `config.json` if you
create one, and then by `CLINIC_*` environment variables (`CLINIC_PORT`,
`CLINIC_SECRET_KEY`, and so on). `config.json` is gitignored, and
`config.example.json` is deliberately never read at runtime, so a placeholder secret can
never become the live one just because nobody copied the file.

The defaults are meant to be safe rather than convenient:

| Setting | Default | Why |
| --- | --- | --- |
| `secret_key` | generated into `db/secret.key` | no two installations share a key, so nobody can forge a session cookie from the source |
| `owner_password` | generated, printed once, written to `db/first-login.txt` | there is no password in this repository to try |
| `debug` | `false` | the Werkzeug debugger is a remote shell; it is also forced off if `host` is not loopback |
| `https_only` | `false` | set `true` behind TLS to get `Secure` cookies and HSTS |
| `trusted_proxies` | `0` | how many `X-Forwarded-For` hops are yours; see below |

Both generated files are gitignored. Delete `db/first-login.txt` once you have signed in
and set your own password.

**`trusted_proxies` matters.** Rate limits and the login lockout are only as trustworthy
as the address they count against. With `0`, the app uses `remote_addr` and ignores
`X-Forwarded-For` entirely, because a caller can rotate that header on every request and
walk straight through any per-IP limit. Behind nginx or a load balancer, set it to the
number of proxies you control so the real client address is read from the right position
in the chain.

### Deploying

It is a normal WSGI app: `create_app()` in `app.py`. Behind gunicorn or waitress, leave
`debug` false, set `https_only` true, set `trusted_proxies` to your hop count, and put
`static/uploads` and `db/clinic.db` on persistent storage. SQLite is the right call for
one practice; the whole database is a single file you can copy.

---

## The public site

One `pages` row per URL, each holding an ordered list of typed `sections`. A section's
type decides both the admin form and the partial in `templates/public/sections/`, which
is what makes "add, edit, reorder, delete a section" real rather than cosmetic.

Fifteen section types ship: `hero`, `trust`, `stats`, `services`, `about`, `process`,
`gallery`, `doctors`, `reviews`, `emi`, `branches`, `faq`, `enquiry`, `cta`, `richtext`.
Each is declared once in `core/sections.py` with its own fields; adding a sixteenth means
a dict entry and a partial.

Seeded pages: home, treatments, about, EMI and payment, contact, plus a detail page per
treatment at `/treatments/<slug>` and a generated `sitemap.xml` and `robots.txt`.

Animation is clinical rather than showy: `IntersectionObserver` reveals with staggered
siblings, counters on the trust numbers, a scroll progress line, header state change,
subtle image parallax, and a lightbox gallery with arrow-key navigation. Everything has a
`prefers-reduced-motion` path that shows content immediately and disables parallax and
counters. Theme colours, both fonts and the corner radius are written into the page as
custom properties from Settings, so rebranding is a form rather than a code edit.

The enquiry form and the EMI application both post through `fetch` and confirm in place.
Each carries a CSRF token and a signed `form_token` stamping when the form was served;
the server rejects a post with no CSRF token, and treats a missing or too-fresh stamp as
automated. The stamp is signed rather than kept in the session so it still works with
JavaScript off, and cannot be skipped by simply not asking for one.

On top of that: a honeypot field, a soft per-IP threshold that flags rather than drops
(so a noisy real patient is still reachable in the Spam tab), and hard per-IP and
whole-site hourly ceilings that answer 429 instead of writing another row.

---

## On a phone

Below 760px both skins become applications rather than narrow pages. Two stylesheets do
it — `static/css/phone.css` for the site and `static/css/admin-phone.css` for the admin
panel — each loaded with `media="(max-width: 760px)"`, so nothing about the desktop
layout is negotiated at runtime and neither file costs a wider screen anything.

The public site gets a compact app bar that slides away as you read and returns the
moment you scroll back, call and WhatsApp as icon buttons in the bar, card grids turned
into snap-scrolling rails, and a five-slot bottom tab bar with the appointment action
raised in the middle. The burger and the sticky call bar step aside; the rest of the
navigation lives in a bottom sheet that opens from **More**, traps focus, and closes on
Escape or a tap above it.

The admin panel replaces the dark sidebar with the same pattern: bottom tabs for
Dashboard, Enquiries, EMI and Website, a **More** sheet holding all twenty screens
grouped as in the sidebar, and a back chevron on anything below the top level. Every
list table collapses into cards — each cell prints its column name from `data-label`,
the actions form a footer, the bulk checkbox moves to the corner — so nothing has to be
scrolled sideways to be read. Reordering, which needs a mouse to drag, grows a pair of
move buttons that `admin.js` adds only on touch. Primary actions float as a pill above
the tabs, the save bar and the bulk bar dock straight on top of them, and every field is
44px tall at 16px type, which is the size iOS needs to not zoom the page on focus.

---

## Admin panel

Its own dense layout at `/admin`, deliberately unlike the public skin.

- **Dashboard** — enquiries today and this week, the pipeline by status, EMI outstanding
  and overdue, the next 30 days of instalments, the live Google rating, recent activity.
- **Pages and sections** — page CRUD with its own meta title, description and social
  image, then a section builder with drag reorder, publish toggles that save without a
  reload, duplicate, per-type editors and a "view on site" link that lands on the right
  anchor.
- **Treatments** and categories — fee band, chair time, visits, EMI eligibility, featured
  flag, photograph. **Clinicians**, **Clinics** (with per-clinic hours and Place ID),
  **FAQs**, **Menus** for the header and footer, **Curated quotes**.
- **Media library** — multi-file drag-drop upload, Pillow-generated WebP variants (1200px
  medium for the page, 480px thumb for admin grids), alt text, search, a usage check
  before delete, and an importer for the clinic's Google Place photos. A picker modal is
  reachable from every image field.
- **Google reviews** — connection screen, Place ID search, test fetch, sync log.
- **Enquiries** — status tabs and filters by date, treatment, clinic, assignee and
  priority, search, bulk status change and assignment, CSV export, and a detail view with
  the activity timeline, internal notes, WhatsApp and mail links, spam marking and
  "convert to an EMI application".
- **EMI** — plans CRUD that directly drives the public calculator, applications through
  submitted → under review → approved → active → completed (with rejected, defaulted and
  cancelled), a generated instalment schedule, payment recording against an instalment, a
  printable receipt, void with a reason, an overdue view and a ledger export.
- **Settings** — practice and contact, social links, theme, SEO, enquiry wording,
  EMI wording and receipt numbering, opening hours and closures.
- **Users** (owner only), **Your account**, **Activity log**, **Backup**.

Three roles: **Owner** reaches everything including users; **Administrator** is the same
minus user management; **Front desk** sees only enquiries and EMI.

Front desk can raise applications, take payments and print receipts, but not set plan
terms, approve or reject an application, void a receipt or delete a record — those need
the `emi_admin` permission that only Owner and Administrator hold, so the same person
cannot both write the terms and sign them off. The buttons are hidden as well as refused.

Passwords are hashed with `werkzeug.security` (PBKDF2-SHA256, 260k iterations) and an
unknown email is compared against a dummy hash so response time does not reveal which
accounts exist. Sessions are signed cookies, rotated on sign-in. Every mutating POST
carries a CSRF token, including sign-in and sign-out. Eight failed sign-ins from one
address, or twelve against one account, locks out for 15 minutes.

Every response carries a Content-Security-Policy (`script-src 'self'` plus a per-request
nonce for the handful of inline admin scripts), `nosniff`, `X-Frame-Options: DENY` and a
referrer policy; admin pages are additionally `Cache-Control: no-store`.

Every create, update and delete is written to `audit_log` with the before and after JSON,
which is what the Activity log reads.

### Adding an admin field

Most admin screens are declarative. A resource is a table plus a list of `Field` specs in
`blueprints/admin_content.py`; `core/crud.py` generates the list, form, save, delete,
toggle and reorder routes from it, and the same renderer draws the settings screens from
the groups in `blueprints/admin_settings.py`. Adding a field to Treatments means one
`Field` line and one column in `db/schema.sql`.

---

## Google reviews

`services/google_reviews.py` exposes one provider interface with two implementations,
chosen on the **Google reviews** screen: Google with a fallback to curated quotes,
Google only, or curated quotes only.

1. Create a Google Cloud project, enable **Places API (New)**, and make an API key. Note
   that reviews are billed at the Enterprise + Atmosphere tier — the admin screen says so
   too — and that Places returns **at most five reviews**.
2. Paste the key into **Google reviews** and press **Save connection**. Then search for
   the practice by name and city: the search calls
   `POST https://places.googleapis.com/v1/places:searchText` and lists the candidates with
   their address and rating, and **Use this one** stores that `place_id`.
3. Press **Sync now** to test. The screen shows the rating, the review count, the response
   status, the cached reviews and a sync log, and any review can be kept permanently as a
   curated quote.

Reviews are read from `GET https://places.googleapis.com/v1/places/{PLACE_ID}` with
`X-Goog-Api-Key` and a field mask of `id,displayName,rating,userRatingCount,googleMapsUri,reviews`.

Compliance is built in rather than bolted on. Review text lives only in
`google_reviews_cache`, which expires on `google.cache_ttl_minutes` (six hours by
default); `place_id` is the only value stored indefinitely. Each review renders the
author's name, avatar and profile link, the block carries its "reviews from Google"
attribution and states how Google orders and filters them, and a "write a review" link
points at `search.google.com/local/writereview?placeid=...`. Place photos are proxied
live through `/media/google-photo/<ref>` rather than stored, so owner-uploaded images are
the right choice for the permanent gallery.

Until a key is present — and whenever Google errors, hits quota or returns nothing above
the configured minimum rating — the section falls back to the curated quotes under
**Curated quotes**, so the page never renders empty. The seeded heading is deliberately
source-neutral for that reason.

If your network sits behind a TLS-inspecting proxy, set `"google_verify_tls": false` in
`config.json` to let `requests` through.

---

## Data model

25 tables, created idempotently from `db/schema.sql` with a version in `meta`.

- **Content** — `settings`, `pages`, `sections`, `services`, `service_categories`,
  `doctors`, `branches`, `faqs`, `nav_items`, `media`, `galleries`, `gallery_items`
- **Reviews** — `testimonials` (curated), `google_reviews_cache` (short TTL, transient),
  `review_sync_log`
- **Funnel** — `enquiries`, `enquiry_events`
- **EMI** — `emi_plans`, `emi_applications`, `emi_installments`, `payments`
- **Ops** — `users`, `login_attempts`, `audit_log`, `meta`

Settings are a typed key/value table read through `core/settings.py`, cached per request
and reachable in any template as `S('brand.name')`.

EMI is a full in-house ledger: plans, applications, computed schedules, payment recording
and receipts. No payment gateway is wired up — there is no Razorpay checkout — so staff
record each payment with its method and an optional provider reference. A gateway can be
added on top of `payments` later without touching the schedule logic.

---

## Backup and restore

**Backup** in the sidebar writes a timestamped zip into `backups/` containing a consistent
copy of the database (taken through SQLite's backup API, so it is safe while the app is
running) and everything in `static/uploads`. The same screen downloads or restores one; a
restore copies the current database aside as `clinic.db.pre-restore` before overwriting
it, and signs you out so you come back on the restored data.

By hand: stop the app, copy `db/clinic.db` and `static/uploads/`, done.

---

## Verification

Two scripts, both of which need the dev server running:

```
python app.py serve --no-reload      # in one terminal
python check_routes.py               # in another
python check_browser.py all
```

`check_routes.py` is stdlib only. It signs in, GETs all 65 public and admin routes, then
exercises the write paths end to end — an enquiry, an EMI application through schedule,
payment, receipt and void, treatment and section CRUD, settings, an upload, a backup. It
also asserts the hardening holds: public posts without a CSRF token are refused, a post
with no form stamp is kept but flagged, logout cannot be a GET, a malformed reorder
payload is a 400 rather than a 500, a text file renamed `.png` is turned away, the CSP
and `no-store` headers are present, and the Google photo proxy refuses a photo name it
never imported. It cleans up its own rows and restores any setting it touched.

`check_browser.py` needs Playwright (`pip install playwright && playwright install
chromium`). It drives Chromium at 1440×900 and 390×844 over the public site, a
reduced-motion pass and the admin panel: every interactive piece, console errors, failed
requests, horizontal overflow, broken images, clipped text, WCAG AA contrast, tap-target
size, the first tab stop and focus rings. The two phone passes also check the app shell —
tabs docked and marking the current screen, the More sheets, tables rendered as cards,
the floating action button and save bar clearing the tabs, and fields large enough that
iOS will not zoom. Screenshots land in `_shots/`. Pass one of `desktop`, `mobile`,
`motion` or `admin` to run a single pass.

Both report `0 problem(s)` on the seeded database — 95 browser checks and 103 route and
write checks.

---

## Layout

```
dental-clinic-cms/
├── app.py                  # factory, config, Jinja globals, CLI, error pages
├── db/schema.sql           # 25 tables, idempotent
├── db/seed.py              # the demo practice
├── core/                   # db, auth, settings, crud, sections, media, emi, hours, audit, util
├── services/               # google_places.py, google_reviews.py
├── blueprints/             # public.py, admin.py, admin_{content,media,reviews,enquiries,emi,settings}.py
├── templates/public/       # base, home, page, service, sections/*.html
├── templates/admin/        # base, dashboard, crud_list, crud_form, and one per screen
├── static/css/             # site.css, admin.css, and the phone.css / admin-phone.css app layer
├── static/                 # js/site.js, js/admin.js, uploads/
├── check_routes.py         # route and write smoke test
└── check_browser.py        # Playwright pass
```

The demo practice is fictional. Rename it in **Settings → Practice and contact** and the
name, phone numbers, address and schema markup follow everywhere.
