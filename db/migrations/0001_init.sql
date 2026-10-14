-- Scholarly Pattern Explorer v2 schema (Postgres 16 + pgvector).
-- Keys are OpenAlex IDs (W…, T…, A…). Topic display names are attributes only.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE works (
    work_id       TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    abstract      TEXT,
    pub_year      INTEGER NOT NULL,
    pub_date      DATE,
    cited_by      INTEGER NOT NULL DEFAULT 0,
    n_authors     INTEGER NOT NULL DEFAULT 0,
    doi           TEXT,
    openalex_url  TEXT,
    oa_url        TEXT,
    updated_date  TIMESTAMPTZ,
    loaded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    tsv           TSVECTOR GENERATED ALWAYS AS (
                    to_tsvector('english', coalesce(title, '') || ' ' || coalesce(abstract, ''))
                  ) STORED
);

CREATE TABLE topics (
    topic_id      TEXT PRIMARY KEY,
    display_name  TEXT NOT NULL,
    subfield      TEXT,
    field         TEXT,
    domain        TEXT
);

CREATE TABLE authors (
    author_id     TEXT PRIMARY KEY,
    display_name  TEXT,
    institution   TEXT,
    country       CHAR(2)
);

CREATE TABLE work_topics (
    work_id   TEXT NOT NULL REFERENCES works ON DELETE CASCADE,
    topic_id  TEXT NOT NULL REFERENCES topics,
    score     REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (work_id, topic_id)
);

CREATE TABLE work_authors (
    work_id     TEXT NOT NULL REFERENCES works ON DELETE CASCADE,
    author_id   TEXT NOT NULL REFERENCES authors,
    author_pos  INTEGER NOT NULL,
    PRIMARY KEY (work_id, author_id)
);

CREATE TABLE work_countries (
    work_id  TEXT NOT NULL REFERENCES works ON DELETE CASCADE,
    country  CHAR(2) NOT NULL,
    PRIMARY KEY (work_id, country)
);

-- 384-d sentence embeddings (bge-small / MiniLM). Separate table so the
-- free-tier DB can hold embeddings for a subset of works only.
CREATE TABLE work_embeddings (
    work_id    TEXT PRIMARY KEY REFERENCES works ON DELETE CASCADE,
    model      TEXT NOT NULL,
    embedding  VECTOR(384) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE paper_summaries (
    work_id    TEXT PRIMARY KEY REFERENCES works ON DELETE CASCADE,
    model      TEXT NOT NULL,
    summary    TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One row per pipeline execution (scheduled or manual).
CREATE TABLE runs (
    run_id          BIGSERIAL PRIMARY KEY,
    kind            TEXT NOT NULL CHECK (kind IN ('fetch','mine','full','embed')),
    trigger         TEXT NOT NULL DEFAULT 'manual',   -- cron | manual | ci
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    status          TEXT NOT NULL DEFAULT 'running'
                    CHECK (status IN ('running','success','failed')),
    works_added     INTEGER NOT NULL DEFAULT 0,
    works_updated   INTEGER NOT NULL DEFAULT 0,
    windows_mined   INTEGER NOT NULL DEFAULT 0,
    patterns_born   INTEGER NOT NULL DEFAULT 0,
    patterns_died   INTEGER NOT NULL DEFAULT 0,
    fetch_watermark DATE,              -- from_updated_date for the next run
    notes           JSONB NOT NULL DEFAULT '{}'
);

-- Scope '' = global corpus, otherwise ISO-3166 alpha-2 country code.
-- One row per mined window: what parameters produced the stored patterns.
-- A params_hash mismatch forces a re-mine of that window.
CREATE TABLE mining_windows (
    scope           TEXT NOT NULL DEFAULT '',
    window_start    INTEGER NOT NULL,
    window_end      INTEGER NOT NULL,
    params_hash     TEXT NOT NULL,
    params          JSONB NOT NULL,      -- min_support, max_len, min_confidence, …
    n_tx            INTEGER NOT NULL,
    basket_hash     TEXT NOT NULL,       -- digest of input baskets; unchanged => skip
    run_id          BIGINT REFERENCES runs,
    mined_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (scope, window_start),
    CHECK (window_end >= window_start)
);

-- itemset_key = sorted topic IDs joined by '|', e.g. 'T10028|T10320'.
CREATE TABLE patterns (
    scope          TEXT NOT NULL DEFAULT '',
    window_start   INTEGER NOT NULL,
    itemset_key    TEXT NOT NULL,
    topic_ids      TEXT[] NOT NULL,
    k              SMALLINT NOT NULL,
    support_count  INTEGER NOT NULL,
    support        DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (scope, window_start, itemset_key),
    FOREIGN KEY (scope, window_start) REFERENCES mining_windows ON DELETE CASCADE
);

CREATE TABLE rules (
    scope            TEXT NOT NULL DEFAULT '',
    window_start     INTEGER NOT NULL,
    antecedent_key   TEXT NOT NULL,
    consequent_id    TEXT NOT NULL,
    support          DOUBLE PRECISION NOT NULL,
    confidence       DOUBLE PRECISION NOT NULL,
    lift             DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (scope, window_start, antecedent_key, consequent_id),
    FOREIGN KEY (scope, window_start) REFERENCES mining_windows ON DELETE CASCADE
);

-- Timeline: pattern birth/death events derived after each mining run.
CREATE TABLE pattern_events (
    scope         TEXT NOT NULL DEFAULT '',
    itemset_key   TEXT NOT NULL,
    window_start  INTEGER NOT NULL,
    event         TEXT NOT NULL CHECK (event IN ('born','died')),
    run_id        BIGINT REFERENCES runs,
    PRIMARY KEY (scope, itemset_key, window_start, event)
);

CREATE INDEX idx_works_year      ON works (pub_year);
CREATE INDEX idx_works_tsv       ON works USING GIN (tsv);
CREATE INDEX idx_wt_topic        ON work_topics (topic_id);
CREATE INDEX idx_wa_author       ON work_authors (author_id);
CREATE INDEX idx_wc_country      ON work_countries (country);
CREATE INDEX idx_patterns_key    ON patterns (scope, itemset_key);
CREATE INDEX idx_patterns_topics ON patterns USING GIN (topic_ids);
CREATE INDEX idx_emb_hnsw        ON work_embeddings USING hnsw (embedding vector_cosine_ops);
