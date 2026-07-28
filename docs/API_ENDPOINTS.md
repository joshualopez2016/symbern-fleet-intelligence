# API Endpoints — BMS Cloud Dashboard

Read-only FastAPI service. Base URL in dev: `http://127.0.0.1:8000`. All
responses are JSON; all SQL is parameterized (`%s`), no string interpolation.
Interactive docs (Swagger) are served at `/docs`.

`NUMERIC` columns are returned as JSON **numbers** (not strings). Timestamps are
ISO-8601 with timezone.

---

## GET /api/health
Liveness + DB reachability. → `{ "status": "ok" }`

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
| `status` | `ok`\|`warning`\|`critical` | — | filter by current status |
| `site` | string | — | filter by depot/location |
| `q` | string | — | search `device_id` / `label` (ILIKE) |
| `since` | ISO timestamp | — | **delta poll**: only devices updated after this ts |
| `limit` | int 1–5000 | 500 | pagination |
| `offset` | int ≥0 | 0 | pagination |

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

## Error shape
FastAPI default: `{ "detail": "<message>" }` with `404` (unknown device) or `422`
(invalid enum / out-of-range param).

## Run it
```
cd backend
py -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
Requires the simulator to have seeded data (`py simulator/simulator.py --reset`).
