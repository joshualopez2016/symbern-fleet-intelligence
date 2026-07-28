"""CSV / XLSX export helpers.

Rows are dicts (as returned by db.query). Values are emitted in the given header
order; datetimes are stringified (openpyxl rejects tz-aware datetimes).
"""
from __future__ import annotations

import csv
import datetime as _dt
import io

from openpyxl import Workbook
from openpyxl.styles import Font


def _scalar(v):
    if isinstance(v, (_dt.datetime, _dt.date)):
        return v.isoformat()
    return v


def rows_to_csv(headers: list[str], rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    for r in rows:
        w.writerow([_scalar(r.get(h)) for h in headers])
    return buf.getvalue()


def rows_to_xlsx(headers: list[str], rows: list[dict], sheet_name: str = "Export") -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name[:31]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for r in rows:
        ws.append([_scalar(r.get(h)) for h in headers])
    ws.freeze_panes = "A2"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
