-- Remaining Postgres tables from pipeline/schema_v2.sql, so one apply rebuilds
-- the whole API database. Idempotent.

CREATE TABLE IF NOT EXISTS runs (
    id               SERIAL PRIMARY KEY,
    started_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at      TIMESTAMPTZ,
    status           TEXT NOT NULL DEFAULT 'running',
    since_date       DATE,
    papers_added     INTEGER DEFAULT 0,
    patterns_changed INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS paper_summaries (
    work_id    VARCHAR PRIMARY KEY,
    summary    TEXT,
    one_line   TEXT,
    model      TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS snapshots (
    run_id  INTEGER REFERENCES runs(id),
    kind    TEXT,
    payload JSONB,
    PRIMARY KEY (run_id, kind)
);

ALTER TABLE runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE paper_summaries ENABLE ROW LEVEL SECURITY;
ALTER TABLE snapshots ENABLE ROW LEVEL SECURITY;
