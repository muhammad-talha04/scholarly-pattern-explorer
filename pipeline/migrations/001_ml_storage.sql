-- Idempotent pgvector storage for embeddings and JSON documents.
-- Applied by PgVectorStore on connect, and safe to run on a database that
-- already has pipeline/schema_v2.sql (model was NOT NULL and meta was absent).

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS paper_embeddings (
    work_id   TEXT PRIMARY KEY,
    embedding vector(384),
    meta      JSONB,
    model     TEXT
);

ALTER TABLE paper_embeddings ADD COLUMN IF NOT EXISTS meta JSONB;
ALTER TABLE paper_embeddings ADD COLUMN IF NOT EXISTS model TEXT;

-- schema_v2.sql originally created model TEXT NOT NULL. The store writes meta
-- and leaves model unset, so an existing NOT NULL column has to become nullable.
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

-- One row per document kind. payload is the JSON the API or a teammate stores.
-- Known kinds: galaxy, galaxy_state, patterns, countries, topics, topic_country_year.
CREATE TABLE IF NOT EXISTS documents (
    kind       TEXT PRIMARY KEY,
    payload    JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
