"""BMS Cloud Dashboard — read-only API (FastAPI).

The API only READS. The simulator is the only writer. Endpoints:

    GET /api/health
    GET /api/config/thresholds
    GET /api/fleet                      ?status=&site=&q=&since=&limit=&offset=
    GET /api/devices/{device_id}
    GET /api/devices/{device_id}/readings   ?since=&limit=
    GET /api/alarms                     ?active=&severity=&device_id=&limit=

Every query is parameterized (%s). Responses are JSON only.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .db import pool, query, query_one

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config.thresholds import THRESHOLDS  # noqa: E402

MAX_READINGS = 5000          # hard cap so a single request can't scan unbounded history
MAX_FLEET = 5000
MAX_ALARMS = 1000

VALID_STATUS = {"ok", "warning", "critical"}
VALID_SEVERITY = {"info", "warning", "critical"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool.open()
    yield
    pool.close()


app = FastAPI(title="BMS Cloud Dashboard API", version="0.1.0", lifespan=lifespan)

# Dev CORS: Vite dev server. Tighten for any real deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    row = query_one("SELECT 1 AS ok")
    return {"status": "ok" if row and row["ok"] == 1 else "degraded"}


@app.get("/api/config/thresholds")
def get_thresholds() -> dict:
    """Serve the SAME limits the simulator alarms on, so the UI colors match."""
    return THRESHOLDS


@app.get("/api/fleet/summary")
def get_fleet_summary() -> dict:
    """Whole-fleet status tallies from a single aggregate over device_status.
    Cost is independent of how the grid is paginated, so the UI can show true
    counts for thousands of devices without shipping every row."""
    row = query_one(
        """
        SELECT count(*)                                    AS total,
               count(*) FILTER (WHERE status = 'ok')       AS ok,
               count(*) FILTER (WHERE status = 'warning')  AS warning,
               count(*) FILTER (WHERE status = 'critical') AS critical,
               COALESCE(sum(active_alarms), 0)             AS active_alarms
        FROM device_status
        """
    )
    return row


@app.get("/api/fleet")
def get_fleet(
    status: Optional[str] = Query(None, description="ok | warning | critical"),
    site: Optional[str] = None,
    q: Optional[str] = Query(None, description="search device_id / label"),
    since: Optional[datetime] = Query(None, description="only devices updated after this ts (delta poll)"),
    limit: int = Query(500, ge=1, le=MAX_FLEET),
    offset: int = Query(0, ge=0),
) -> dict:
    """Fleet grid — reads ONLY device_status (one row/device), joined to devices
    for label/site/model. Never scans the readings time-series."""
    if status is not None and status not in VALID_STATUS:
        raise HTTPException(422, f"invalid status; expected one of {sorted(VALID_STATUS)}")

    where = []
    params: list = []
    if status is not None:
        where.append("s.status = %s")
        params.append(status)
    if site is not None:
        where.append("d.site = %s")
        params.append(site)
    if q is not None:
        where.append("(s.device_id ILIKE %s OR d.label ILIKE %s)")
        params.extend([f"%{q}%", f"%{q}%"])
    if since is not None:
        where.append("s.ts > %s")
        params.append(since)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    total = query_one(
        f"SELECT count(*) AS n FROM device_status s JOIN devices d USING (device_id) {where_sql}",
        tuple(params),
    )["n"]

    rows = query(
        f"""
        SELECT s.device_id, d.label, d.model, d.site,
               s.soc, s.pack_voltage, s.current_a, s.temperature_c,
               s.status, s.active_alarms, s.ts
        FROM device_status s
        JOIN devices d USING (device_id)
        {where_sql}
        ORDER BY CASE s.status WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END,
                 s.soc ASC
        LIMIT %s OFFSET %s
        """,
        tuple(params) + (limit, offset),
    )
    return {"total": total, "count": len(rows), "devices": rows}


@app.get("/api/devices/{device_id}")
def get_device(device_id: str) -> dict:
    """Device detail: static metadata + its latest status snapshot."""
    device = query_one(
        "SELECT device_id, label, model, site, cell_count, nominal_voltage, "
        "capacity_ah, commissioned_at FROM devices WHERE device_id = %s",
        (device_id,),
    )
    if device is None:
        raise HTTPException(404, f"device {device_id!r} not found")
    status = query_one(
        "SELECT ts, soc, pack_voltage, current_a, temperature_c, status, active_alarms "
        "FROM device_status WHERE device_id = %s",
        (device_id,),
    )
    return {"device": device, "status": status}


@app.get("/api/devices/{device_id}/readings")
def get_readings(
    device_id: str,
    since: Optional[datetime] = Query(None, description="return readings AFTER this ts (delta fetch)"),
    limit: int = Query(500, ge=1, le=MAX_READINGS),
) -> dict:
    """Time-series for the drill-down charts.

    With `since`, returns only newer rows (ascending) — the incremental-fetch
    path the frontend uses on every poll. Without it, returns the most recent
    `limit` rows (ascending) for the initial chart load.
    """
    if query_one("SELECT 1 FROM devices WHERE device_id = %s", (device_id,)) is None:
        raise HTTPException(404, f"device {device_id!r} not found")

    if since is not None:
        rows = query(
            """
            SELECT ts, soc, pack_voltage, current_a, temperature_c
            FROM readings
            WHERE device_id = %s AND ts > %s
            ORDER BY ts ASC
            LIMIT %s
            """,
            (device_id, since, limit),
        )
    else:
        # newest `limit`, returned oldest-first so charts plot left-to-right
        rows = query(
            """
            SELECT ts, soc, pack_voltage, current_a, temperature_c FROM (
                SELECT ts, soc, pack_voltage, current_a, temperature_c
                FROM readings
                WHERE device_id = %s
                ORDER BY ts DESC
                LIMIT %s
            ) t
            ORDER BY ts ASC
            """,
            (device_id, limit),
        )
    latest = rows[-1]["ts"] if rows else since
    return {"device_id": device_id, "count": len(rows), "latest_ts": latest, "readings": rows}


@app.get("/api/alarms")
def get_alarms(
    active: Optional[bool] = Query(None, description="true = only open alarms"),
    severity: Optional[str] = Query(None, description="info | warning | critical"),
    device_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=MAX_ALARMS),
) -> dict:
    if severity is not None and severity not in VALID_SEVERITY:
        raise HTTPException(422, f"invalid severity; expected one of {sorted(VALID_SEVERITY)}")

    where = []
    params: list = []
    if active is True:
        where.append("cleared_at IS NULL")
    elif active is False:
        where.append("cleared_at IS NOT NULL")
    if severity is not None:
        where.append("severity = %s")
        params.append(severity)
    if device_id is not None:
        where.append("device_id = %s")
        params.append(device_id)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    rows = query(
        f"""
        SELECT id, device_id, ts, code, severity, value, cleared_at,
               (cleared_at IS NULL) AS active
        FROM alarms
        {where_sql}
        ORDER BY ts DESC, id DESC
        LIMIT %s
        """,
        tuple(params) + (limit,),
    )
    return {"count": len(rows), "alarms": rows}
