-- Keep the Render API awake from inside Supabase (pg_cron + pg_net, both on the free tier).
-- GitHub's 10-minute keepalive cron ran only 82 times in 22 days (scheduled Actions are
-- throttled), so the API slept and the first visitor waited 20+ s. Run once in the
-- Supabase SQL editor. Undo: select cron.unschedule('keepalive-render-api');
create extension if not exists pg_cron;
create extension if not exists pg_net;
select cron.schedule('keepalive-render-api', '*/10 * * * *',
  $$select net.http_get('https://scholarly-pattern-explorer.onrender.com/api/v1/health', timeout_milliseconds := 30000)$$);
