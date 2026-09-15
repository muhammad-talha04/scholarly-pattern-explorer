-- ============================================================
-- Indexes, created AFTER the data is loaded.
--
-- An index is a sorted lookup structure. If it exists while you
-- are inserting rows, the database has to keep it sorted on every
-- insert. If you create it afterwards, it sorts the finished table
-- once. Same result, dramatically less work - this is standard
-- practice for any bulk load.
--
-- Runs unchanged on both DuckDB and SQLite.
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_works_year      ON works (pub_year);
CREATE INDEX IF NOT EXISTS idx_wt_topic        ON work_topics (topic_id);
CREATE INDEX IF NOT EXISTS idx_wt_work         ON work_topics (work_id);
CREATE INDEX IF NOT EXISTS idx_wa_author       ON work_authors (author_id);
CREATE INDEX IF NOT EXISTS idx_patterns_window ON patterns (window_start);
CREATE INDEX IF NOT EXISTS idx_patterns_k      ON patterns (k);
CREATE INDEX IF NOT EXISTS idx_wc_country     ON work_countries (country);
CREATE INDEX IF NOT EXISTS idx_wa_work         ON work_authors (work_id);
