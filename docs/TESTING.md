# Testing

The API is tested two ways, both against a live server:

1. **Postman / Thunder Client collection** — `tests/bms_api.postman_collection.json`
   (22 requests, 39 assertions). Import and run with the Collection Runner.
2. **pytest integration suite** — `tests/test_api.py` (19 tests). Runnable in CI.

Both currently pass **green**. Endpoint request/response formats are documented in
[API_ENDPOINTS.md](API_ENDPOINTS.md).

## Prerequisites
Start the stack first (see the README): PostgreSQL running, the simulator seeded,
and the API on `http://127.0.0.1:8000`. Seed users must exist:
`admin@bms.local / Admin#2026` and `viewer@bms.local / Viewer#2026`.

## Run the Postman / Thunder Client collection
- **Postman:** File → Import → `tests/bms_api.postman_collection.json`, then open
  the collection and click **Run** (Collection Runner). The `Login (admin)` request
  stores the JWT in the `{{token}}` variable; every later request reuses it.
- **Thunder Client (VS Code):** Collections → Import → select the same file → Run All.
- **Headless (CI):** `newman run tests/bms_api.postman_collection.json`

`{{baseUrl}}` defaults to `http://127.0.0.1:8000` — change the collection variable
to point at another host. The AI-search request skips itself gracefully if the
server has no `TRUSSED_API_KEY`.

## Run the pytest suite
```bash
py -m pip install -r tests/requirements.txt
py -m pytest tests/ -v            # from the project root, API running
# target another host:  BMS_API=http://host:8000 py -m pytest tests/
```

## Test-case matrix

### Authentication
| # | Method / route | Scenario | Expected |
|---|---|---|---|
| A1 | POST /api/auth/login | valid admin credentials | 200 + JWT + role=administrator |
| A2 | POST /api/auth/login | wrong password | 401 |
| A3 | GET /api/auth/me | valid token | 200 + email/role |
| A4 | GET /api/fleet/summary | **no** token | 401 |
| A5 | GET /api/fleet/summary | garbage token | 401 |

### Fleet / devices / readings / alarms
| # | Method / route | Scenario | Expected |
|---|---|---|---|
| F1 | GET /api/fleet/summary | authed | 200; ok+warning+critical = total |
| F2 | GET /api/fleet?limit=5 | authed | 200; ≤5 devices; worst-first |
| F3 | GET /api/fleet?status=warning | filter | 200; every row status=warning |
| F4 | GET /api/fleet?status=bogus | invalid enum | 422 |
| D1 | GET /api/devices/{id} | known device | 200; ids match |
| D2 | GET /api/devices/NOPE-9999 | unknown device | 404 |
| D3 | GET /api/devices/{id}/readings?since= | delta fetch | 200; every row ts > cursor |
| L1 | GET /api/alarms?active=true | active only | 200; every alarm active=true |
| C1 | GET /api/config/thresholds | authed | 200; soc/voltage/temp limits present |

### AI
| # | Method / route | Scenario | Expected |
|---|---|---|---|
| I1 | GET /api/ai/status | authed | 200; `configured` boolean |
| I2 | POST /api/ai/search | **no** token | 401 |
| I3 | POST /api/ai/search | authed, key set | 200; explanation + devices[] (503 if no key) |

### Notes — CRUD & ownership
| # | Method / route | Scenario | Expected |
|---|---|---|---|
| N1 | POST /api/devices/{id}/notes | create | 200; echoes body |
| N2 | GET /api/devices/{id}/notes | list | 200; contains the new note |
| N3 | PUT /api/notes/{id} | update own | 200; body updated |
| N4 | DELETE /api/notes/{id} | delete own | 200; returns deleted id |
| N5 | PUT /api/notes/{id} | update after delete | 404 |
| N6 | POST /api/devices/{id}/notes | empty/whitespace body | 422 |
| N7 | GET /api/devices/{id}/notes | **no** token | 401 |
| N8 | note created by admin, read/edited by viewer | ownership scoping | not listed for viewer; PUT → 404 |

## Coverage summary
- **Auth:** login (valid/invalid), token validation, protected-route enforcement.
- **CRUD:** notes create / read / update / delete, plus not-found-after-delete.
- **Edge & error cases:** 401 (unauthenticated / bad token), 422 (invalid enum /
  empty note), 404 (unknown device / note), and per-user data isolation.
