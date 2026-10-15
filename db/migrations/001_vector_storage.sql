-- pgvector embeddings and JSON documents.
-- Idempotent. Safe on a database created by the old pipeline/schema_v2.sql,
-- where paper_embeddings.model was NOT NULL and meta was missing.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS paper_embeddings (
    work_id   TEXT PRIMARY KEY,
    embedding vector(384),
    meta      JSONB,
    model     TEXT
);

ALTER TABLE paper_embeddings ADD COLUMN IF NOT EXISTS meta JSONB;
ALTER TABLE paper_embeddings ADD COLUMN IF NOT EXISTS model TEXT;

-- Older schema_v2.sql created model TEXT NOT NULL. The store writes meta and
-- leaves model unset, so that column has to accept NULL.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'paper_embeddings'
          AND column_name = 'model'
          AND is_nullable = 'NO'
    ) THEN
        ALTER TABLE paper_embeddings ALTER COLUMN model DROP NOT NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS paper_embeddings_hnsw
    ON paper_embeddings USING hnsw (embedding vector_cosine_ops);

-- One row per document kind. Known kinds: galaxy, galaxy_state, patterns,
-- countries, topics, topic_country_year.
CREATE TABLE IF NOT EXISTS documents (
    kind       TEXT PRIMARY KEY,
    payload    JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- No policies: anon and authenticated see nothing. DATABASE_URL (the table
-- owner / superuser) bypasses row level security and is how the API connects.
ALTER TABLE paper_embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
