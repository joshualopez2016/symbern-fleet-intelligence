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

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import ai, auth, exports, querybuilder
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


# ---- Authentication --------------------------------------------------------

class LoginBody(BaseModel):
    email: str
    password: str


@app.post("/api/auth/login")
def login(body: LoginBody) -> dict:
    user = auth.authenticate(body.email, body.password)
    if not user:
        raise HTTPException(401, "Invalid email or password")
    token = auth.create_token(user["email"], user["role"])
    return {"token": token, "user": {"email": user["email"], "role": user["role"]}}


@app.get("/api/auth/me")
def me(user: dict = Depends(auth.require_user)) -> dict:
    return {"email": user["email"], "role": user["role"]}


@app.post("/api/auth/logout")
def logout(user: dict = Depends(auth.require_user)) -> dict:
    # Stateless JWT: the client discards its token. Endpoint exists for symmetry.
    return {"ok": True}


@app.get("/api/config/thresholds")
def get_thresholds(_user: dict = Depends(auth.require_user)) -> dict:
    """Serve the SAME limits the simulator alarms on, so the UI colors match."""
    return THRESHOLDS


@app.get("/api/fleet/summary")
def get_fleet_summary(_user: dict = Depends(auth.require_user)) -> dict:
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


def _split(v: Optional[str]) -> list[str]:
    return [x.strip() for x in v.split(",") if x.strip()] if v else []


def _fleet_where(*, status=None, statuses=None, sites=None, companies=None,
                 equipment=None, soc_min=None, soc_max=None, has_alarms=False,
                 q=None, since=None):
    """Build the parameterized WHERE for a fleet query. Shared by the grid and
    the exports so both honor the same advanced filters. Returns (sql, params)."""
    where, params = [], []
    st = [s for s in (_split(statuses) or ([status] if status else [])) if s in VALID_STATUS]
    if st:
        where.append(f"s.status IN ({','.join(['%s'] * len(st))})")
        params += st
    for col, vals in (("d.site", _split(sites)), ("d.company", _split(companies)),
                      ("d.equipment", _split(equipment))):
        if vals:
            where.append(f"{col} IN ({','.join(['%s'] * len(vals))})")
            params += vals
    if soc_min is not None:
        where.append("s.soc >= %s")
        params.append(soc_min)
    if soc_max is not None:
        where.append("s.soc <= %s")
        params.append(soc_max)
    if has_alarms:
        where.append("s.active_alarms > 0")
    if q:
        where.append("(s.device_id ILIKE %s OR d.label ILIKE %s)")
        params += [f"%{q}%", f"%{q}%"]
    if since is not None:
        where.append("s.ts > %s")
        params.append(since)
    return (("WHERE " + " AND ".join(where)) if where else ""), params


@app.get("/api/fleet/filter-options")
def fleet_filter_options(_user: dict = Depends(auth.require_user)) -> dict:
    """Distinct values for the advanced-filter dropdowns."""
    return {
        "sites": [r["site"] for r in query("SELECT DISTINCT site FROM devices ORDER BY site")],
        "companies": [r["company"] for r in query("SELECT DISTINCT company FROM devices ORDER BY company")],
        "equipment": [r["equipment"] for r in query("SELECT DISTINCT equipment FROM devices ORDER BY equipment")],
    }


@app.get("/api/fleet")
def get_fleet(
    status: Optional[str] = Query(None, description="single status (stat pills)"),
    statuses: Optional[str] = Query(None, description="comma list: ok,warning,critical"),
    sites: Optional[str] = Query(None, description="comma list of sites"),
    companies: Optional[str] = Query(None, description="comma list of companies"),
    equipment: Optional[str] = Query(None, description="comma list of equipment"),
    soc_min: Optional[float] = Query(None, ge=0, le=100),
    soc_max: Optional[float] = Query(None, ge=0, le=100),
    has_alarms: bool = Query(False, description="only packs with active alarms"),
    q: Optional[str] = Query(None, description="search device_id / label"),
    since: Optional[datetime] = Query(None, description="only devices updated after this ts (delta poll)"),
    limit: int = Query(500, ge=1, le=MAX_FLEET),
    offset: int = Query(0, ge=0),
    _user: dict = Depends(auth.require_user),
) -> dict:
    """Fleet grid — reads ONLY device_status (one row/device), joined to devices.
    Supports multi-select status/site/company/equipment, an SoC range, an
    active-alarms toggle, search, and delta polling. Never scans readings."""
    if status is not None and status not in VALID_STATUS:
        raise HTTPException(422, f"invalid status; expected one of {sorted(VALID_STATUS)}")

    where_sql, params = _fleet_where(
        status=status, statuses=statuses, sites=sites, companies=companies,
        equipment=equipment, soc_min=soc_min, soc_max=soc_max,
        has_alarms=has_alarms, q=q, since=since,
    )
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
def get_device(device_id: str, _user: dict = Depends(auth.require_user)) -> dict:
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
    _user: dict = Depends(auth.require_user),
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
    _user: dict = Depends(auth.require_user),
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


# ---- AI features (FAU Trussed.ai) ------------------------------------------

class AiSearchBody(BaseModel):
    query: str


@app.get("/api/ai/status")
def ai_status(_user: dict = Depends(auth.require_user)) -> dict:
    return {"configured": ai.is_configured(), "model": ai.MODEL}


@app.post("/api/ai/search")
def ai_search(body: AiSearchBody, user: dict = Depends(auth.require_user)) -> dict:
    """Natural-language fleet search: English -> structured filters -> matching devices."""
    q = (body.query or "").strip()
    if not q:
        raise HTTPException(400, "Please type a question first.")
    if not ai.check_rate_limit(user["email"]):
        raise HTTPException(429, "Too many AI requests — please wait a minute.")
    try:
        filters = ai.nl_to_filters(q)
    except ai.AIError as e:
        raise HTTPException(e.status, e.message)

    where, params = [], []
    status = str(filters.get("status") or "").strip()
    if status in VALID_STATUS:
        where.append("s.status = %s")
        params.append(status)
    for col, key in (("d.site", "site"), ("d.company", "company"), ("d.equipment", "equipment")):
        val = str(filters.get(key) or "").strip()
        if val:
            where.append(f"{col} = %s")
            params.append(val)
    if isinstance(filters.get("soc_max"), (int, float)):
        where.append("s.soc <= %s")
        params.append(filters["soc_max"])
    if isinstance(filters.get("soc_min"), (int, float)):
        where.append("s.soc >= %s")
        params.append(filters["soc_min"])
    search = str(filters.get("search") or "").strip()
    if search:
        where.append("(s.device_id ILIKE %s OR d.label ILIKE %s)")
        params.extend([f"%{search}%", f"%{search}%"])
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    rows = query(
        f"""
        SELECT s.device_id, d.label, d.model, d.site,
               s.soc, s.pack_voltage, s.current_a, s.temperature_c,
               s.status, s.active_alarms, s.ts
        FROM device_status s JOIN devices d USING (device_id)
        {where_sql}
        ORDER BY CASE s.status WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END,
                 s.soc ASC
        LIMIT 200
        """,
        tuple(params),
    )
    return {"explanation": filters.get("explanation", ""), "filters": filters,
            "count": len(rows), "devices": rows}


@app.post("/api/ai/briefing")
def ai_briefing(user: dict = Depends(auth.require_user)) -> dict:
    """AI fleet-health briefing, grounded in live stats."""
    if not ai.check_rate_limit(user["email"]):
        raise HTTPException(429, "Too many AI requests — please wait a minute.")
    summary = query_one(
        """
        SELECT count(*) AS total,
               count(*) FILTER (WHERE status = 'ok')       AS ok,
               count(*) FILTER (WHERE status = 'warning')  AS warning,
               count(*) FILTER (WHERE status = 'critical') AS critical,
               COALESCE(sum(active_alarms), 0)             AS active_alarms
        FROM device_status
        """
    )
    worst = query(
        """
        SELECT s.device_id, d.label, d.company, d.equipment, d.site,
               s.soc, s.pack_voltage, s.temperature_c, s.status, s.active_alarms
        FROM device_status s JOIN devices d USING (device_id)
        WHERE s.status <> 'ok'
        ORDER BY CASE s.status WHEN 'critical' THEN 0 ELSE 1 END, s.soc ASC
        LIMIT 8
        """
    )
    alarm_counts = query(
        "SELECT code, count(*) AS n FROM alarms WHERE cleared_at IS NULL GROUP BY code ORDER BY n DESC"
    )
    stats = {"summary": summary, "worst_packs": worst, "active_alarms_by_type": alarm_counts}
    try:
        text = ai.fleet_briefing(stats)
    except ai.AIError as e:
        raise HTTPException(e.status, e.message)
    return {"briefing": text, "stats": stats}


# ---- Notes (per-user CRUD on a pack) ---------------------------------------

class NoteBody(BaseModel):
    body: str


def _clean_note(text: str) -> str:
    text = (text or "").strip()
    if not text:
        raise HTTPException(422, "Note cannot be empty.")
    if len(text) > 2000:
        raise HTTPException(422, "Note too long (max 2000 characters).")
    return text


@app.get("/api/devices/{device_id}/notes")
def list_notes(device_id: str, user: dict = Depends(auth.require_user)) -> dict:
    rows = query(
        "SELECT id, device_id, body, created_at, updated_at FROM notes "
        "WHERE device_id = %s AND user_id = %s ORDER BY updated_at DESC",
        (device_id, user["id"]),
    )
    return {"count": len(rows), "notes": rows}


@app.post("/api/devices/{device_id}/notes")
def create_note(device_id: str, body: NoteBody, user: dict = Depends(auth.require_user)) -> dict:
    text = _clean_note(body.body)
    if query_one("SELECT 1 FROM devices WHERE device_id = %s", (device_id,)) is None:
        raise HTTPException(404, f"device {device_id!r} not found")
    return query_one(
        "INSERT INTO notes (user_id, device_id, body) VALUES (%s, %s, %s) "
        "RETURNING id, device_id, body, created_at, updated_at",
        (user["id"], device_id, text),
    )


@app.put("/api/notes/{note_id}")
def update_note(note_id: int, body: NoteBody, user: dict = Depends(auth.require_user)) -> dict:
    text = _clean_note(body.body)
    row = query_one(
        "UPDATE notes SET body = %s, updated_at = now() WHERE id = %s AND user_id = %s "
        "RETURNING id, device_id, body, created_at, updated_at",
        (text, note_id, user["id"]),
    )
    if row is None:
        raise HTTPException(404, "note not found")
    return row


@app.delete("/api/notes/{note_id}")
def delete_note(note_id: int, user: dict = Depends(auth.require_user)) -> dict:
    row = query_one(
        "DELETE FROM notes WHERE id = %s AND user_id = %s RETURNING id",
        (note_id, user["id"]),
    )
    if row is None:
        raise HTTPException(404, "note not found")
    return {"deleted": row["id"]}


# ---- Reporting & export ----------------------------------------------------

FLEET_EXPORT_COLS = [
    "device_id", "label", "model", "site", "company", "equipment",
    "soc", "pack_voltage", "current_a", "temperature_c", "status", "active_alarms", "ts",
]

XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _fleet_export_rows(**filters):
    where_sql, params = _fleet_where(**filters)
    return query(
        f"""
        SELECT s.device_id, d.label, d.model, d.site, d.company, d.equipment,
               s.soc, s.pack_voltage, s.current_a, s.temperature_c, s.status,
               s.active_alarms, s.ts
        FROM device_status s JOIN devices d USING (device_id)
        {where_sql}
        ORDER BY CASE s.status WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END,
                 s.soc ASC
        """,
        tuple(params),
    )


def _daily_report_rows(day):
    if day:
        return query(
            "SELECT * FROM daily_pack_report WHERE report_date = %s ORDER BY pack_number",
            (day,),
        )
    return query("SELECT * FROM daily_pack_report WHERE report_date = CURRENT_DATE ORDER BY pack_number")


def _export_response(fmt: str, headers: list, rows: list, basename: str):
    if fmt == "csv":
        content = exports.rows_to_csv(headers, rows)
        return Response(
            content=content, media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{basename}.csv"'},
        )
    data = exports.rows_to_xlsx(headers, rows, basename)
    return Response(
        content=data, media_type=XLSX_MEDIA,
        headers={"Content-Disposition": f'attachment; filename="{basename}.xlsx"'},
    )


@app.get("/api/daily-report")
def daily_report(date: Optional[str] = None, _user: dict = Depends(auth.require_user)) -> dict:
    """Daily per-pack report (JSON) for the UI. Defaults to today."""
    rows = _daily_report_rows(date)
    report_date = date or (str(rows[0]["report_date"]) if rows else None)
    return {"date": report_date, "count": len(rows), "rows": rows}


@app.get("/api/export/fleet.{fmt}")
def export_fleet(
    fmt: str,
    status: Optional[str] = None,
    statuses: Optional[str] = None,
    sites: Optional[str] = None,
    companies: Optional[str] = None,
    equipment: Optional[str] = None,
    soc_min: Optional[float] = None,
    soc_max: Optional[float] = None,
    has_alarms: bool = False,
    q: Optional[str] = None,
    _user: dict = Depends(auth.require_user),
):
    if fmt not in ("csv", "xlsx"):
        raise HTTPException(404, "format must be csv or xlsx")
    if status is not None and status not in VALID_STATUS:
        raise HTTPException(422, f"invalid status; expected one of {sorted(VALID_STATUS)}")
    rows = _fleet_export_rows(
        status=status, statuses=statuses, sites=sites, companies=companies,
        equipment=equipment, soc_min=soc_min, soc_max=soc_max, has_alarms=has_alarms, q=q,
    )
    return _export_response(fmt, FLEET_EXPORT_COLS, rows, "fleet")


@app.get("/api/query/sources")
def query_sources(_user: dict = Depends(auth.require_user)) -> dict:
    """Field-mapping registry for the no-code query builder."""
    return querybuilder.sources_schema()


class QuerySpec(BaseModel):
    source: str
    columns: Optional[list] = None
    filters: Optional[list] = None
    sort: Optional[dict] = None
    limit: Optional[int] = None


@app.post("/api/query/run")
def query_run(spec: QuerySpec, _user: dict = Depends(auth.require_user)) -> dict:
    """Run a structured query -> parameterized SQL. Users never write SQL."""
    try:
        return querybuilder.build_and_run(spec.model_dump())
    except querybuilder.QBError as e:
        raise HTTPException(422, str(e))


@app.get("/api/export/daily-report.{fmt}")
def export_daily_report(
    fmt: str,
    date: Optional[str] = None,
    _user: dict = Depends(auth.require_user),
):
    if fmt not in ("csv", "xlsx"):
        raise HTTPException(404, "format must be csv or xlsx")
    rows = _daily_report_rows(date)
    headers = list(rows[0].keys()) if rows else [
        "report_date", "pack_number", "pack_label", "model", "company", "equipment", "location",
    ]
    return _export_response(fmt, headers, rows, "daily_pack_report")
