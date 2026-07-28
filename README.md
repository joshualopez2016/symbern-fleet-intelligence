# BMS Cloud Dashboard

A full-stack proof-of-concept **fleet-battery intelligence platform**, built for
**Symbern** — *"Batteries. Equipment. Intelligence."* It covers a unit's whole
lifecycle across two data domains behind one shell:

- **Fleet Intelligence** — real-time monitoring of deployed battery packs (state
  of charge, voltage, temperature, alarms), with live **WebSocket** updates.
- **Production Test Records** — manufacturing/QA test history: pass/fail at
  stations & fixtures, by operator, serial-traceable (Pass/Fail lookup, daily
  production summary, serial history, universal search).

**All data is simulated** — standalone generators produce plausible data; no real
hardware or customer data is involved (cloud-safe).

**Author:** Joshua Lopez · Z23384309 · Joshualopez2016@fau.edu

Pipeline: **Simulators → PostgreSQL → FastAPI → React**. Also includes JWT auth
with enforced roles, a no-code query builder, AI features (FAU Trussed.ai), and
reporting/export. Swapping a simulator for a real feed leaves the schema, API,
and UI untouched.

```
BMS-Cloud-Dashboard/          ← self-contained; copy this one folder to move the project
├── docs/       DESIGN, API_ENDPOINTS, SCALE, SECURITY, TESTING, TRANSFER, PRODUCTION_SCOPE
├── sql/        schema · auth · notes · roles · daily_report · production
├── simulator/  simulator.py (telemetry) · production_sim.py (QA test records)
├── backend/    FastAPI app (app/) + config/thresholds.py
├── frontend/   React (Vite) dashboard
├── tests/      pytest suite + Postman/Thunder collection
├── .env.example  copy to .env and fill in (real .env is git-ignored)
└── README.md
```

## Feature overview
Auth (JWT) + enforced roles (viewer/engineer/supervisor/administrator) · user
management · fleet grid + drill-down trend charts · configurable alert thresholds
· active-alerts panel · advanced filters · **AI** (NL fleet search + fleet
briefing) · reporting & export (CSV/Excel/PDF-print) · **no-code query builder**
(read-only role) · **WebSocket realtime** · daily pack report · **Production Test
Records** domain. Security self-cert in [docs/SECURITY.md](docs/SECURITY.md);
tests in [docs/TESTING.md](docs/TESTING.md).

---

## Prerequisites

| Tool | Version used | Notes |
|---|---|---|
| PostgreSQL | 17 | any recent Postgres works |
| Python | 3.12 (`py` launcher) | backend + simulator |
| Node.js | 24 LTS | frontend (Vite 7 needs Node ≥ 20.19) |

## Setup

### 1. Database
Create an app role + database, then load the schema:
```bash
# as a postgres superuser
psql -c "CREATE ROLE bms_app LOGIN PASSWORD 'CHANGE_ME';"
psql -c "CREATE DATABASE bms OWNER bms_app;"
# load all schema objects (as bms_app)
DB="postgresql://bms_app:CHANGE_ME@127.0.0.1:5432/bms"
psql "$DB" -f sql/schema.sql -f sql/auth.sql -f sql/notes.sql \
           -f sql/daily_report.sql -f sql/production.sql
# read-only role for the query builder (as a superuser)
psql -d bms -f sql/roles.sql
```

### 2. Environment
```bash
cp .env.example .env
# edit DATABASE_URL + READONLY_DATABASE_URL to match your passwords, set a
# JWT_SECRET (any long random string), and TRUSSED_API_KEY for the AI features.
```

### 3. Python (backend + simulator)
```bash
py -m pip install -r backend/requirements.txt
py -m pip install -r simulator/requirements.txt
# (optional but recommended on a fresh machine: use a virtualenv)
#   py -m venv .venv && .venv\Scripts\activate    # Windows
#   pip install -r backend/requirements.txt -r simulator/requirements.txt
```

### 4. Frontend
```bash
cd frontend && npm install
```

## Seed data & users (once)
```bash
# telemetry fleet (or run live below), and the production QA test records
py simulator/simulator.py --reset --fleet-size 30 --seed-only
py simulator/production_sim.py --reset --units 600 --days 14
# create login users
py backend/create_user.py admin@bms.local  Admin#2026  administrator
py backend/create_user.py viewer@bms.local Viewer#2026 viewer
```

## Running (three processes)
```bash
# 1) stream live telemetry
py simulator/simulator.py --fleet-size 30 --interval 2

# 2) API (from repo root)
cd backend && py -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 3) dashboard
cd frontend && npm run dev        # http://localhost:5173
```

The Vite dev server proxies `/api` (and the `/api/ws` WebSocket) to the backend on
:8000, so open only **http://localhost:5173**. Use the **Fleet / Production**
switch in the header to move between the two domains.

Telemetry simulator flags: `--fleet-size N`, `--interval SECONDS`, `--ticks N`
(0 = forever), `--reset`, `--seed-only`. Without `--reset` it resumes each pack's
state. Production simulator: `--units N`, `--days D`, `--reset`.

## Where things are configured
- **Alert thresholds:** [`backend/config/thresholds.py`](backend/config/thresholds.py)
  — the single source of truth, shared by the simulator (raising alarms) and the
  API (`GET /api/config/thresholds`). Not hardcoded in the UI.
- **DB connection:** `.env` only (never committed).

## Scale & efficiency (chosen stretch goal)
Proven with a 2,000-device fleet: bounded worst-first pages (~47 KB regardless of
fleet size vs ~467 KB unbounded), a one-query fleet summary (~5 ms), incremental
`?since=` fetching, and index-only queries (sub-millisecond over 50k readings).
Full measured results in [docs/SCALE.md](docs/SCALE.md).

## How the simulator models data
Each pack runs a discharge → charge state machine. Pack voltage comes from an
open-circuit-voltage curve of state-of-charge, sagging under load. Temperature
drifts with current. Alarms are consequences of state (low charge drags voltage
down; heavy load overheats a pack) plus a small rate of injected faults, and they
clear automatically when the condition recovers. See [docs/DESIGN.md](docs/DESIGN.md) §4.

## Moving this project to another machine
Everything lives inside this one folder. To relocate:
1. Copy the `BMS-Cloud-Dashboard/` folder (git-ignored `node_modules/`,
   `.venv/`, and `.env` do **not** need to come along).
2. Install the prerequisites above on the new machine.
3. Recreate `.env` from `.env.example`, run the DB setup, `npm install`, and
   `pip install -r` the two requirements files.

Nothing outside this folder is required except the locally-installed Postgres
service (recreated via the DB setup step) and the Python/Node runtimes.

## Testing
The API is covered by a **Postman/Thunder Client collection** (22 requests, 39
assertions) and a **pytest suite** (19 tests) — both green against a live server,
covering auth, CRUD (notes), AI, and error/edge cases (401/422/404). See
[docs/TESTING.md](docs/TESTING.md).
```bash
py -m pip install -r tests/requirements.txt && py -m pytest tests/ -v
# or:  newman run tests/bms_api.postman_collection.json
```

## Security self-certification
All four checklist items pass — full evidence in [docs/SECURITY.md](docs/SECURITY.md):
- ✅ No secrets / connection strings in the repo (`.env` git-ignored; runtime reads from env)
- ✅ All queries parameterized (`%s` bind params, pg8000)
- ✅ XSS-safe (React escaping; JSON-only API; no `dangerouslySetInnerHTML`)
- ✅ `pip-audit` + `npm audit` clean; all dependencies permissively licensed (no copyleft)
