-- ============================================================
-- Database schema for the OpenAlex pattern-mining project.
--
-- This is a NORMALIZED design: facts are stored once, and the
-- many-to-many relationships live in their own bridge tables
-- (work_topics, work_authors). This is exactly what a database
-- course means by third normal form, and it keeps every fact
-- correctable in exactly one place.
--
-- Runs unchanged on both DuckDB and SQLite.
-- ============================================================

DROP TABLE IF EXISTS work_topics;
DROP TABLE IF EXISTS work_authors;
DROP TABLE IF EXISTS patterns;
DROP TABLE IF EXISTS rules;
DROP TABLE IF EXISTS works;
DROP TABLE IF EXISTS topics;
DROP TABLE IF EXISTS authors;

-- One row per paper -------------------------------------------------
CREATE TABLE works (
    work_id     VARCHAR PRIMARY KEY,
    title       VARCHAR,
    pub_year    INTEGER,
    cited_by    INTEGER,
    n_authors   INTEGER
);

-- One row per research topic ---------------------------------------
CREATE TABLE topics (
    topic_id     VARCHAR PRIMARY KEY,
    display_name VARCHAR,
    field        VARCHAR,
    domain       VARCHAR
);

-- Bridge table: which topics appear on which paper -----------------
-- THIS is our transaction table. One paper = one "basket",
-- its topics = the "items" in that basket.
CREATE TABLE work_topics (
    work_id  VARCHAR,
    topic_id VARCHAR,
    score    DOUBLE,
    PRIMARY KEY (work_id, topic_id)
);

-- One row per author ------------------------------------------------
CREATE TABLE authors (
    author_id    VARCHAR PRIMARY KEY,
    display_name VARCHAR,
    institution  VARCHAR,
    country      VARCHAR
);

-- Bridge table: who wrote which paper ------------------------------
CREATE TABLE work_authors (
    work_id       VARCHAR,
    author_id     VARCHAR,
    author_pos    INTEGER,
    PRIMARY KEY (work_id, author_id)
);

-- Mining RESULTS are stored in the database too, not just printed.
-- Keeping the data and the mining results in one database is what makes
-- pattern lifecycles cheap to draw: every window is already answered.
CREATE TABLE patterns (
    window_start  INTEGER,
    window_end    INTEGER,
    itemset       VARCHAR,   -- topic names joined by ' | ', sorted
    k             INTEGER,   -- how many items in the set
    support_count INTEGER,   -- papers containing the whole set
    n_tx          INTEGER,   -- papers in this window
    support       DOUBLE,    -- support_count / n_tx
    PRIMARY KEY (window_start, itemset)
);

CREATE TABLE rules (
    window_start INTEGER,
    antecedent   VARCHAR,
    consequent   VARCHAR,
    support      DOUBLE,
    confidence   DOUBLE,
    lift         DOUBLE
);

-- NOTE: the indexes are NOT here. They live in indexes.sql and are created
-- AFTER the data is loaded. Building an index while rows are still arriving
-- means the database re-sorts the index on every single insert. On 188,000
-- papers that is the difference between seconds and half an hour.
