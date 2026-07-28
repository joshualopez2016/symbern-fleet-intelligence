"""BMS telemetry simulator — a standalone producer (Simulator -> DB).

Generates plausible battery telemetry for a fleet of simulated packs and writes
it to PostgreSQL. The API only ever *reads*; this process only *writes*. Swapping
this out for a real telemetry feed would leave the schema and API untouched.

Usage:
    py simulator/simulator.py --reset --fleet-size 24     # seed fleet + run
    py simulator/simulator.py --fleet-size 2000           # bigger fleet (scale)
    py simulator/simulator.py --seed-only --fleet-size 50 # just create devices
    py simulator/simulator.py --ticks 10                  # run N ticks then stop

Model (see docs/DESIGN.md §4):
    * Each pack runs a discharge -> charge -> discharge state machine.
    * Pack voltage comes from an open-circuit-voltage (OCV) curve of SoC, then
      sags under load (V = OCV(soc) - current * internal_resistance).
    * Temperature drifts with load.
    * Alarms are CONSEQUENCES of state (low SoC drags voltage down, heavy load
      heats the pack) plus a small rate of injected faults, evaluated against the
      shared thresholds in backend/config/thresholds.py.

Uses pg8000 (pure-Python, BSD-3-Clause) with %s placeholders — parameterized,
no copyleft dependencies.
"""
from __future__ import annotations

import argparse
import os
import signal
import ssl
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import pg8000.dbapi
from dotenv import load_dotenv

# --- shared config: single source of truth for alert thresholds --------------
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from config.thresholds import evaluate  # noqa: E402

import random  # noqa: E402

load_dotenv(ROOT / ".env")
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    sys.exit("DATABASE_URL not set. Copy .env.example to .env and fill it in.")

# Accelerate simulated time so SoC visibly moves each tick during a demo:
# one real tick advances the battery model by TIME_ACCEL seconds of "battery time".
TIME_ACCEL = 120.0

# Postgres caps a statement at 65535 bind params; chunk multi-row inserts well
# under that (largest row here has 8 columns -> 1000 rows = 8000 params).
INSERT_CHUNK = 1000

SITES = ["Depot-North", "Depot-South", "Yard-A", "Yard-B", "Substation-3"]
MODELS = ["PowerCell-48", "PowerCell-51", "Industns-100"]
COMPANIES = ["Northwind Energy", "Cascade Logistics", "Harbor Marine",
             "Summit Materials", "Delta Freight"]
EQUIPMENT = ["Forklift", "AGV", "Yard Tractor", "Backup UPS",
             "Ground Power Unit", "Reach Stacker"]

_rng = random.Random()


def connect():
    u = urlparse(DATABASE_URL)
    kwargs = dict(
        user=unquote(u.username or ""),
        password=unquote(u.password or ""),
        host=u.hostname or "127.0.0.1",
        port=u.port or 5432,
        database=(u.path or "/").lstrip("/") or "postgres",
    )
    sslmode = (parse_qs(u.query).get("sslmode", [""])[0]).lower()
    if sslmode in ("require", "verify-ca", "verify-full") or os.environ.get("DB_SSL") == "1":
        kwargs["ssl_context"] = ssl.create_default_context()
    return pg8000.dbapi.connect(**kwargs)


def _insert_many(cur, prefix: str, template: str, rows: list, suffix: str = "") -> None:
    """Chunked multi-row INSERT: prefix + '(...),(...),...' + suffix."""
    for i in range(0, len(rows), INSERT_CHUNK):
        batch = rows[i:i + INSERT_CHUNK]
        placeholders = ",".join([template] * len(batch))
        args = [v for row in batch for v in row]
        cur.execute(prefix + placeholders + suffix, args)


# OCV curve: fraction of the (v_empty..v_full) span as a function of SoC.
_OCV_SOC = [0.0, 10.0, 20.0, 50.0, 80.0, 100.0]
_OCV_FRAC = [0.00, 0.45, 0.62, 0.78, 0.93, 1.00]


def _interp(x: float, xs: list[float], ys: list[float]) -> float:
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    for i in range(1, len(xs)):
        if x <= xs[i]:
            t = (x - xs[i - 1]) / (xs[i] - xs[i - 1])
            return ys[i - 1] + t * (ys[i] - ys[i - 1])
    return ys[-1]


class Battery:
    """In-memory state for one simulated pack."""

    def __init__(self, idx: int, rng: random.Random):
        self.device_id = f"BMS-{idx:04d}"
        self.label = f"Pack {idx:04d}"
        self.model = rng.choice(MODELS)
        self.site = rng.choice(SITES)
        self.company = rng.choice(COMPANIES)
        self.equipment = rng.choice(EQUIPMENT)
        self.cell_count = rng.choice([15, 16])
        self.nominal_voltage = round(self.cell_count * 3.2, 2)      # LiFePO4 ~3.2 V/cell
        self.capacity_ah = float(rng.choice([100, 150, 200, 280]))
        self.v_full = round(self.nominal_voltage * 1.125, 2)
        self.v_empty = round(self.nominal_voltage * 0.78, 2)
        self.internal_resistance = rng.uniform(0.010, 0.030)        # ohms (per-pack personality)
        self.ambient_c = rng.uniform(20.0, 28.0)

        # Dynamic state
        self.soc = rng.uniform(40.0, 95.0)
        self.mode = "discharge"
        self.temperature_c = self.ambient_c + rng.uniform(0.0, 3.0)
        self.low_switch = rng.uniform(8.0, 22.0)
        self.high_switch = rng.uniform(93.0, 100.0)
        self.base_load_c = rng.uniform(0.15, 0.55)                  # C-rate while discharging
        self.faulty = rng.random() < 0.12

    def ocv(self, soc: float) -> float:
        frac = _interp(soc, _OCV_SOC, _OCV_FRAC)
        return self.v_empty + frac * (self.v_full - self.v_empty)

    def step(self, dt_seconds: float, rng: random.Random) -> dict:
        dt_h = dt_seconds / 3600.0

        if self.mode == "discharge":
            load_c = self.base_load_c * rng.uniform(0.7, 1.3)
            if self.faulty:
                load_c *= 1.6
            current = load_c * self.capacity_ah                     # +A discharge
            self.soc -= current * dt_h / self.capacity_ah * 100.0
            if self.soc <= self.low_switch:
                self.mode = "charge"
        else:  # charge
            charge_c = 0.35 * rng.uniform(0.8, 1.2)
            current = -charge_c * self.capacity_ah                  # -A charge
            self.soc += -current * dt_h / self.capacity_ah * 100.0
            if self.soc >= self.high_switch:
                self.mode = "discharge"

        self.soc = max(0.0, min(100.0, self.soc))

        voltage = self.ocv(self.soc) - current * self.internal_resistance
        voltage += rng.uniform(-0.05, 0.05)                         # sensor noise

        target = self.ambient_c + abs(current) / self.capacity_ah * 22.0
        if self.faulty:
            target += 12.0
        self.temperature_c += (target - self.temperature_c) * 0.15
        self.temperature_c += rng.uniform(-0.2, 0.2)
        if rng.random() < 0.002:
            self.temperature_c += rng.uniform(6.0, 14.0)

        return {
            "soc": round(self.soc, 2),
            "pack_voltage": round(voltage, 2),
            "current_a": round(current, 2),
            "temperature_c": round(self.temperature_c, 2),
        }


def seed_devices(conn, fleet: list[Battery]) -> None:
    cur = conn.cursor()
    try:
        rows = [(b.device_id, b.label, b.model, b.site, b.company, b.equipment,
                 b.cell_count, b.nominal_voltage, b.capacity_ah) for b in fleet]
        _insert_many(
            cur,
            "INSERT INTO devices (device_id, label, model, site, company, equipment, "
            "cell_count, nominal_voltage, capacity_ah) VALUES ",
            "(%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            rows,
            " ON CONFLICT (device_id) DO NOTHING",
        )
    finally:
        cur.close()
    conn.commit()


def load_state(conn, fleet: list[Battery]) -> int:
    """Resume each pack's dynamic state from device_status so a simulator
    restart is continuous (no SoC discontinuity). Returns how many were resumed."""
    by_id = {b.device_id: b for b in fleet}
    resumed = 0
    cur = conn.cursor()
    try:
        cur.execute("SELECT device_id, soc, temperature_c, current_a FROM device_status")
        for device_id, soc, temperature_c, current_a in cur.fetchall():
            b = by_id.get(device_id)
            if b is None:
                continue
            b.soc = float(soc)
            b.temperature_c = float(temperature_c)
            b.mode = "charge" if float(current_a) < 0 else "discharge"
            resumed += 1
    finally:
        cur.close()
    return resumed


def load_open_alarms(conn) -> dict[str, set[str]]:
    """device_id -> set of currently-open alarm codes (survives restarts)."""
    open_map: dict[str, set[str]] = {}
    cur = conn.cursor()
    try:
        cur.execute("SELECT device_id, code FROM alarms WHERE cleared_at IS NULL")
        for device_id, code in cur.fetchall():
            open_map.setdefault(device_id, set()).add(code)
    finally:
        cur.close()
    return open_map


def write_tick(conn, fleet: list[Battery], open_alarms: dict[str, set[str]],
               ts: datetime, rng: random.Random) -> tuple[int, int]:
    readings_rows = []
    status_rows = []
    new_alarm_rows = []
    cleared: list[tuple] = []

    for b in fleet:
        r = b.step(TIME_ACCEL, rng)
        readings_rows.append((b.device_id, ts, r["soc"], r["pack_voltage"],
                              r["current_a"], r["temperature_c"]))

        verdict = evaluate(r["soc"], r["pack_voltage"], r["temperature_c"],
                           b.nominal_voltage)
        tripped = {a["code"]: a for a in verdict["alarms"]}
        prev = open_alarms.setdefault(b.device_id, set())

        for code, a in tripped.items():
            if code not in prev:
                new_alarm_rows.append((b.device_id, ts, code, a["severity"], a["value"]))
                prev.add(code)
        for code in list(prev):
            if code not in tripped:
                cleared.append((ts, b.device_id, code))
                prev.discard(code)

        status_rows.append((b.device_id, ts, r["soc"], r["pack_voltage"],
                            r["current_a"], r["temperature_c"],
                            verdict["status"], len(prev)))

    cur = conn.cursor()
    try:
        _insert_many(
            cur,
            "INSERT INTO readings (device_id, ts, soc, pack_voltage, current_a, "
            "temperature_c) VALUES ",
            "(%s, %s, %s, %s, %s, %s)",
            readings_rows,
        )
        _insert_many(
            cur,
            "INSERT INTO device_status (device_id, ts, soc, pack_voltage, current_a, "
            "temperature_c, status, active_alarms) VALUES ",
            "(%s, %s, %s, %s, %s, %s, %s, %s)",
            status_rows,
            " ON CONFLICT (device_id) DO UPDATE SET "
            "ts = EXCLUDED.ts, soc = EXCLUDED.soc, pack_voltage = EXCLUDED.pack_voltage, "
            "current_a = EXCLUDED.current_a, temperature_c = EXCLUDED.temperature_c, "
            "status = EXCLUDED.status, active_alarms = EXCLUDED.active_alarms",
        )
        if new_alarm_rows:
            _insert_many(
                cur,
                "INSERT INTO alarms (device_id, ts, code, severity, value) VALUES ",
                "(%s, %s, %s, %s, %s)",
                new_alarm_rows,
            )
        if cleared:
            cur.executemany(
                "UPDATE alarms SET cleared_at = %s "
                "WHERE device_id = %s AND code = %s AND cleared_at IS NULL",
                cleared,
            )
    finally:
        cur.close()
    conn.commit()
    return len(new_alarm_rows), len(cleared)


def main() -> None:
    ap = argparse.ArgumentParser(description="BMS telemetry simulator")
    ap.add_argument("--fleet-size", type=int, default=24)
    ap.add_argument("--interval", type=float, default=2.0, help="seconds between ticks")
    ap.add_argument("--ticks", type=int, default=0, help="stop after N ticks (0 = run forever)")
    ap.add_argument("--seed", type=int, default=42, help="RNG seed for a reproducible fleet")
    ap.add_argument("--reset", action="store_true",
                    help="TRUNCATE all data before seeding (dev only)")
    ap.add_argument("--seed-only", action="store_true", help="create devices then exit")
    args = ap.parse_args()

    _rng.seed(args.seed)
    fleet = [Battery(i + 1, _rng) for i in range(args.fleet_size)]

    conn = connect()
    try:
        if args.reset:
            cur = conn.cursor()
            try:
                cur.execute("TRUNCATE readings, alarms, device_status, devices "
                            "RESTART IDENTITY CASCADE")
            finally:
                cur.close()
            conn.commit()
            print("Reset: all tables truncated.")

        seed_devices(conn, fleet)
        print(f"Seeded {len(fleet)} devices.")
        if args.seed_only:
            return

        if not args.reset:
            resumed = load_state(conn, fleet)
            if resumed:
                print(f"Resumed state for {resumed} devices from device_status.")
        open_alarms = load_open_alarms(conn)

        stop = {"flag": False}
        signal.signal(signal.SIGINT, lambda *_: stop.__setitem__("flag", True))

        print(f"Streaming telemetry: {len(fleet)} devices, {args.interval}s tick, "
              f"{TIME_ACCEL:.0f}x time. Ctrl+C to stop.")
        tick = 0
        while not stop["flag"]:
            ts = datetime.now(timezone.utc)
            t0 = time.perf_counter()
            n_new, n_clear = write_tick(conn, fleet, open_alarms, ts, _rng)
            dt_ms = (time.perf_counter() - t0) * 1000.0
            tick += 1
            active = sum(len(s) for s in open_alarms.values())
            print(f"tick {tick:>5} | {len(fleet)} readings in {dt_ms:6.1f} ms "
                  f"| +{n_new} alarms -{n_clear} cleared | {active} active")
            if args.ticks and tick >= args.ticks:
                break
            time.sleep(max(0.0, args.interval - (time.perf_counter() - t0)))
    finally:
        conn.close()

    print("Simulator stopped.")


if __name__ == "__main__":
    main()
