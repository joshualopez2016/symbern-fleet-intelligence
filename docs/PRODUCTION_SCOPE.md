# Scope — Production Test Records domain

A planning doc for the second data domain: **manufacturing / QA test records**,
alongside the existing **Fleet Intelligence** (deployed-battery telemetry).

## 1. Concept — one platform, two lifecycle stages
- **Fleet Intelligence** (built): monitors **deployed** battery packs in the field
  — SoC, voltage, temperature, alarms.
- **Production Test Records** (this scope): tracks packs/equipment during
  **manufacturing test** — pass/fail at test stations & fixtures, by operator,
  traceable by serial and part number.

Together they cover a unit's whole lifecycle — *built & tested → deployed &
monitored* — which fits Symbern's **"Batteries. Equipment. Intelligence."** The
"data source selector" already in the query builder is the seam that lets one
app hold both domains.

## 2. Data model
`test_records` — one row per test execution:

| Column | Type | Notes |
|---|---|---|
| id | bigint PK | |
| ts | timestamptz | test time |
| product | text | model/family (e.g. PowerCell-51) |
| part_number | text | SKU |
| serial_number | text | unit serial (traceability) |
| station | text | test station |
| fixture | text | test fixture |
| operator | text | operator id/name |
| test_parameter | text | e.g. Pack Voltage, Capacity, Cell Balance, Insulation |
| result | text | `Pass` \| `Fail` |
| measured_value | numeric | the measurement |
| limit_low / limit_high | numeric | spec limits |
| failure_reason | text | null on pass |

Indexes: `serial_number`, `ts DESC`, `(product)`, `(result)`, `(station)`,
`(fixture)`. This shape is realistic enough that swapping the simulator for a real
MES/test-bench feed later is a drop-in — same principle as the telemetry side.

## 3. Features (mapped from your list)
1. **Pass/Fail Lookup** — filter by product, part number, serial, date range,
   station, fixture, test parameter, result.
2. **Daily Production Summary** — Total Tested, Passed, Failed, Pass %, Fail %,
   Most-Failed Product, Most-Failed Fixture, Most-Failed Station.
3. **Serial Number History** — full chronological test history for a serial
   (every test, station, result).
4. **Universal Search** — one bar across serial / part number / product /
   station / fixture / operator.
5. **Advanced filters + Reporting/Export** — reuse the patterns already built.
6. **Query builder** — add `production` as a fifth data source.

## 4. API (auth'd; role model applies — viewers read-only)
- `GET /api/production/records` ?product=&part_number=&serial=&from=&to=&station=&fixture=&test_parameter=&result=&limit=&offset=
- `GET /api/production/summary` ?date=  → totals, pass/fail %, most-failed product/fixture/station
- `GET /api/production/serial/{serial}` → full history for one unit
- `GET /api/production/search` ?q=  → cross-entity matches
- `GET /api/export/production.{csv,xlsx}`
- Query builder: `production` source

## 5. Simulator
A production-test generator (parallel to the telemetry simulator): units (serials)
flow through stations/fixtures; operators run parameterized tests; realistic pass
rates (~93–97 %) with a few products/fixtures/stations failing more often (so
"most-failed" is meaningful); failure reasons tied to the parameter that tripped.

## 6. UI
- A top-level **mode switch: Fleet ↔ Production**.
- Production view: summary tiles (Total / Pass / Fail / Pass %), most-failed
  callouts, a filterable pass/fail records table, the universal search bar, and a
  serial drill-down showing full history. Export + query-builder integration.

## 7. ⚠️ Data-sensitivity decision (the important one)
These features mirror **ACR's real manufacturing test data** (Project 1:
Hand_Held / FLY / Boat, real stations/fixtures/serials). Per the standing rule
(*no classified company data to the cloud*):

- **Recommended for the Symbern pitch — SIMULATED, Symbern-branded production
  data** (battery/equipment QA). Fully demoable, cloud-safe, exposes no real ACR
  data. Same code could later ingest a real feed.
- **Real ACR data — on-prem only**, never in the cloud/public deploy: same code,
  a different data source + separate `.env`, not committed.
- This is exactly the two-track split already in play (demo data public, real data
  local).

## 8. Phasing
- **P1** — schema + production simulator (verify records land)
- **P2** — API (records / summary / serial / search) + query-builder source
- **P3** — UI (mode switch + production views)
- **P4** — export + tests + docs
