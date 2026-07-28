"""Integration tests for the BMS Cloud Dashboard API.

Runs against a live server (start the API + simulator first). Covers auth,
the core data endpoints, notes CRUD, and error/edge cases (401/422/404).

    py -m pytest tests/ -v        # from the project root, API running on :8000

Override the target with BMS_API (e.g. BMS_API=http://127.0.0.1:8000).
AI tests only check config/auth — they do not spend LLM budget.
"""
import os
import uuid

import pytest
import requests

BASE = os.environ.get("BMS_API", "http://127.0.0.1:8000")
ADMIN = ("admin@bms.local", "Admin#2026")
VIEWER = ("viewer@bms.local", "Viewer#2026")


def _login(email, password):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    r.raise_for_status()
    return r.json()["token"]


@pytest.fixture(scope="session")
def admin():
    return {"Authorization": f"Bearer {_login(*ADMIN)}"}


@pytest.fixture(scope="session")
def viewer():
    return {"Authorization": f"Bearer {_login(*VIEWER)}"}


@pytest.fixture(scope="session")
def device_id(admin):
    r = requests.get(f"{BASE}/api/fleet?limit=1", headers=admin, timeout=15)
    return r.json()["devices"][0]["device_id"]


# ---- health & auth ---------------------------------------------------------

def test_health_is_open():
    r = requests.get(f"{BASE}/api/health", timeout=15)
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_protected_requires_auth():
    r = requests.get(f"{BASE}/api/fleet/summary", timeout=15)
    assert r.status_code == 401


def test_login_bad_password_401():
    r = requests.post(f"{BASE}/api/auth/login", json={"email": ADMIN[0], "password": "wrong"}, timeout=15)
    assert r.status_code == 401


def test_login_and_me(admin):
    r = requests.get(f"{BASE}/api/auth/me", headers=admin, timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == ADMIN[0]
    assert body["role"] == "administrator"


def test_bad_token_401():
    r = requests.get(f"{BASE}/api/fleet/summary", headers={"Authorization": "Bearer garbage"}, timeout=15)
    assert r.status_code == 401


# ---- fleet -----------------------------------------------------------------

def test_fleet_summary_shape(admin):
    r = requests.get(f"{BASE}/api/fleet/summary", headers=admin, timeout=15)
    assert r.status_code == 200
    b = r.json()
    for k in ("total", "ok", "warning", "critical", "active_alarms"):
        assert k in b
    assert b["total"] == b["ok"] + b["warning"] + b["critical"]


def test_fleet_status_filter(admin):
    r = requests.get(f"{BASE}/api/fleet?status=warning&limit=50", headers=admin, timeout=15)
    assert r.status_code == 200
    assert all(d["status"] == "warning" for d in r.json()["devices"])


def test_fleet_invalid_status_422(admin):
    r = requests.get(f"{BASE}/api/fleet?status=bogus", headers=admin, timeout=15)
    assert r.status_code == 422


def test_fleet_pagination_bounded(admin):
    r = requests.get(f"{BASE}/api/fleet?limit=5", headers=admin, timeout=15)
    assert r.status_code == 200
    assert len(r.json()["devices"]) <= 5


def test_filter_options(admin):
    r = requests.get(f"{BASE}/api/fleet/filter-options", headers=admin, timeout=15)
    assert r.status_code == 200
    b = r.json()
    for k in ("sites", "companies", "equipment"):
        assert isinstance(b[k], list) and b[k]


def test_fleet_multi_status(admin):
    r = requests.get(f"{BASE}/api/fleet?statuses=warning,critical&limit=200", headers=admin, timeout=15)
    assert r.status_code == 200
    assert all(d["status"] in ("warning", "critical") for d in r.json()["devices"])


def test_fleet_soc_range(admin):
    r = requests.get(f"{BASE}/api/fleet?soc_min=0&soc_max=25&limit=200", headers=admin, timeout=15)
    assert r.status_code == 200
    assert all(0 <= d["soc"] <= 25 for d in r.json()["devices"])


def test_fleet_has_alarms(admin):
    r = requests.get(f"{BASE}/api/fleet?has_alarms=true&limit=200", headers=admin, timeout=15)
    assert r.status_code == 200
    assert all(d["active_alarms"] > 0 for d in r.json()["devices"])


# ---- devices & readings ----------------------------------------------------

def test_device_detail(admin, device_id):
    r = requests.get(f"{BASE}/api/devices/{device_id}", headers=admin, timeout=15)
    assert r.status_code == 200
    assert r.json()["device"]["device_id"] == device_id


def test_device_unknown_404(admin):
    r = requests.get(f"{BASE}/api/devices/NOPE-9999", headers=admin, timeout=15)
    assert r.status_code == 404


def test_readings_since_returns_only_newer(admin, device_id):
    first = requests.get(f"{BASE}/api/devices/{device_id}/readings?limit=5", headers=admin, timeout=15).json()
    cursor = first["latest_ts"]
    if not cursor:
        pytest.skip("no readings yet")
    delta = requests.get(
        f"{BASE}/api/devices/{device_id}/readings?since={cursor}", headers=admin, timeout=15
    ).json()
    assert all(row["ts"] > cursor for row in delta["readings"])


# ---- alarms ----------------------------------------------------------------

def test_alarms_active_only(admin):
    r = requests.get(f"{BASE}/api/alarms?active=true&limit=50", headers=admin, timeout=15)
    assert r.status_code == 200
    assert all(a["active"] is True for a in r.json()["alarms"])


# ---- AI (no LLM spend) -----------------------------------------------------

def test_ai_status(admin):
    r = requests.get(f"{BASE}/api/ai/status", headers=admin, timeout=15)
    assert r.status_code == 200
    assert isinstance(r.json()["configured"], bool)


def test_ai_search_requires_auth():
    r = requests.post(f"{BASE}/api/ai/search", json={"query": "x"}, timeout=15)
    assert r.status_code == 401


# ---- query builder ---------------------------------------------------------

def test_query_sources(admin):
    r = requests.get(f"{BASE}/api/query/sources", headers=admin, timeout=15)
    assert r.status_code == 200
    assert "fleet" in r.json()


def test_query_run_parameterized(admin):
    spec = {
        "source": "fleet",
        "columns": ["device_id", "soc", "status"],
        "filters": [{"field": "soc", "op": "lt", "value": 30}],
        "sort": {"field": "soc", "dir": "asc"},
        "limit": 10,
    }
    r = requests.post(f"{BASE}/api/query/run", headers=admin, json=spec, timeout=15)
    assert r.status_code == 200
    b = r.json()
    assert all(row["soc"] < 30 for row in b["rows"])
    assert "%s" in b["sql"]  # values are bound, not inlined


def test_query_rejects_unknown_field(admin):
    spec = {"source": "fleet", "filters": [{"field": "soc); DROP TABLE devices;--", "op": "eq", "value": 1}]}
    r = requests.post(f"{BASE}/api/query/run", headers=admin, json=spec, timeout=15)
    assert r.status_code == 422


def test_query_injection_in_value_is_safe(admin):
    spec = {
        "source": "fleet",
        "columns": ["device_id"],
        "filters": [{"field": "company", "op": "eq", "value": "x'); DROP TABLE devices;--"}],
    }
    r = requests.post(f"{BASE}/api/query/run", headers=admin, json=spec, timeout=15)
    assert r.status_code == 200
    assert r.json()["count"] == 0
    assert requests.get(f"{BASE}/api/fleet/summary", headers=admin, timeout=15).json()["total"] > 0


def test_query_requires_auth():
    r = requests.post(f"{BASE}/api/query/run", json={"source": "fleet"}, timeout=15)
    assert r.status_code == 401


# ---- support assistant + tickets -------------------------------------------

def test_assistant_requires_auth():
    r = requests.post(f"{BASE}/api/assistant/chat",
                      json={"messages": [{"role": "user", "content": "hi"}]}, timeout=15)
    assert r.status_code == 401


def test_ticket_create_and_list(admin):
    created = requests.post(f"{BASE}/api/support/tickets", headers=admin,
                            json={"subject": "pytest", "category": "IT", "body": "test body"}, timeout=15)
    assert created.status_code == 200
    tid = created.json()["id"]
    lst = requests.get(f"{BASE}/api/support/tickets", headers=admin, timeout=15).json()
    assert any(t["id"] == tid for t in lst["tickets"])


def test_ticket_bad_category(admin):
    r = requests.post(f"{BASE}/api/support/tickets", headers=admin,
                      json={"subject": "x", "category": "Nope", "body": "y"}, timeout=15)
    assert r.status_code == 422


# ---- production test records -----------------------------------------------

def test_production_records_filter(admin):
    r = requests.get(f"{BASE}/api/production/records?result=Fail&limit=50", headers=admin, timeout=15)
    assert r.status_code == 200
    assert all(rec["result"] == "Fail" for rec in r.json()["records"])


def test_production_summary(admin):
    r = requests.get(f"{BASE}/api/production/summary", headers=admin, timeout=15)
    assert r.status_code == 200
    b = r.json()
    assert b["passed"] + b["failed"] == b["total_tested"]


def test_production_serial_history(admin):
    serial = requests.get(f"{BASE}/api/production/records?limit=1", headers=admin, timeout=15).json()["records"][0]["serial_number"]
    r = requests.get(f"{BASE}/api/production/serial/{serial}", headers=admin, timeout=15)
    assert r.status_code == 200 and r.json()["tests"] > 0
    assert requests.get(f"{BASE}/api/production/serial/NOPE-XXX", headers=admin, timeout=15).status_code == 404


def test_production_search(admin):
    r = requests.get(f"{BASE}/api/production/search?q=FIX-C", headers=admin, timeout=15)
    assert r.status_code == 200 and r.json()["count"] > 0


def test_production_requires_auth():
    assert requests.get(f"{BASE}/api/production/summary", timeout=15).status_code == 401


# ---- notes CRUD ------------------------------------------------------------

def test_notes_full_crud(admin, device_id):
    body = f"pytest note {uuid.uuid4().hex[:8]}"
    # CREATE
    created = requests.post(
        f"{BASE}/api/devices/{device_id}/notes", headers=admin, json={"body": body}, timeout=15
    )
    assert created.status_code == 200
    note = created.json()
    note_id = note["id"]
    assert note["body"] == body
    try:
        # READ (list contains it)
        listed = requests.get(f"{BASE}/api/devices/{device_id}/notes", headers=admin, timeout=15).json()
        assert any(n["id"] == note_id for n in listed["notes"])
        # UPDATE
        upd = requests.put(f"{BASE}/api/notes/{note_id}", headers=admin, json={"body": body + " edited"}, timeout=15)
        assert upd.status_code == 200
        assert upd.json()["body"].endswith("edited")
    finally:
        # DELETE
        deleted = requests.delete(f"{BASE}/api/notes/{note_id}", headers=admin, timeout=15)
        assert deleted.status_code == 200
    # gone
    gone = requests.put(f"{BASE}/api/notes/{note_id}", headers=admin, json={"body": "x"}, timeout=15)
    assert gone.status_code == 404


def test_notes_empty_rejected_422(admin, device_id):
    r = requests.post(f"{BASE}/api/devices/{device_id}/notes", headers=admin, json={"body": "   "}, timeout=15)
    assert r.status_code == 422


def test_notes_require_auth(device_id):
    r = requests.get(f"{BASE}/api/devices/{device_id}/notes", timeout=15)
    assert r.status_code == 401


def test_notes_are_user_scoped(admin, viewer, device_id):
    """A note created by admin must not be visible to (or editable by) the viewer."""
    body = f"admin-only {uuid.uuid4().hex[:8]}"
    note = requests.post(
        f"{BASE}/api/devices/{device_id}/notes", headers=admin, json={"body": body}, timeout=15
    ).json()
    try:
        # viewer cannot see it
        vlist = requests.get(f"{BASE}/api/devices/{device_id}/notes", headers=viewer, timeout=15).json()
        assert all(n["id"] != note["id"] for n in vlist["notes"])
        # viewer is read-only -> write is forbidden by role
        vedit = requests.put(f"{BASE}/api/notes/{note['id']}", headers=viewer, json={"body": "hax"}, timeout=15)
        assert vedit.status_code == 403
    finally:
        requests.delete(f"{BASE}/api/notes/{note['id']}", headers=admin, timeout=15)


# ---- role-based authorization ----------------------------------------------

def test_viewer_cannot_write_notes(viewer, device_id):
    r = requests.post(f"{BASE}/api/devices/{device_id}/notes", headers=viewer,
                      json={"body": "nope"}, timeout=15)
    assert r.status_code == 403


def test_user_management_is_admin_only(viewer):
    assert requests.get(f"{BASE}/api/users", headers=viewer, timeout=15).status_code == 403


def test_admin_user_crud(admin):
    assert requests.get(f"{BASE}/api/users", headers=admin, timeout=15).status_code == 200
    email = f"temp_{uuid.uuid4().hex[:8]}@bms.local"
    created = requests.post(f"{BASE}/api/users", headers=admin,
                            json={"email": email, "password": "Temp#2026", "role": "engineer"}, timeout=15)
    assert created.status_code == 200
    uid = created.json()["id"]
    try:
        upd = requests.put(f"{BASE}/api/users/{uid}", headers=admin, json={"role": "supervisor"}, timeout=15)
        assert upd.status_code == 200 and upd.json()["role"] == "supervisor"
    finally:
        assert requests.delete(f"{BASE}/api/users/{uid}", headers=admin, timeout=15).status_code == 200


def test_admin_cannot_delete_self(admin):
    users = requests.get(f"{BASE}/api/users", headers=admin, timeout=15).json()["users"]
    me = requests.get(f"{BASE}/api/auth/me", headers=admin, timeout=15).json()
    admin_id = next(u["id"] for u in users if u["email"] == me["email"])
    assert requests.delete(f"{BASE}/api/users/{admin_id}", headers=admin, timeout=15).status_code == 400
