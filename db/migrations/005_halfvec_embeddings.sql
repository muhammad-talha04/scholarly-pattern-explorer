-- Store embeddings as halfvec(384) (2 bytes/dim instead of 4) to fit ~70k papers
-- in the Supabase free tier. Needs pgvector >= 0.7 (Supabase ships 0.8).
-- Idempotent: only converts when the column is still vector. The index keeps the
-- name paper_embeddings_hnsw so 001's CREATE INDEX IF NOT EXISTS stays a no-op.
-- Rewrites the table and rebuilds the index: run it once, off-peak, before the bulk load.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_attribute a
        JOIN pg_class c ON c.oid = a.attrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relname = 'paper_embeddings'
          AND a.attname = 'embedding' AND format_type(a.atttypid, a.atttypmod) = 'vector(384)'
    ) THEN
        DROP INDEX IF EXISTS paper_embeddings_hnsw;
        ALTER TABLE paper_embeddings ALTER COLUMN embedding TYPE halfvec(384)
            USING embedding::halfvec(384);
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS paper_embeddings_hnsw
    ON paper_embeddings USING hnsw (embedding halfvec_cosine_ops);
