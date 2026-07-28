-- Least-privilege READ-ONLY role.
-- The API routes the ad-hoc query builder (and can route any read path) through
-- this role, so those queries physically cannot modify data — protecting the
-- telemetry/production tables from accidental edits.
--
-- Run as a superuser (creates a role + grants):
--   psql "postgresql://postgres:***@127.0.0.1:5432/bms" -f sql/roles.sql

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'bms_readonly') THEN
        CREATE ROLE bms_readonly LOGIN PASSWORD 'bms_ro_2026';
    END IF;
END $$;

GRANT CONNECT ON DATABASE bms TO bms_readonly;
GRANT USAGE ON SCHEMA public TO bms_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO bms_readonly;

-- Belt and suspenders: ensure NO write privileges of any kind.
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA public FROM bms_readonly;

-- Future tables created by the app owner are also read-only to this role.
ALTER DEFAULT PRIVILEGES FOR ROLE bms_app IN SCHEMA public GRANT SELECT ON TABLES TO bms_readonly;
