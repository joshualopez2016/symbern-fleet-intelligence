# API Endpoints — BMS Cloud Dashboard

Read-only FastAPI service. Base URL in dev: `http://127.0.0.1:8000`. All
responses are JSON; all SQL is parameterized (`%s`), no string interpolation.
Interactive docs (Swagger) are served at `/docs`.

`NUMERIC` columns are returned as JSON **numbers** (not strings). Timestamps are
ISO-8601 with timezone.

---

## GET /api/health
Liveness + DB reachability. → `{ "status": "ok" }` (open, no auth)

## Authentication
All `/api/*` data endpoints below require a **Bearer JWT** (`Authorization:
Bearer <token>`); without it they return `401`. `/api/health` and
`/api/auth/login` are open.

- **POST /api/auth/login** — body `{ "email", "password" }` →
  `{ "token": "<jwt>", "user": { "email", "role" } }`. `401` on bad credentials.
- **GET /api/auth/me** — current user `{ "email", "role" }` (requires token).
- **POST /api/auth/logout** — `{ "ok": true }` (stateless JWT; client discards token).

Roles: `viewer | engineer | supervisor | administrator`, **enforced** via
`require_role(...)`:
- **viewer** — read-only (cannot write notes → `403`)
- **engineer / supervisor / administrator** — may create/edit/delete notes
- **administrator** — may also manage users (below)

## User management (administrator only)
All return `403` for non-admins.
- **GET /api/users** → `{ count, users: [{id, email, role, created_at, last_login_at}] }`
- **POST /api/users** — `{ email, password, role }` → created user. `409` if email exists, `422` bad role.
- **PUT /api/users/{id}** — `{ role }` → updated user. `404` if unknown.
- **DELETE /api/users/{id}** → `{ deleted: id }`. `400` if deleting your own account, `404` if unknown.

## GET /api/config/thresholds
The single source of truth for alert limits (same values the simulator alarms
on). The UI colors its badges/charts off this.

```json
{
  "soc":               { "direction": "below", "warning": 25.0, "critical": 10.0, "unit": "%" },
  "pack_voltage_frac": { "direction": "below", "warning": 0.92, "critical": 0.85, "unit": "x_nominal" },
  "temperature_c":     { "direction": "above", "warning": 45.0, "critical": 55.0, "unit": "C" }
}
```

## GET /api/fleet/summary
Whole-fleet status tallies from a single aggregate over `device_status`. Cost is
independent of paging, so the UI shows true counts for thousands of devices
without shipping every row.

```json
{ "total": 2000, "ok": 1407, "warning": 571, "critical": 22, "active_alarms": 713 }
```

## GET /api/fleet
Fleet grid. Reads **only** `device_status` (one row/device) joined to `devices`
— never scans the readings time-series. Ordered worst-status first, then lowest
SoC.

| Query param | Type | Default | Notes |
|---|---|---|---|
| `status` | `ok`\|`warning`\|`critical` | — | single status (stat pills) |
| `statuses` | comma list | — | multi-select status (e.g. `warning,critical`) |
| `sites` | comma list | — | multi-select site |
| `companies` | comma list | — | multi-select company |
| `equipment` | comma list | — | multi-select equipment |
| `soc_min` / `soc_max` | number 0–100 | — | state-of-charge range |
| `has_alarms` | bool | false | only packs with active alarms |
| `q` | string | — | search `device_id` / `label` (ILIKE) |
| `since` | ISO timestamp | — | **delta poll**: only devices updated after this ts |
| `limit` / `offset` | int | 500 / 0 | pagination |

**GET /api/fleet/filter-options** → `{ "sites": [...], "companies": [...], "equipment": [...] }`
(distinct values for the filter dropdowns). The same filter params above apply to
`GET /api/export/fleet.{csv,xlsx}`, so exports honor the active filters.

```json
{ "total": 24, "count": 3, "devices": [
  { "device_id": "BMS-0007", "label": "Pack 0007", "model": "PowerCell-48",
    "site": "Depot-North", "soc": 14.31, "pack_voltage": 50.48, "current_a": -81.54,
    "temperature_c": 28.67, "status": "warning", "active_alarms": 1,
    "ts": "2026-07-28T05:31:32.16-04:00" } ] }
```

## GET /api/devices/{device_id}
Device metadata + latest status snapshot. `404` if unknown.

```json
{ "device": { "device_id": "BMS-0007", "label": "Pack 0007", "model": "PowerCell-48",
    "site": "Depot-North", "cell_count": 16, "nominal_voltage": 51.20,
    "capacity_ah": 280.00, "commissioned_at": "2026-07-27T08:38:57-04:00" },
  "status": { "ts": "…", "soc": 14.31, "pack_voltage": 50.48, "current_a": -81.54,
    "temperature_c": 28.67, "status": "warning", "active_alarms": 1 } }
```

## GET /api/devices/{device_id}/readings
Time-series for the drill-down charts. `404` if unknown device.

| Query param | Type | Default | Notes |
|---|---|---|---|
| `since` | ISO timestamp | — | **incremental fetch**: only readings after this ts (ascending) |
| `limit` | int 1–5000 | 500 | cap per request |

Without `since`: newest `limit` rows, returned oldest-first (initial chart load).
With `since`: only newer rows (each poll). `latest_ts` is the cursor to send next.

```json
{ "device_id": "BMS-0007", "count": 5, "latest_ts": "2026-07-28T05:31:32.16-04:00",
  "readings": [ { "ts": "…", "soc": 90.68, "pack_voltage": 55.51,
    "current_a": -40.2, "temperature_c": 27.4 } ] }
```

## GET /api/alarms
Alarm feed, newest first.

| Query param | Type | Notes |
|---|---|---|
| `active` | bool | `true` = only open (`cleared_at IS NULL`) |
| `severity` | `info`\|`warning`\|`critical` | filter |
| `device_id` | string | filter to one device |
| `limit` | int 1–1000 (default 100) | cap |

```json
{ "count": 2, "alarms": [
  { "id": 33, "device_id": "BMS-0007", "ts": "…", "code": "LOW_VOLTAGE",
    "severity": "warning", "value": 46.88, "cleared_at": null, "active": true } ] }
```

---

## AI features (FAU Trussed.ai, model gpt-5.4)
Require auth. Rate-limited per user (15/min → `429`). The API key is server-side
only (`TRUSSED_API_KEY`); if unset, these return `503` with a friendly message.

- **GET /api/ai/status** → `{ "configured": bool, "model": "gpt-5.4" }`
- **POST /api/ai/search** — body `{ "query": "critical packs at Harbor Marine below 20%" }`.
  LLM turns English into structured filters, which are applied (parameterized) to
  the fleet. → `{ "explanation", "filters", "count", "devices": [...] }`
- **POST /api/ai/briefing** — no body. Gathers live fleet stats and returns an
  LLM-written health summary → `{ "briefing": "…", "stats": {…} }`

## Notes — per-user CRUD on a pack
All require auth; every note is scoped to the authenticated user.

- **GET /api/devices/{id}/notes** → `{ "count", "notes": [{id, device_id, body, created_at, updated_at}] }`
- **POST /api/devices/{id}/notes** — body `{ "body": "…" }` → the created note. `422` if empty/too long, `404` unknown device.
- **PUT /api/notes/{note_id}** — body `{ "body": "…" }` → updated note. `404` if not the user's note.
- **DELETE /api/notes/{note_id}** → `{ "deleted": <id> }`. `404` if not the user's note.

## WebSocket — realtime fleet feed
**WS /api/ws?token=&lt;jwt&gt;** — authenticated WebSocket. On connect the server sends
an immediate snapshot, then pushes one ~every 2s:
```json
{ "type": "snapshot", "summary": { total, ok, warning, critical, active_alarms },
  "devices": [ { device_id, label, soc, pack_voltage, status, ... } ] }
```
A single server-side broadcaster does one DB read per tick and fans it out to all
clients (cheaper than N clients polling). The UI uses it for the default live view
and shows a "⚡ Realtime" badge; it falls back to HTTP polling when filters/search/
pagination are active. Invalid/missing token → close code 1008.

## Reporting & export
Require auth.

- **GET /api/daily-report?date=YYYY-MM-DD** → `{ "date", "count", "rows": [...] }`
  (defaults to today). Each row is the wide `daily_pack_report` (30 columns).
- **GET /api/export/fleet.{csv|xlsx}** ?status=&site=&q= → downloads the current
  fleet status (all matching rows) as CSV or Excel. `404` on other formats.
- **GET /api/export/daily-report.{csv|xlsx}** ?date= → downloads the daily report.

Downloads carry `Content-Disposition: attachment`. The frontend fetches them with
the Bearer token and saves the returned blob. (PDF is handled client-side via
browser Print / Save-as-PDF of the report view.)

## Production test records (manufacturing / QA)
Simulated, cloud-safe. All require auth.

- **GET /api/production/records** ?product=&part_number=&serial=&from=&to=&station=&fixture=&test_parameter=&result=&limit=&offset= → `{ total, count, records: [...] }` (Pass/Fail lookup)
- **GET /api/production/summary** ?date= → `{ date, total_tested, passed, failed, pass_pct, fail_pct, most_failed_product, most_failed_fixture, most_failed_station }` (defaults to most recent test date)
- **GET /api/production/serial/{serial}** → `{ serial_number, product, tests, passed, failed, records: [...] }` (full history; `404` if unknown)
- **GET /api/production/search** ?q= → cross-entity search over serial / part / product / station / fixture / operator
- **GET /api/export/production.{csv|xlsx}** — same filters as records
- Query builder: `production` source

## Error shape
FastAPI default: `{ "detail": "<message>" }` with `404` (unknown device) or `422`
(invalid enum / out-of-range param).

## Run it
```
cd backend
py -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
Requires the simulator to have seeded data (`py simulator/simulator.py --reset`).
