# Free cloud deploy — a link to share with Symbern

One **free** web service (API + WebSocket + UI + simulator, all in one) on
**Render**, backed by a **free Neon** Postgres. You share the **Render URL** with
Symbern — the GitHub repo is just the source Render builds from.

**Cost: $0.** Caveat: free services **sleep after ~15 min idle** — the first visit
after that has a ~30–60 s cold start, and the simulator resumes from the database
on wake (no data loss). A ~$7/mo plan removes the sleep if you want it always-on.

---

## Step 1 — Push the repo to GitHub (free)
```bash
# from BMS-Cloud-Dashboard/
git remote add origin https://github.com/<you>/symbern-fleet-intelligence.git
git push -u origin main
```
(`.env` is git-ignored, so no secrets are pushed.)

## Step 2 — Create a free Neon Postgres
1. Sign up at **neon.tech** (free, no card) → create a project.
2. Copy the **connection string** — it looks like:
   `postgresql://user:pass@ep-xxx.region.aws.neon.tech/dbname?sslmode=require`
   (the `?sslmode=require` matters — the app enables TLS from it.)

## Step 3 — Initialize the Neon database (once, from your machine)
`psql` and `py` are already set up locally. Point them at Neon:
```bash
NEON="postgresql://…neon…/dbname?sslmode=require"

# schema + all objects
psql "$NEON" -f sql/schema.sql -f sql/auth.sql -f sql/notes.sql \
             -f sql/daily_report.sql -f sql/production.sql -f sql/support.sql

# logins  (give Symbern the engineer one; keep admin for yourself)
DATABASE_URL="$NEON" py backend/create_user.py admin@bms.local     Admin#2026     administrator
DATABASE_URL="$NEON" py backend/create_user.py symbern@demo.local  Symbern#2026   engineer

# seed data
DATABASE_URL="$NEON" py simulator/production_sim.py --reset --units 600 --days 14
DATABASE_URL="$NEON" py simulator/simulator.py       --reset --fleet-size 30 --seed-only
```
*(Skip `sql/roles.sql` — Neon may not allow creating the read-only role; the query
builder falls back to the main connection automatically. To enable it, create a
read-only role in Neon and set `READONLY_DATABASE_URL` in Step 4.)*

## Step 4 — Deploy on Render (free)
1. Sign up at **render.com** (free) → **New → Blueprint** → connect your GitHub repo.
2. Render reads `render.yaml` and creates the service. Set the env vars it asks for:
   - **DATABASE_URL** = your Neon string (with `?sslmode=require`)
   - **TRUSSED_API_KEY** = your FAU key *(optional — see note below)*
   - `JWT_SECRET` is auto-generated; `RUN_SIMULATOR=1` and `SIM_FLEET=30` are preset.
3. Deploy. When it's live, open the Render URL — that's the app.

## Step 5 — Share it
- Send Symbern the **Render URL** + the login `symbern@demo.local / Symbern#2026`.
- They can leave feedback in-app via the **💬 Assistant → Start a support ticket**;
  you'll see it (sign in as admin → the tickets are in the database / API).

## Notes
- **AI key on a public demo:** the AI features use your FAU Trussed key (course
  budget/terms). For a public link, either omit `TRUSSED_API_KEY` (AI shows a
  friendly "off" state) or use an Anthropic key instead.
- **Updating the app:** push to GitHub → Render redeploys automatically.
- The whole thing is one Docker image (`Dockerfile`): builds the React app, then
  runs FastAPI which serves the UI, the API, the WebSocket, and the simulator.
