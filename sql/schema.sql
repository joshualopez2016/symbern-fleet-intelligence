-- BMS Cloud Dashboard — PostgreSQL schema (DDL + indexes)
-- Run as the app role against the `bms` database, e.g.:
--   psql "postgresql://bms_app:***@127.0.0.1:5432/bms" -f sql/schema.sql
--
-- Design notes (see docs/DESIGN.md):
--   * readings        = honest time-series of record (append-only, high volume)
--   * device_status   = denormalized "latest per device" cache for the fleet grid
--                       (O(fleet) reads instead of GROUP BY over millions of rows)
--   * alarms          = first-class rows with severity + optional cleared_at
--   * thresholds live in backend config, NOT in the DB (configurable in one place)

-- Idempotent: safe to re-run during development.
DROP TABLE IF EXISTS readings      CASCADE;
DROP TABLE IF EXISTS alarms        CASCADE;
DROP TABLE IF EXISTS device_status CASCADE;
DROP TABLE IF EXISTS devices       CASCADE;

-- One row per physical battery pack in the (simulated) fleet.
CREATE TABLE devices (
    device_id        TEXT PRIMARY KEY,                 -- e.g. 'BMS-0421'
    label            TEXT        NOT NULL,
    model            TEXT        NOT NULL,
    site             TEXT        NOT NULL,              -- depot / location
    company          TEXT        NOT NULL DEFAULT 'Unassigned',  -- operating company
    equipment        TEXT        NOT NULL DEFAULT 'Unassigned',  -- equipment the pack powers
    cell_count       INTEGER     NOT NULL DEFAULT 16,   -- reserved for cell-level stretch
    nominal_voltage  NUMERIC(6,2) NOT NULL,             -- pack nominal, e.g. 51.20 V
    capacity_ah      NUMERIC(7,2) NOT NULL,             -- pack capacity, e.g. 100.00 Ah
    commissioned_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Append-only telemetry. This is the "swap for a real feed later" surface.
CREATE TABLE readings (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    device_id     TEXT        NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
    ts            TIMESTAMPTZ NOT NULL,
    soc           NUMERIC(5,2) NOT NULL,                -- state of charge, %
    pack_voltage  NUMERIC(6,2) NOT NULL,                -- V
    current_a     NUMERIC(7,2) NOT NULL,                -- + = discharge, - = charge
    temperature_c NUMERIC(5,2) NOT NULL
);

-- Denormalized current state — the fleet grid reads ONLY this table.
CREATE TABLE device_status (
    device_id     TEXT PRIMARY KEY REFERENCES devices(device_id) ON DELETE CASCADE,
    ts            TIMESTAMPTZ NOT NULL,
    soc           NUMERIC(5,2) NOT NULL,
    pack_voltage  NUMERIC(6,2) NOT NULL,
    current_a     NUMERIC(7,2) NOT NULL,
    temperature_c NUMERIC(5,2) NOT NULL,
    status        TEXT        NOT NULL DEFAULT 'ok',    -- ok | warning | critical
    active_alarms INTEGER     NOT NULL DEFAULT 0
);

-- Fault/alarm events. Active = cleared_at IS NULL.
CREATE TABLE alarms (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    device_id   TEXT        NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
    ts          TIMESTAMPTZ NOT NULL,
    code        TEXT        NOT NULL,                   -- LOW_SOC | LOW_VOLTAGE | OVER_TEMP ...
    severity    TEXT        NOT NULL,                   -- info | warning | critical
    value       NUMERIC(8,2),                           -- the reading that tripped it
    cleared_at  TIMESTAMPTZ                             -- NULL while active
);

-- Indexes ---------------------------------------------------------------

-- Powers drill-down history AND `?since=` delta queries (both filter by
-- device_id and order/bound by ts). DESC matches "most recent first".
CREATE INDEX idx_readings_device_ts ON readings (device_id, ts DESC);

-- Global "what changed since T" feed (delta polling across the whole fleet).
CREATE INDEX idx_readings_ts ON readings (ts DESC);

-- Alarm history per device, newest first.
CREATE INDEX idx_alarms_device_ts ON alarms (device_id, ts DESC);

-- Cheap "active alerts" lookups — partial index over only open alarms.
CREATE INDEX idx_alarms_active ON alarms (ts DESC) WHERE cleared_at IS NULL;
