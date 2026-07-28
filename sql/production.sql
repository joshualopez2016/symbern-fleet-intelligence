-- Production Test Records domain (manufacturing / QA).
-- One row per test execution. Simulated, Symbern-branded battery/equipment QA
-- (cloud-safe). The same shape could ingest a real MES/test-bench feed on-prem.
--   psql "$DATABASE_URL" -f sql/production.sql

DROP TABLE IF EXISTS test_records CASCADE;

CREATE TABLE test_records (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ts             TIMESTAMPTZ  NOT NULL,
    product        TEXT         NOT NULL,               -- model / family
    part_number    TEXT         NOT NULL,               -- SKU
    serial_number  TEXT         NOT NULL,               -- unit serial (traceability)
    station        TEXT         NOT NULL,               -- test station
    fixture        TEXT         NOT NULL,               -- test fixture
    operator       TEXT         NOT NULL,               -- operator id
    test_parameter TEXT         NOT NULL,               -- e.g. Pack Voltage, Capacity
    result         TEXT         NOT NULL CHECK (result IN ('Pass', 'Fail')),
    measured_value NUMERIC(10,3),
    limit_low      NUMERIC(10,3),
    limit_high     NUMERIC(10,3),
    failure_reason TEXT                                 -- NULL on pass
);

CREATE INDEX idx_tr_serial   ON test_records (serial_number);
CREATE INDEX idx_tr_ts       ON test_records (ts DESC);
CREATE INDEX idx_tr_product  ON test_records (product);
CREATE INDEX idx_tr_result   ON test_records (result);
CREATE INDEX idx_tr_station  ON test_records (station);
CREATE INDEX idx_tr_fixture  ON test_records (fixture);

-- The read-only role (query builder) can read this table too.
GRANT SELECT ON test_records TO bms_readonly;
