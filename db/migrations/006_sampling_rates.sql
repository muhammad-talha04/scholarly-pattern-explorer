-- Per-month OpenAlex sampling rate, written by `ml.cli bulk`. Lets gap / emerging
-- analysis scale sample counts back to the full OpenAlex population:
--   estimated_openalex = sample_count * openalex_total / sampled
-- openalex_total: works in that publication month matching `filter` (meta.count).
-- sampled: papers we hold for that month (stored before the run + fetched by it).
CREATE TABLE IF NOT EXISTS sampling_rates (
    month          DATE PRIMARY KEY,           -- first day of the publication month
    openalex_total INTEGER NOT NULL,
    sampled        INTEGER NOT NULL,
    filter         TEXT NOT NULL,
    fetched_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE sampling_rates ENABLE ROW LEVEL SECURITY;

-- One read-only policy: the spe_api role may SELECT. No insert/update/delete
-- policies (the loader writes as the table owner, which bypasses RLS).
-- Guarded: skipped when spe_api does not exist; drop + create keeps it re-runnable.
DROP POLICY IF EXISTS sampling_rates_select_spe_api ON sampling_rates;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'spe_api') THEN
        CREATE POLICY sampling_rates_select_spe_api ON sampling_rates
            FOR SELECT TO spe_api USING (true);
    END IF;
END $$;
