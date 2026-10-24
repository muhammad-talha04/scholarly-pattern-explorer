-- Applied by hand on 2026-10-24 (Supabase MCP). The bulk loader's role could not
-- update sampling_rates until the table belonged to spe_api.
alter table if exists sampling_rates owner to spe_api;
