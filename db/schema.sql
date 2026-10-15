-- ============================================================================
-- Dental clinic CMS — schema
-- Applied with executescript() on every boot; every statement is idempotent.
-- Column names avoid SQLite keywords (before_json / after_json, not before/after).
-- ============================================================================

CREATE TABLE IF NOT EXISTS meta (
  key   TEXT PRIMARY KEY,
  value TEXT
);

-- ── people ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
  id            INTEGER PRIMARY KEY,
  email         TEXT NOT NULL UNIQUE,
  name          TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  role          TEXT NOT NULL DEFAULT 'staff',   -- owner | admin | staff
  is_active     INTEGER NOT NULL DEFAULT 1,
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  last_login_at TEXT
);

CREATE TABLE IF NOT EXISTS login_attempts (
  id         INTEGER PRIMARY KEY,
  ip         TEXT,
  email      TEXT,
  ok         INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_login_attempts_ip ON login_attempts(ip, created_at);

-- ── settings ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS settings (
  key        TEXT PRIMARY KEY,
  value      TEXT,                               -- JSON encoded
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ── media ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS media (
  id         INTEGER PRIMARY KEY,
  filename   TEXT,                               -- stored original (local uploads)
  medium     TEXT,                               -- 1200w webp variant
  thumb      TEXT,                               -- 480w webp variant
  url        TEXT,                               -- set for remote/seed images
  alt        TEXT NOT NULL DEFAULT '',
  title      TEXT NOT NULL DEFAULT '',
  width      INTEGER,
  height     INTEGER,
  bytes      INTEGER,
  mime       TEXT,
  source     TEXT NOT NULL DEFAULT 'upload',     -- upload | remote | google
  credit     TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS galleries (
  id         INTEGER PRIMARY KEY,
  name       TEXT NOT NULL,
  slug       TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS gallery_items (
  id         INTEGER PRIMARY KEY,
  gallery_id INTEGER NOT NULL REFERENCES galleries(id) ON DELETE CASCADE,
  media_id   INTEGER NOT NULL REFERENCES media(id) ON DELETE CASCADE,
  caption    TEXT NOT NULL DEFAULT '',
  sort_order INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_gallery_items ON gallery_items(gallery_id, sort_order);

-- ── pages and sections ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pages (
  id               INTEGER PRIMARY KEY,
  slug             TEXT NOT NULL UNIQUE,
  title            TEXT NOT NULL,
  meta_title       TEXT NOT NULL DEFAULT '',
  meta_description TEXT NOT NULL DEFAULT '',
  og_media_id      INTEGER REFERENCES media(id) ON DELETE SET NULL,
  is_home          INTEGER NOT NULL DEFAULT 0,
  is_published     INTEGER NOT NULL DEFAULT 1,
  sort_order       INTEGER NOT NULL DEFAULT 0,
  created_at       TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sections (
  id           INTEGER PRIMARY KEY,
  page_id      INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
  type         TEXT NOT NULL,
  name         TEXT NOT NULL DEFAULT '',         -- admin-facing label
  anchor       TEXT NOT NULL DEFAULT '',         -- optional #id for nav
  eyebrow      TEXT NOT NULL DEFAULT '',
  title        TEXT NOT NULL DEFAULT '',
  subtitle     TEXT NOT NULL DEFAULT '',
  body         TEXT NOT NULL DEFAULT '',
  data         TEXT NOT NULL DEFAULT '{}',       -- JSON, per-type fields
  sort_order   INTEGER NOT NULL DEFAULT 0,
  is_published INTEGER NOT NULL DEFAULT 1,
  created_at   TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_sections_page ON sections(page_id, sort_order);

-- ── catalogue ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS service_categories (
  id           INTEGER PRIMARY KEY,
  name         TEXT NOT NULL,
  slug         TEXT NOT NULL UNIQUE,
  summary      TEXT NOT NULL DEFAULT '',
  sort_order   INTEGER NOT NULL DEFAULT 0,
  is_published INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS services (
  id           INTEGER PRIMARY KEY,
  name         TEXT NOT NULL,
  slug         TEXT NOT NULL UNIQUE,
  category_id  INTEGER REFERENCES service_categories(id) ON DELETE SET NULL,
  icon         TEXT NOT NULL DEFAULT 'tooth',
  summary      TEXT NOT NULL DEFAULT '',
  body         TEXT NOT NULL DEFAULT '',
  price_from   REAL,
  price_to     REAL,
  duration_min INTEGER,
  sittings     TEXT NOT NULL DEFAULT '',
  media_id     INTEGER REFERENCES media(id) ON DELETE SET NULL,
  emi_eligible INTEGER NOT NULL DEFAULT 0,
  is_featured  INTEGER NOT NULL DEFAULT 0,
  sort_order   INTEGER NOT NULL DEFAULT 0,
  is_published INTEGER NOT NULL DEFAULT 1,
  created_at   TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_services_order ON services(sort_order);

CREATE TABLE IF NOT EXISTS doctors (
  id            INTEGER PRIMARY KEY,
  name          TEXT NOT NULL,
  role_title    TEXT NOT NULL DEFAULT '',
  qualification TEXT NOT NULL DEFAULT '',
  reg_no        TEXT NOT NULL DEFAULT '',
  experience_yr INTEGER,
  specialities  TEXT NOT NULL DEFAULT '',        -- comma separated
  bio           TEXT NOT NULL DEFAULT '',
  media_id      INTEGER REFERENCES media(id) ON DELETE SET NULL,
  sort_order    INTEGER NOT NULL DEFAULT 0,
  is_published  INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS branches (
  id             INTEGER PRIMARY KEY,
  name           TEXT NOT NULL,
  address        TEXT NOT NULL DEFAULT '',
  city           TEXT NOT NULL DEFAULT '',
  pincode        TEXT NOT NULL DEFAULT '',
  phone          TEXT NOT NULL DEFAULT '',
  whatsapp       TEXT NOT NULL DEFAULT '',
  email          TEXT NOT NULL DEFAULT '',
  place_id       TEXT NOT NULL DEFAULT '',
  map_embed      TEXT NOT NULL DEFAULT '',
  directions_url TEXT NOT NULL DEFAULT '',
  hours          TEXT NOT NULL DEFAULT '{}',     -- JSON {mon:[open,close], ...}
  media_id       INTEGER REFERENCES media(id) ON DELETE SET NULL,
  sort_order     INTEGER NOT NULL DEFAULT 0,
  is_published   INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS faqs (
  id           INTEGER PRIMARY KEY,
  question     TEXT NOT NULL,
  answer       TEXT NOT NULL DEFAULT '',
  category     TEXT NOT NULL DEFAULT 'General',
  sort_order   INTEGER NOT NULL DEFAULT 0,
  is_published INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS testimonials (
  id               INTEGER PRIMARY KEY,
  author           TEXT NOT NULL,
  author_role      TEXT NOT NULL DEFAULT '',
  rating           INTEGER NOT NULL DEFAULT 5,
  body             TEXT NOT NULL DEFAULT '',
  treatment        TEXT NOT NULL DEFAULT '',
  source           TEXT NOT NULL DEFAULT 'manual',  -- manual | google
  google_review_id TEXT NOT NULL DEFAULT '',
  is_featured      INTEGER NOT NULL DEFAULT 0,
  sort_order       INTEGER NOT NULL DEFAULT 0,
  is_published     INTEGER NOT NULL DEFAULT 1,
  created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS nav_items (
  id           INTEGER PRIMARY KEY,
  label        TEXT NOT NULL,
  url          TEXT NOT NULL DEFAULT '#',
  location     TEXT NOT NULL DEFAULT 'header',   -- header | footer | footer2
  sort_order   INTEGER NOT NULL DEFAULT 0,
  is_published INTEGER NOT NULL DEFAULT 1
);

-- ── google reviews ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS google_reviews_cache (
  place_id   TEXT PRIMARY KEY,
  payload    TEXT NOT NULL DEFAULT '{}',
  rating     REAL,
  total      INTEGER,
  fetched_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS review_sync_log (
  id          INTEGER PRIMARY KEY,
  place_id    TEXT NOT NULL DEFAULT '',
  ok          INTEGER NOT NULL DEFAULT 0,
  status_code INTEGER,
  message     TEXT NOT NULL DEFAULT '',
  count       INTEGER NOT NULL DEFAULT 0,
  created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ── enquiries ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS enquiries (
  id             INTEGER PRIMARY KEY,
  ref            TEXT NOT NULL UNIQUE,
  name           TEXT NOT NULL,
  phone          TEXT NOT NULL DEFAULT '',
  email          TEXT NOT NULL DEFAULT '',
  service_id     INTEGER REFERENCES services(id) ON DELETE SET NULL,
  branch_id      INTEGER REFERENCES branches(id) ON DELETE SET NULL,
  preferred_date TEXT NOT NULL DEFAULT '',
  preferred_time TEXT NOT NULL DEFAULT '',
  message        TEXT NOT NULL DEFAULT '',
  status         TEXT NOT NULL DEFAULT 'new',     -- new|contacted|booked|treated|closed|lost
  priority       TEXT NOT NULL DEFAULT 'normal',  -- low|normal|high
  assigned_to    INTEGER REFERENCES users(id) ON DELETE SET NULL,
  source_page    TEXT NOT NULL DEFAULT '',
  utm            TEXT NOT NULL DEFAULT '{}',
  ip             TEXT NOT NULL DEFAULT '',
  user_agent     TEXT NOT NULL DEFAULT '',
  is_spam        INTEGER NOT NULL DEFAULT 0,
  created_at     TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_enquiries_status ON enquiries(status, created_at);

CREATE TABLE IF NOT EXISTS enquiry_events (
  id         INTEGER PRIMARY KEY,
  enquiry_id INTEGER NOT NULL REFERENCES enquiries(id) ON DELETE CASCADE,
  user_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
  type       TEXT NOT NULL DEFAULT 'note',       -- created|note|status|assign|call|emi
  note       TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_enquiry_events ON enquiry_events(enquiry_id, created_at);

-- ── EMI ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS emi_plans (
  id                INTEGER PRIMARY KEY,
  name              TEXT NOT NULL,
  provider          TEXT NOT NULL DEFAULT 'In-house',
  tenure_months     INTEGER NOT NULL DEFAULT 12,
  interest_rate     REAL NOT NULL DEFAULT 0,     -- annual %, 0 = no cost EMI
  processing_fee_pct REAL NOT NULL DEFAULT 0,
  downpayment_pct   REAL NOT NULL DEFAULT 0,
  min_amount        REAL NOT NULL DEFAULT 0,
  max_amount        REAL NOT NULL DEFAULT 0,     -- 0 = no ceiling
  notes             TEXT NOT NULL DEFAULT '',
  sort_order        INTEGER NOT NULL DEFAULT 0,
  is_active         INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS emi_applications (
  id               INTEGER PRIMARY KEY,
  ref              TEXT NOT NULL UNIQUE,
  enquiry_id       INTEGER REFERENCES enquiries(id) ON DELETE SET NULL,
  applicant_name   TEXT NOT NULL,
  phone            TEXT NOT NULL DEFAULT '',
  email            TEXT NOT NULL DEFAULT '',
  service_id       INTEGER REFERENCES services(id) ON DELETE SET NULL,
  treatment_label  TEXT NOT NULL DEFAULT '',
  treatment_amount REAL NOT NULL DEFAULT 0,
  plan_id          INTEGER REFERENCES emi_plans(id) ON DELETE SET NULL,
  plan_label       TEXT NOT NULL DEFAULT '',
  tenure_months    INTEGER NOT NULL DEFAULT 12,
  interest_rate    REAL NOT NULL DEFAULT 0,
  processing_fee   REAL NOT NULL DEFAULT 0,
  downpayment      REAL NOT NULL DEFAULT 0,
  financed         REAL NOT NULL DEFAULT 0,
  monthly_emi      REAL NOT NULL DEFAULT 0,
  total_payable    REAL NOT NULL DEFAULT 0,
  status           TEXT NOT NULL DEFAULT 'submitted',
  -- submitted|under_review|approved|rejected|active|completed|defaulted|cancelled
  start_date       TEXT NOT NULL DEFAULT '',
  kyc_notes        TEXT NOT NULL DEFAULT '',
  notes            TEXT NOT NULL DEFAULT '',
  created_at       TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_emi_apps_status ON emi_applications(status, created_at);

CREATE TABLE IF NOT EXISTS emi_installments (
  id             INTEGER PRIMARY KEY,
  application_id INTEGER NOT NULL REFERENCES emi_applications(id) ON DELETE CASCADE,
  seq            INTEGER NOT NULL,
  due_date       TEXT NOT NULL,
  amount         REAL NOT NULL DEFAULT 0,
  status         TEXT NOT NULL DEFAULT 'due',    -- due|paid|waived
  paid_at        TEXT,
  payment_id     INTEGER
);
CREATE INDEX IF NOT EXISTS idx_installments_app ON emi_installments(application_id, seq);
CREATE INDEX IF NOT EXISTS idx_installments_due ON emi_installments(status, due_date);

CREATE TABLE IF NOT EXISTS payments (
  id             INTEGER PRIMARY KEY,
  receipt_no     TEXT NOT NULL UNIQUE,
  application_id INTEGER REFERENCES emi_applications(id) ON DELETE SET NULL,
  installment_id INTEGER REFERENCES emi_installments(id) ON DELETE SET NULL,
  enquiry_id     INTEGER REFERENCES enquiries(id) ON DELETE SET NULL,
  payer_name     TEXT NOT NULL DEFAULT '',
  amount         REAL NOT NULL DEFAULT 0,
  method         TEXT NOT NULL DEFAULT 'upi',    -- cash|upi|card|netbanking|gateway
  provider       TEXT NOT NULL DEFAULT '',
  provider_ref   TEXT NOT NULL DEFAULT '',
  status         TEXT NOT NULL DEFAULT 'paid',   -- paid|pending|failed|refunded
  paid_at        TEXT NOT NULL DEFAULT (datetime('now')),
  notes          TEXT NOT NULL DEFAULT '',
  recorded_by    INTEGER REFERENCES users(id) ON DELETE SET NULL,
  created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_payments_paid ON payments(paid_at);

-- ── audit ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_log (
  id          INTEGER PRIMARY KEY,
  user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
  user_email  TEXT NOT NULL DEFAULT '',
  action      TEXT NOT NULL DEFAULT '',          -- create|update|delete|login|sync|payment
  entity      TEXT NOT NULL DEFAULT '',
  entity_id   TEXT NOT NULL DEFAULT '',
  label       TEXT NOT NULL DEFAULT '',
  before_json TEXT,
  after_json  TEXT,
  ip          TEXT NOT NULL DEFAULT '',
  created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at);
