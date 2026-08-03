# Project Plan — Symbern Fleet Intelligence (BMS Cloud Dashboard)

**Author:** Joshua Lopez · Z23384309 · Joshualopez2016@fau.edu
**Course:** FAU AI HootCamp (Summer 2026) — Build Plan & Design Assignment

---

## 1. Project goals

A full-stack **fleet-battery intelligence platform** for **Symbern** ("Batteries.
Equipment. Intelligence."). It follows a battery pack across its whole lifecycle
behind one application, in two data domains:

- **Fleet Intelligence** — real-time monitoring of *deployed* battery packs (state
  of charge, voltage, current, temperature, alarms) so a fleet manager can see
  health at a glance and drill into trends.
- **Production Test Records** — *manufacturing / QA* history: pass/fail at test
  stations and fixtures, by operator, fully traceable by serial number.

**Primary goal:** prove a clean, honest data pipeline (Simulator → Database → API →
UI) with realistic simulated data, built so that swapping the simulator for a real
telemetry / test feed later requires minimal rewrites.

All data is **simulated** (cloud-safe); no real hardware or customer data is used.

## 2. Requirements

### Functional (core)
- Realistic data **simulation** of telemetry (device id, timestamp, SoC, pack
  voltage, current, temperature, and alarm/fault conditions with severity).
- **Fleet grid + drill-down** — a status grid of all packs; click one for history.
- **Live charts & alerts** — real-time-feeling SoC/voltage charts; threshold
  crossings surface visibly in the UI.
- **Configurable thresholds** in a single config file (not hardcoded in the UI).
- **Production test records** — pass/fail lookup, daily production summary
  (totals, pass/fail %, most-failed product/fixture/station), serial history,
  universal cross-entity search.

### Functional (extended — added during Build Phase)
- **Authentication** (login required) with **role-based authorization**
  (viewer / engineer / supervisor / administrator) and user management.
- **AI features** (3): natural-language fleet search, an AI fleet-health briefing,
  and an in-app **assistant chatbot** that can open IT/Management support tickets.
- **Reporting & export** — CSV / Excel / browser-print (Save-as-PDF).
- **No-code query builder** over multiple data sources (safe, parameterized).
- **Real-time updates via WebSockets** with a polling fallback.
- **Notes CRUD** (per-user annotations on a pack).

### Non-functional
- **Security:** no secrets in git, all queries parameterized (no SQL injection),
  XSS-safe (React escaping, JSON-only API), least-privilege read-only DB role,
  clean `pip-audit` / `npm audit`, no copyleft dependencies.
- **Efficiency / scale:** bounded, worst-first pages so payload/query cost stay
  flat as the fleet grows (validated at ~2,000 packs / 50k readings; index-only
  queries).
- **Clean architecture:** clear separation of concerns (simulator / backend /
  frontend / sql / tests / docs).
- **Deployability:** runs as a single service; deployed free to the cloud.

## 3. Milestones

| # | Milestone | Deliverable |
|---|---|---|
| M1 | Data pipeline | Schema + telemetry simulator writing to Postgres |
| M2 | Read API | FastAPI endpoints (fleet, device, readings `?since=`, alarms) |
| M3 | Fleet UI | React grid, live polling, worst-first color-coded cards |
| M4 | Drill-down + charts | SoC/voltage trend charts with threshold lines |
| M5 | Alerts | Active-alerts panel + configurable thresholds |
| M6 | Scale & efficiency | Bounded pagination, summary endpoint, measured results |
| M7 | Security self-cert | Parameterized, no-copyleft, `pip-audit`/`npm audit` clean |
| M8 | Auth + RBAC | JWT login, enforced roles, user management |
| M9 | AI features | NL search, briefing, assistant chatbot + tickets |
| M10 | Reporting/export | CSV/Excel/PDF, daily report, no-code query builder |
| M11 | Realtime | WebSocket live feed + fallback |
| M12 | Production domain | Test-records schema, API, and UI (Fleet ↔ Production) |
| M13 | Testing | pytest suite (40) + Postman/Thunder collection |
| M14 | Cloud deploy | Single-service Docker deploy (Render + Neon), live URL |

## 4. Implementation plan

**Tech stack**
- **Frontend:** React (Vite), Recharts, WebSocket client
- **Backend:** FastAPI (Python), Uvicorn, pg8000 (BSD-3 — permissive Postgres driver)
- **Database:** PostgreSQL (local for dev; Neon managed Postgres in production)
- **Simulators:** standalone Python generators (telemetry + production QA)
- **AI:** FAU Trussed.ai (OpenAI-compatible LLM, `gpt-5.4`), server-side key
- **Deploy:** Docker (multi-stage) → Render web service; single service serves the
  API, the WebSocket, and the built UI, and runs the simulator in-process

**Approach**
1. Build the honest pipeline first (simulator → DB) and verify rows land.
2. Layer a read-only, parameterized API; keep the simulator the only writer.
3. Build the UI against the API; add live charts, alerts, filters.
4. Add platform capabilities (auth/RBAC, AI, reporting, query builder, realtime).
5. Add the second data domain (production) reusing the same patterns.
6. Test (automated + Postman), self-certify security, deploy to the cloud.

## 5. Advanced topics from the Build Phase (identified)

This project deliberately incorporates several advanced topics covered in the
Build Phase — each is called out again in `design.md`:

- **Authentication & authorization** — JWT sessions, bcrypt password hashing,
  enforced role-based access control (RBAC).
- **Real-time systems** — WebSocket push with a shared server-side broadcaster
  (one DB read fanned to all clients) and a graceful polling fallback.
- **AI / LLM integration** — natural-language → structured query, grounded
  summaries, and a conversational assistant; robust error handling + rate limiting.
- **Database security & design** — parameterized queries, a least-privilege
  read-only role, indexing, a denormalized "current state" cache, and a SQL view.
- **Dynamic / no-code query building** — a whitelist-driven, injection-safe
  structured-query → parameterized-SQL engine (field-mapping + data-source selector).
- **API design & documentation** — RESTful endpoints, documented request/response
  formats, health checks.
- **Testing** — automated integration tests (pytest) + a Postman/Thunder collection.
- **DevOps / cloud deployment** — Docker multi-stage build, single-service
  architecture, managed Postgres, environment-based configuration, TLS.
- **Data visualization** — live time-series charts with threshold reference lines.
- **Scalability & efficiency** — bounded pagination, aggregate summary endpoints,
  incremental (`?since=`) fetching, measured under load.
