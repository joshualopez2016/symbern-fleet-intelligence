-- Daily per-battery-pack report.
-- One row per pack per day, with every recorded quantity broken out into its own
-- column: identity/metadata (serial/pack number, equipment, company, location),
-- plus daily min / avg / max / end-of-day for SoC, pack voltage, current, and
-- temperature, plus the day's alarm counts by severity and by type.
--
-- Load with:  psql "$DATABASE_URL" -f sql/daily_report.sql
-- Requires the `company` and `equipment` columns on devices (see schema.sql).

CREATE OR REPLACE VIEW daily_pack_report AS
WITH agg AS (   -- per-pack, per-day aggregates over the telemetry time-series
    SELECT
        device_id,
        (ts AT TIME ZONE 'UTC')::date       AS report_date,
        count(*)                            AS readings,
        round(min(soc), 2)                  AS soc_min,
        round(avg(soc), 2)                  AS soc_avg,
        round(max(soc), 2)                  AS soc_max,
        round(min(pack_voltage), 2)         AS voltage_min,
        round(avg(pack_voltage), 2)         AS voltage_avg,
        round(max(pack_voltage), 2)         AS voltage_max,
        round(min(current_a), 2)            AS current_min,
        round(avg(current_a), 2)            AS current_avg,
        round(max(current_a), 2)            AS current_max,
        round(min(temperature_c), 2)        AS temp_min,
        round(avg(temperature_c), 2)        AS temp_avg,
        round(max(temperature_c), 2)        AS temp_max
    FROM readings
    GROUP BY device_id, (ts AT TIME ZONE 'UTC')::date
),
last_of_day AS (   -- end-of-day snapshot (final reading of each pack each day)
    SELECT DISTINCT ON (device_id, (ts AT TIME ZONE 'UTC')::date)
        device_id,
        (ts AT TIME ZONE 'UTC')::date       AS report_date,
        round(soc, 2)                       AS soc_end,
        round(pack_voltage, 2)              AS voltage_end
    FROM readings
    ORDER BY device_id, (ts AT TIME ZONE 'UTC')::date, ts DESC
),
alarms_day AS (   -- alarms raised per pack per day, split by severity and code
    SELECT
        device_id,
        (ts AT TIME ZONE 'UTC')::date                              AS report_date,
        count(*)                                                   AS alarms_raised,
        count(*) FILTER (WHERE severity = 'critical')              AS alarms_critical,
        count(*) FILTER (WHERE severity = 'warning')               AS alarms_warning,
        count(*) FILTER (WHERE code = 'LOW_SOC')                   AS low_soc_events,
        count(*) FILTER (WHERE code = 'LOW_VOLTAGE')               AS low_voltage_events,
        count(*) FILTER (WHERE code = 'OVER_TEMP')                 AS over_temp_events
    FROM alarms
    GROUP BY device_id, (ts AT TIME ZONE 'UTC')::date
)
SELECT
    a.report_date,
    a.device_id                         AS pack_number,   -- serial / pack number
    d.label                             AS pack_label,
    d.model,
    d.company,
    d.equipment,
    d.site                              AS location,
    d.nominal_voltage,
    d.capacity_ah,
    a.readings,
    a.soc_min, a.soc_avg, a.soc_max, l.soc_end,
    a.voltage_min, a.voltage_avg, a.voltage_max, l.voltage_end,
    a.current_min, a.current_avg, a.current_max,
    a.temp_min, a.temp_avg, a.temp_max,
    COALESCE(al.alarms_raised, 0)       AS alarms_raised,
    COALESCE(al.alarms_critical, 0)     AS alarms_critical,
    COALESCE(al.alarms_warning, 0)      AS alarms_warning,
    COALESCE(al.low_soc_events, 0)      AS low_soc_events,
    COALESCE(al.low_voltage_events, 0)  AS low_voltage_events,
    COALESCE(al.over_temp_events, 0)    AS over_temp_events
FROM agg a
JOIN devices d      USING (device_id)
JOIN last_of_day l  ON l.device_id = a.device_id AND l.report_date = a.report_date
LEFT JOIN alarms_day al ON al.device_id = a.device_id AND al.report_date = a.report_date
ORDER BY a.report_date DESC, a.device_id;

-- ---------------------------------------------------------------------------
-- Example: today's report, one row per pack
--   SELECT * FROM daily_pack_report WHERE report_date = CURRENT_DATE;
-- One pack's full daily history:
--   SELECT * FROM daily_pack_report WHERE pack_number = 'BMS-0001' ORDER BY report_date;

-- Optional: persist each day's report so history survives readings pruning.
-- A scheduled job (cron / pg_cron / Task Scheduler) would run the INSERT once
-- per day. Cloning the view's exact column shape with WHERE false (no rows).
CREATE TABLE IF NOT EXISTS daily_pack_report_archive AS
    SELECT * FROM daily_pack_report WHERE false;

-- Idempotent daily snapshot for a given day (defaults to yesterday):
--   INSERT INTO daily_pack_report_archive
--   SELECT * FROM daily_pack_report WHERE report_date = CURRENT_DATE - 1;
