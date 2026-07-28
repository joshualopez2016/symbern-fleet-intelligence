"""No-code query builder — a whitelist-driven, injection-safe SQL generator.

The UI sends a STRUCTURED query (source + filters + columns + sort + limit); this
module validates every part against a field-mapping registry and emits a fully
PARAMETERIZED SQL statement. Users never write SQL, and only registered
sources/fields/operators are reachable — so there is no injection surface.

  Data Source Selector  -> SOURCES keys
  Field Mapping Engine  -> SOURCES[src]["fields"] (friendly name -> real column + type)
  Dynamic Query Builder -> build_and_run(spec)
"""
from __future__ import annotations

from .db import query_ro


class QBError(Exception):
    pass


# Allowed operators per field type -> SQL operator (or a marker handled below).
OPS_FOR_TYPE = {
    "number":    {"eq": "=", "ne": "<>", "lt": "<", "le": "<=", "gt": ">", "ge": ">="},
    "text":      {"eq": "=", "ne": "<>", "contains": "ILIKE", "starts_with": "ILIKE"},
    "enum":      {"eq": "=", "ne": "<>"},
    "timestamp": {"before": "<", "after": ">", "on": "on"},
    "boolean":   {"eq": "="},
}

# The only sources/fields a query can touch. Columns are OUR strings, never user input.
SOURCES = {
    "fleet": {
        "label": "Fleet (current status)",
        "from": "device_status s JOIN devices d USING (device_id)",
        "fields": {
            "device_id":     {"col": "s.device_id", "type": "text", "label": "Device ID"},
            "label":         {"col": "d.label", "type": "text", "label": "Label"},
            "model":         {"col": "d.model", "type": "text", "label": "Model"},
            "site":          {"col": "d.site", "type": "text", "label": "Site"},
            "company":       {"col": "d.company", "type": "text", "label": "Company"},
            "equipment":     {"col": "d.equipment", "type": "text", "label": "Equipment"},
            "soc":           {"col": "s.soc", "type": "number", "label": "State of charge (%)"},
            "pack_voltage":  {"col": "s.pack_voltage", "type": "number", "label": "Pack voltage (V)"},
            "current_a":     {"col": "s.current_a", "type": "number", "label": "Current (A)"},
            "temperature_c": {"col": "s.temperature_c", "type": "number", "label": "Temperature (C)"},
            "status":        {"col": "s.status", "type": "enum", "label": "Status",
                              "values": ["ok", "warning", "critical"]},
            "active_alarms": {"col": "s.active_alarms", "type": "number", "label": "Active alarms"},
        },
        "default_sort": {"field": "soc", "dir": "asc"},
    },
    "readings": {
        "label": "Telemetry readings",
        "from": "readings",
        "fields": {
            "device_id":     {"col": "device_id", "type": "text", "label": "Device ID"},
            "ts":            {"col": "ts", "type": "timestamp", "label": "Timestamp"},
            "soc":           {"col": "soc", "type": "number", "label": "State of charge (%)"},
            "pack_voltage":  {"col": "pack_voltage", "type": "number", "label": "Pack voltage (V)"},
            "current_a":     {"col": "current_a", "type": "number", "label": "Current (A)"},
            "temperature_c": {"col": "temperature_c", "type": "number", "label": "Temperature (C)"},
        },
        "default_sort": {"field": "ts", "dir": "desc"},
    },
    "alarms": {
        "label": "Alarms",
        "from": "alarms a JOIN devices d USING (device_id)",
        "fields": {
            "device_id": {"col": "a.device_id", "type": "text", "label": "Device ID"},
            "site":      {"col": "d.site", "type": "text", "label": "Site"},
            "company":   {"col": "d.company", "type": "text", "label": "Company"},
            "code":      {"col": "a.code", "type": "enum", "label": "Code",
                          "values": ["LOW_SOC", "LOW_VOLTAGE", "OVER_TEMP"]},
            "severity":  {"col": "a.severity", "type": "enum", "label": "Severity",
                          "values": ["info", "warning", "critical"]},
            "value":     {"col": "a.value", "type": "number", "label": "Tripped value"},
            "ts":        {"col": "a.ts", "type": "timestamp", "label": "Raised at"},
            "active":    {"col": "(a.cleared_at IS NULL)", "type": "boolean", "label": "Active"},
        },
        "default_sort": {"field": "ts", "dir": "desc"},
    },
    "daily_report": {
        "label": "Daily pack report",
        "from": "daily_pack_report",
        "fields": {
            "report_date": {"col": "report_date", "type": "timestamp", "label": "Date"},
            "pack_number": {"col": "pack_number", "type": "text", "label": "Pack number"},
            "company":     {"col": "company", "type": "text", "label": "Company"},
            "equipment":   {"col": "equipment", "type": "text", "label": "Equipment"},
            "location":    {"col": "location", "type": "text", "label": "Location"},
            "soc_avg":     {"col": "soc_avg", "type": "number", "label": "SoC avg (%)"},
            "soc_min":     {"col": "soc_min", "type": "number", "label": "SoC min (%)"},
            "voltage_avg": {"col": "voltage_avg", "type": "number", "label": "Voltage avg (V)"},
            "temp_max":    {"col": "temp_max", "type": "number", "label": "Temp max (C)"},
            "alarms_raised":   {"col": "alarms_raised", "type": "number", "label": "Alarms raised"},
            "over_temp_events": {"col": "over_temp_events", "type": "number", "label": "Over-temp events"},
        },
        "default_sort": {"field": "report_date", "dir": "desc"},
    },
}

MAX_LIMIT = 1000


def sources_schema() -> dict:
    """UI-facing description of every source, field, type, operator, and enum."""
    out = {}
    for name, s in SOURCES.items():
        out[name] = {
            "label": s["label"],
            "default_sort": s.get("default_sort"),
            "fields": [
                {
                    "name": fn,
                    "label": fd["label"],
                    "type": fd["type"],
                    "ops": list(OPS_FOR_TYPE[fd["type"]].keys()),
                    "values": fd.get("values"),
                }
                for fn, fd in s["fields"].items()
            ],
        }
    return out


def _condition(field_def: dict, op: str, value) -> tuple[str, list]:
    ftype = field_def["type"]
    col = field_def["col"]
    allowed = OPS_FOR_TYPE[ftype]
    if op not in allowed:
        raise QBError(f"operator {op!r} not allowed for {ftype} field")

    if ftype == "text":
        if op in ("contains", "starts_with"):
            v = f"%{value}%" if op == "contains" else f"{value}%"
            return f"{col} ILIKE %s", [v]
        return f"{col} {allowed[op]} %s", [str(value)]
    if ftype == "enum":
        if value not in (field_def.get("values") or []):
            raise QBError(f"{value!r} is not an allowed value")
        return f"{col} {allowed[op]} %s", [value]
    if ftype == "number":
        try:
            num = float(value)
        except (TypeError, ValueError):
            raise QBError(f"{value!r} is not a number")
        return f"{col} {allowed[op]} %s", [num]
    if ftype == "boolean":
        b = value in (True, "true", "True", 1, "1")
        return f"{col} = %s", [b]
    if ftype == "timestamp":
        if op == "on":
            return f"{col}::date = %s::date", [value]
        return f"{col} {allowed[op]} %s", [value]
    raise QBError(f"unsupported field type {ftype!r}")


def build_and_run(spec: dict) -> dict:
    src = SOURCES.get(spec.get("source"))
    if not src:
        raise QBError("unknown data source")
    fields = src["fields"]

    columns = [c for c in (spec.get("columns") or []) if c in fields] or list(fields.keys())
    select_sql = ", ".join(f'{fields[c]["col"]} AS {c}' for c in columns)

    where_parts, params = [], []
    for f in (spec.get("filters") or []):
        fd = fields.get(f.get("field"))
        if not fd:
            raise QBError(f"unknown field {f.get('field')!r}")
        if f.get("value") in (None, ""):
            continue
        frag, p = _condition(fd, f.get("op"), f.get("value"))
        where_parts.append(frag)
        params += p
    where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

    sort = spec.get("sort") or src.get("default_sort") or {}
    order_sql = ""
    if sort.get("field") in fields:
        direction = "DESC" if str(sort.get("dir", "asc")).lower() == "desc" else "ASC"
        order_sql = f'ORDER BY {fields[sort["field"]]["col"]} {direction}'

    try:
        limit = int(spec.get("limit") or 200)
    except (TypeError, ValueError):
        limit = 200
    limit = max(1, min(limit, MAX_LIMIT))

    sql = f"SELECT {select_sql} FROM {src['from']} {where_sql} {order_sql} LIMIT {limit}".strip()
    rows = query_ro(sql, tuple(params))  # runs on the read-only role — cannot write
    return {"columns": columns, "rows": rows, "count": len(rows), "sql": sql, "params": params}
