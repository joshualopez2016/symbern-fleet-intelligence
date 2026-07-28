-- Support tickets (raised from the in-app assistant chatbot).
--   psql "$DATABASE_URL" -f sql/support.sql

CREATE TABLE IF NOT EXISTS tickets (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id    BIGINT      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    user_email TEXT        NOT NULL,
    subject    TEXT        NOT NULL,
    category   TEXT        NOT NULL DEFAULT 'IT'
               CHECK (category IN ('IT', 'Management', 'Other')),
    body       TEXT        NOT NULL,
    status     TEXT        NOT NULL DEFAULT 'open'
               CHECK (status IN ('open', 'in_progress', 'closed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tickets_user ON tickets (user_id);
GRANT SELECT ON tickets TO bms_readonly;
