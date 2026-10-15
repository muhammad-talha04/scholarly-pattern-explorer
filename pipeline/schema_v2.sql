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
    meta      JSONB,
    model     TEXT
);

CREATE INDEX IF NOT EXISTS paper_embeddings_hnsw
    ON paper_embeddings USING hnsw (embedding vector_cosine_ops);

-- JSON documents shared by the ML store: galaxy, galaxy_state, patterns,
-- countries, topics, topic_country_year. See pipeline/migrations/001_ml_storage.sql.
CREATE TABLE IF NOT EXISTS documents (
    kind       TEXT PRIMARY KEY,
    payload    JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
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

-- Topic × country × year counts. country_stats rewrites the same columns into
-- data/topic_country_year.sqlite (view topic_country_year_v) on each ingest,
-- adding only the works new since the previous snapshot.
CREATE TABLE IF NOT EXISTS topic_country_year (
    topic_id          VARCHAR NOT NULL,
    topic_name        VARCHAR NOT NULL,
    country_code      VARCHAR NOT NULL,
    year              INTEGER NOT NULL,
    paper_count       INTEGER NOT NULL,
    fractional_count  DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (topic_id, country_code, year)
);

CREATE OR REPLACE VIEW topic_country_year_v AS
SELECT topic_id, topic_name, country_code, year, paper_count, fractional_count
FROM topic_country_year;
