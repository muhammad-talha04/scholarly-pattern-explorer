-- Saved gap, emerging, and later discovery runs.
-- kind is free text (gap, emerging, and whatever the job adds next).
-- country_code is optional: a null means the snapshot is not filtered to one country.

CREATE TABLE IF NOT EXISTS discovery_snapshots (
    id           BIGSERIAL PRIMARY KEY,
    run_date     DATE NOT NULL,
    kind         TEXT NOT NULL,
    country_code TEXT,
    results      JSONB NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS discovery_snapshots_run_date_idx
    ON discovery_snapshots (run_date);

CREATE INDEX IF NOT EXISTS discovery_snapshots_kind_country_date_idx
    ON discovery_snapshots (kind, country_code, run_date DESC);

CREATE INDEX IF NOT EXISTS discovery_snapshots_created_at_idx
    ON discovery_snapshots (created_at DESC);

ALTER TABLE discovery_snapshots ENABLE ROW LEVEL SECURITY;
