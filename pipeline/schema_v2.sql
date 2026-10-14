-- Postgres (Supabase) additions for incremental runs. Extends schema.sql.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS runs (
    id               SERIAL PRIMARY KEY,
    started_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at      TIMESTAMPTZ,
    status           TEXT NOT NULL DEFAULT 'running',
    since_date       DATE,
    papers_added     INTEGER DEFAULT 0,
    patterns_changed INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS paper_embeddings (
    work_id   VARCHAR PRIMARY KEY,
    embedding vector(384),
    model     TEXT NOT NULL
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
    kind    TEXT,   -- 'patterns' | 'countries' | 'topics'
    payload JSONB,
    PRIMARY KEY (run_id, kind)
);
