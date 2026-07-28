-- Per-user notes on a battery pack (CRUD, scoped to the authenticated user).
--   psql "$DATABASE_URL" -f sql/notes.sql

CREATE TABLE IF NOT EXISTS notes (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id    BIGINT      NOT NULL REFERENCES users(id)   ON DELETE CASCADE,
    device_id  TEXT        NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
    body       TEXT        NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_notes_device ON notes (device_id);
CREATE INDEX IF NOT EXISTS idx_notes_user   ON notes (user_id);
