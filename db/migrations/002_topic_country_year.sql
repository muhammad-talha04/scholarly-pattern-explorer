-- Topic × country × year counts. Same columns as the SQLite table written by
-- pipeline/country_stats.py. Idempotent.

CREATE TABLE IF NOT EXISTS topic_country_year (
    topic_id          VARCHAR NOT NULL,
    topic_name        VARCHAR NOT NULL,
    country_code      VARCHAR NOT NULL,
    year              INTEGER NOT NULL,
    paper_count       INTEGER NOT NULL,
    fractional_count  DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (topic_id, country_code, year)
);

-- security_invoker so a caller cannot skip row level security by reading the view.
CREATE OR REPLACE VIEW topic_country_year_v
WITH (security_invoker = true) AS
SELECT topic_id, topic_name, country_code, year, paper_count, fractional_count
FROM topic_country_year;

ALTER TABLE topic_country_year ENABLE ROW LEVEL SECURITY;
