# BMS Cloud Dashboard

A full-stack proof-of-concept for monitoring a fleet of battery management
systems (BMS) in real time. Fleet managers see every battery's health at a
glance and drill into any device's history. **All telemetry is simulated** — a
standalone generator produces plausible data; no real hardware or customer data
is involved.

**Author:** Joshua Lopez · Z23384309 · Joshualopez2016@fau.edu

Pipeline: **Simulator → PostgreSQL → FastAPI → React**. The simulator is the only
writer; the API is read-only. Swapping the simulator for a real telemetry feed
would leave the schema, API, and UI untouched.

```
BMS-Cloud-Dashboard/          ← self-contained; copy this one folder to move the project
├── docs/          DESIGN.md, API_ENDPOINTS.md
├── sql/           schema.sql  (DDL + indexes)
├── simulator/     simulator.py  (standalone telemetry generator)
├── backend/       FastAPI read API + config/thresholds.py
├── frontend/      React (Vite) dashboard
├── .env.example   copy to .env and fill in (real .env is git-ignored)
└── README.md
```

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
# load tables + indexes
psql "postgresql://bms_app:CHANGE_ME@127.0.0.1:5432/bms" -f sql/schema.sql
```

### 2. Environment
```bash
cp .env.example .env      # then edit DATABASE_URL to match the password above
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

## Running (three processes)

```bash
# 1) seed + stream telemetry
py simulator/simulator.py --reset --fleet-size 30 --interval 2

# 2) API (from repo root)
cd backend && py -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 3) dashboard
cd frontend && npm run dev        # http://localhost:5173
```

The Vite dev server proxies `/api` to the backend on :8000, so open only
**http://localhost:5173**.

Simulator flags: `--fleet-size N`, `--interval SECONDS`, `--ticks N` (0 = forever),
`--reset` (truncate + reseed), `--seed-only`. Without `--reset` it resumes each
pack's state from the last snapshot.

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

## Security self-certification
All four checklist items pass — full evidence in [docs/SECURITY.md](docs/SECURITY.md):
- ✅ No secrets / connection strings in the repo (`.env` git-ignored; runtime reads from env)
- ✅ All queries parameterized (`%s` bind params, pg8000)
- ✅ XSS-safe (React escaping; JSON-only API; no `dangerouslySetInnerHTML`)
- ✅ `pip-audit` + `npm audit` clean; all dependencies permissively licensed (no copyleft)
