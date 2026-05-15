-- ============================================================
-- Weekly ETL schedule via pg_cron
-- ============================================================
-- Runs every Sunday at 02:00 UTC.
-- The actual ETL is in Python; this just NOTIFIEs a listener,
-- which the Python `etl/listener.py` (or a cron-invoked
-- `python -m etl --since auto`) picks up.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Drop any prior schedule with this name (idempotent re-init)
SELECT cron.unschedule(jobid)
FROM cron.job
WHERE jobname = 'telecom-etl-weekly';

SELECT cron.schedule(
    'telecom-etl-weekly',
    '0 2 * * 0',
    $$ NOTIFY telecom_etl, 'run'; $$
);
