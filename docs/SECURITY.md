# Security Self-Certification

Per the project brief, the four checklist items below are self-certified with the
evidence that supports each. Verified 2026-07-27.

| # | Requirement | Status |
|---|---|---|
| 1 | No secrets or DB connection strings in git history | ✅ |
| 2 | All queries parameterized (no SQL injection) | ✅ |
| 3 | No raw HTML injected from simulated data (XSS hygiene) | ✅ |
| 4 | `pip-audit` / `npm audit` clean, no copyleft dependencies | ✅ |

---

## 1. No secrets in the repo / git history
- The only real credential is the `DATABASE_URL`, which lives solely in **`.env`**,
  listed in [`.gitignore`](../.gitignore) (`.env` + `.env.*`, with `!.env.example`).
- [`.env.example`](../.env.example) ships only a `CHANGE_ME` placeholder.
- The connection string is read from the environment at runtime
  ([`backend/app/db.py`](../backend/app/db.py), [`simulator/simulator.py`](../simulator/simulator.py));
  no credential is hardcoded in any source file.
- A repo-wide search for the dev password and `postgresql://…` literals returns
  hits only in `.env` (ignored) and placeholder docs.

## 2. Parameterized queries only
- Every SQL statement uses **`%s` bind parameters** (pg8000 `format` paramstyle);
  values are passed as a separate params tuple, never string-formatted into SQL.
- Dynamic filters (`/api/fleet`, `/api/alarms`) are built by appending **fixed**
  fragments like `s.status = %s` and pushing the value onto the params list — the
  user never contributes SQL text, only bound values.
- The simulator's bulk writes are chunked **multi-row parameterized inserts**
  (`(%s, …), (%s, …)`), not string concatenation.
- **Defense in depth:** the ad-hoc **query builder** runs on a dedicated
  least-privilege **read-only** Postgres role (`bms_readonly`, `sql/roles.sql`) that
  has `SELECT` only — so even a hypothetical bug there physically cannot modify
  data (verified: `UPDATE` → "permission denied"). Query specs are also
  whitelist-validated against a field registry before any SQL is built.

## 3. XSS hygiene
- The UI is React, which **escapes all interpolated values by default**.
- No `dangerouslySetInnerHTML`, `innerHTML`, or `eval` anywhere in the frontend
  (verified by search).
- The API returns **JSON only** — no server-rendered HTML. Simulated fields are
  numbers and fixed enums (`status`, `severity`, alarm `code`), never free text.

## 4. Clean audits, no copyleft
**Vulnerabilities**
- `pip-audit -r backend/requirements.txt -r simulator/requirements.txt` →
  **No known vulnerabilities found.**
- `npm audit` (frontend) → **0 vulnerabilities.**

**Licenses — all permissive (MIT / BSD / Apache / PSF / ISC), no copyleft**

Python (runtime deps):

| Package | License |
|---|---|
| fastapi, pydantic, pydantic-core, anyio, h11, sniffio | MIT |
| starlette, uvicorn, click, python-dotenv, **pg8000** | BSD-3-Clause |
| typing-extensions | PSF-2.0 |

Frontend (`node_modules` tree scan): 83 MIT · 16 ISC · 3 BSD-3-Clause ·
1 Apache-2.0 · 1 CC-BY-4.0 (caniuse browser-compat **data**, attribution-only) —
**0 GPL/LGPL/AGPL/MPL**.

> **Note on the DB driver:** the initial build used `psycopg` (LGPL-3.0, a
> copyleft license). To meet the "no copyleft" requirement it was replaced with
> **pg8000** (BSD-3-Clause, pure-Python). No functional change — same schema,
> same parameterized queries, same API.

## Reproduce
```bash
pip-audit -r backend/requirements.txt -r simulator/requirements.txt
cd frontend && npm audit
```
