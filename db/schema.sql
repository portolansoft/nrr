-- Portolan NRR pilot store. One row per record plus normalised side tables for the fields agents query.
-- The canonical JSON is the source of truth; side tables are derived at load time.
CREATE TABLE IF NOT EXISTS records (
  id TEXT PRIMARY KEY,                 -- content address (urn:portolan:nrr:sha256:...)
  slug TEXT NOT NULL UNIQUE,
  study_id TEXT NOT NULL,
  kind TEXT NOT NULL,                  -- path | attempt
  attempt_type TEXT,                   -- wet-lab | computational | evidence-synthesis | hypothesis-generation | evaluation
  title TEXT NOT NULL,
  question TEXT NOT NULL,
  outcome_class TEXT NOT NULL,
  outcome_summary TEXT,
  operator TEXT NOT NULL,
  is_part_of TEXT,
  date_created TEXT NOT NULL,
  visibility TEXT NOT NULL,
  source_license TEXT,
  applicability TEXT,                  -- JSON
  cost TEXT,                           -- JSON
  canonical_json TEXT NOT NULL,        -- full record
  crate_json TEXT                      -- RO-Crate JSON-LD
);
CREATE TABLE IF NOT EXISTS findings (
  record_id TEXT NOT NULL REFERENCES records(id),
  finding_id TEXT NOT NULL,
  question TEXT NOT NULL,
  target_label TEXT NOT NULL,
  target_identifier TEXT,
  target_type TEXT,
  outcome_class TEXT NOT NULL,
  informativeness TEXT NOT NULL,
  informativeness_reason TEXT,
  failure_modes TEXT,                  -- JSON array
  effect_metric TEXT,
  effect_value TEXT,
  effect_n INTEGER,
  effect_direction TEXT,
  significant TEXT,
  positive_control_kind TEXT,
  positive_control_passed INTEGER,
  negative_control_kind TEXT,
  negative_control_passed INTEGER,
  sensitivity TEXT,
  dose TEXT,
  proposed_by TEXT,
  finding_json TEXT NOT NULL,
  PRIMARY KEY (record_id, finding_id)
);
CREATE TABLE IF NOT EXISTS screened_items (
  record_id TEXT NOT NULL REFERENCES records(id),
  seq INTEGER NOT NULL,
  label TEXT NOT NULL,
  identifier TEXT,
  item_type TEXT NOT NULL,
  proposed_by TEXT,
  decision TEXT NOT NULL,
  reason TEXT NOT NULL,
  score_method TEXT,
  score_value REAL,
  rank INTEGER,
  PRIMARY KEY (record_id, seq)
);
CREATE TABLE IF NOT EXISTS entities (
  id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL,
  label TEXT NOT NULL,
  scheme TEXT,
  url TEXT
);
CREATE TABLE IF NOT EXISTS record_entities (
  record_id TEXT NOT NULL REFERENCES records(id),
  entity_id TEXT NOT NULL REFERENCES entities(id),
  role TEXT,
  PRIMARY KEY (record_id, entity_id)
);
CREATE TABLE IF NOT EXISTS performers (
  record_id TEXT NOT NULL REFERENCES records(id),
  seq INTEGER NOT NULL,
  name TEXT NOT NULL,
  performer_type TEXT NOT NULL,
  role TEXT NOT NULL,
  model TEXT,
  provider TEXT,
  version TEXT,
  commit_hash TEXT,
  PRIMARY KEY (record_id, seq)
);
CREATE TABLE IF NOT EXISTS relations (
  from_id TEXT NOT NULL REFERENCES records(id),
  relation TEXT NOT NULL,
  to_id TEXT NOT NULL,
  note TEXT,
  PRIMARY KEY (from_id, relation, to_id)
);
CREATE TABLE IF NOT EXISTS sources (
  record_id TEXT NOT NULL REFERENCES records(id),
  seq INTEGER NOT NULL,
  role TEXT NOT NULL,
  identifier TEXT NOT NULL,
  label TEXT,
  status_version TEXT,
  status_integrity TEXT,
  status_asserted_by TEXT,
  status_checked_at TEXT,
  data_pointers INTEGER DEFAULT 0,
  PRIMARY KEY (record_id, seq)
);
CREATE TABLE IF NOT EXISTS branches (
  record_id TEXT NOT NULL REFERENCES records(id),
  seq INTEGER NOT NULL,
  branch_kind TEXT NOT NULL,           -- untried-branch | open-question | next-step
  status TEXT,
  description TEXT NOT NULL,
  data_pointers INTEGER DEFAULT 0,
  PRIMARY KEY (record_id, branch_kind, seq)
);
CREATE VIRTUAL TABLE IF NOT EXISTS records_fts USING fts5(
  slug, title, question, outcome_summary, applicability, findings_text, content=''
);
