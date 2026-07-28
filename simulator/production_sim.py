"""Production test-records simulator (Simulator -> DB).

Generates plausible manufacturing/QA test records for Symbern battery/equipment
production: units (serials) flow through test stations & fixtures; operators run
parameterized tests; most pass, some fail — with a few fixtures/stations/products
failing more often so "most-failed" analytics are meaningful.

Simulated data only (cloud-safe). The schema is real-feed-shaped.

Usage:
    py simulator/production_sim.py --reset --units 600 --days 14
"""
from __future__ import annotations

import argparse
import os
import random
import ssl
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import pg8000.dbapi
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    sys.exit("DATABASE_URL not set. Copy .env.example to .env and fill it in.")

INSERT_CHUNK = 1000

# product -> list of (part_number, rated_capacity_ah)
PRODUCTS = {
    "PowerCell-48": [("PC48-100AH", 100), ("PC48-150AH", 150)],
    "PowerCell-51": [("PC51-100AH", 100), ("PC51-200AH", 200)],
    "Industns-100": [("IND100-280AH", 280)],
}
STATIONS = ["Station-1", "Station-2", "Station-3", "Station-4", "Station-5", "Station-6"]
FIXTURES = ["FIX-A", "FIX-B", "FIX-C", "FIX-D"]
OPERATORS = ["OP-Alvarez", "OP-Chen", "OP-Delgado", "OP-Ferraro",
             "OP-Novak", "OP-Osei", "OP-Reyes", "OP-Whitfield"]

# Bias factors so "most-failed" has signal (FIX-C, Station-4, Industns-100 fail more).
FIXTURE_FAIL = {"FIX-A": 1.0, "FIX-B": 1.1, "FIX-C": 2.6, "FIX-D": 0.9}
STATION_FAIL = {s: (1.9 if s == "Station-4" else 1.0) for s in STATIONS}
PRODUCT_FAIL = {"PowerCell-48": 1.0, "PowerCell-51": 1.1, "Industns-100": 1.7}
BASE_FAIL = 0.035

_rng = random.Random()


def connect():
    u = urlparse(DATABASE_URL)
    kwargs = dict(
        user=unquote(u.username or ""), password=unquote(u.password or ""),
        host=u.hostname or "127.0.0.1", port=u.port or 5432,
        database=(u.path or "/").lstrip("/") or "postgres",
    )
    sslmode = (parse_qs(u.query).get("sslmode", [""])[0]).lower()
    if sslmode in ("require", "verify-ca", "verify-full") or os.environ.get("DB_SSL") == "1":
        kwargs["ssl_context"] = ssl.create_default_context()
    return pg8000.dbapi.connect(**kwargs)


def _insert_many(cur, prefix, template, rows):
    for i in range(0, len(rows), INSERT_CHUNK):
        batch = rows[i:i + INSERT_CHUNK]
        placeholders = ",".join([template] * len(batch))
        args = [v for row in batch for v in row]
        cur.execute(prefix + placeholders, args)


def _measure(param, rated, rng, fail):
    """Return (measured, low, high) for a test parameter; push out of spec on fail."""
    if param == "Pack Voltage":
        low, high, nom, sd = 50.0, 52.5, 51.2, 0.35
    elif param == "Capacity (Ah)":
        low, high, nom, sd = rated * 0.95, rated * 1.08, rated * 1.01, rated * 0.02
    elif param == "Cell Balance (mV)":
        low, high, nom, sd = 0.0, 40.0, 18.0, 8.0
    elif param == "Insulation (MOhm)":
        low, high, nom, sd = 10.0, 999.0, 120.0, 60.0
    else:  # Charge Cycle (%)
        low, high, nom, sd = 92.0, 100.0, 97.0, 1.5

    if fail:
        # push just outside a limit
        if rng.random() < 0.5:
            val = low - abs(rng.gauss(0, sd)) - 0.1
        else:
            val = high + abs(rng.gauss(0, sd)) + 0.1
    else:
        val = min(high - 0.05, max(low + 0.05, rng.gauss(nom, sd)))
    return round(val, 3), round(low, 3), round(high, 3)


TESTS = ["Pack Voltage", "Capacity (Ah)", "Cell Balance (mV)", "Insulation (MOhm)", "Charge Cycle (%)"]


def generate(units: int, days: int) -> list[tuple]:
    now = datetime.now(timezone.utc)
    rows = []
    for i in range(units):
        product = _rng.choice(list(PRODUCTS.keys()))
        part_number, rated = _rng.choice(PRODUCTS[product])
        serial = f"SYM-2026-{i + 1:06d}"
        # one build/test session per unit, at a random time in the window
        base = now - timedelta(days=_rng.uniform(0, days),
                               hours=_rng.uniform(0, 8))
        station = _rng.choice(STATIONS)
        fixture = _rng.choice(FIXTURES)
        operator = _rng.choice(OPERATORS)
        for k, param in enumerate(TESTS):
            ts = base + timedelta(minutes=k * _rng.uniform(1.5, 4.0))
            fail_prob = (BASE_FAIL * FIXTURE_FAIL[fixture]
                         * STATION_FAIL[station] * PRODUCT_FAIL[product])
            is_fail = _rng.random() < fail_prob
            measured, low, high = _measure(param, rated, _rng, is_fail)
            rows.append((
                ts, product, part_number, serial, station, fixture, operator,
                param, "Fail" if is_fail else "Pass", measured, low, high,
                f"{param} out of tolerance" if is_fail else None,
            ))
    return rows


def main():
    ap = argparse.ArgumentParser(description="Production test-records simulator")
    ap.add_argument("--units", type=int, default=600)
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--reset", action="store_true", help="TRUNCATE test_records first")
    args = ap.parse_args()

    _rng.seed(args.seed)
    rows = generate(args.units, args.days)

    conn = connect()
    try:
        cur = conn.cursor()
        try:
            if args.reset:
                cur.execute("TRUNCATE test_records RESTART IDENTITY")
            _insert_many(
                cur,
                "INSERT INTO test_records (ts, product, part_number, serial_number, "
                "station, fixture, operator, test_parameter, result, measured_value, "
                "limit_low, limit_high, failure_reason) VALUES ",
                "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                rows,
            )
        finally:
            cur.close()
        conn.commit()
    finally:
        conn.close()

    fails = sum(1 for r in rows if r[8] == "Fail")
    print(f"Inserted {len(rows)} test records for {args.units} units over {args.days} days "
          f"({fails} fails, {100 * (1 - fails / len(rows)):.1f}% pass rate).")


if __name__ == "__main__":
    main()
