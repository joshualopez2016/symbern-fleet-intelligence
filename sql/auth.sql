-- Users & authentication.
-- Passwords are stored ONLY as bcrypt hashes (never plaintext). Roles match the
-- product's role model; role-based authorization is scaffolded for later use.
--   psql "$DATABASE_URL" -f sql/auth.sql

CREATE TABLE IF NOT EXISTS users (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email         TEXT        NOT NULL UNIQUE,
    password_hash TEXT        NOT NULL,               -- bcrypt hash
    role          TEXT        NOT NULL DEFAULT 'viewer'
                  CHECK (role IN ('viewer', 'engineer', 'supervisor', 'administrator')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users (lower(email));
