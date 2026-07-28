"""Database access — a small thread-safe connection pool over pg8000.

pg8000 is a pure-Python, BSD-3-Clause Postgres driver (no copyleft). Endpoints
are sync `def` (FastAPI runs them in a threadpool), so a simple blocking pool is
the right fit. Every query uses %s placeholders (pg8000 'format' paramstyle) —
no string interpolation — satisfying the "parameterized only" requirement.
"""
from __future__ import annotations

import os
import queue
import threading
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from urllib.parse import unquote, urlparse

import pg8000.dbapi
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set. Copy .env.example to .env and fill it in.")


def _conn_params(url: str) -> dict:
    u = urlparse(url)
    return {
        "user": unquote(u.username or ""),
        "password": unquote(u.password or ""),
        "host": u.hostname or "127.0.0.1",
        "port": u.port or 5432,
        "database": (u.path or "/").lstrip("/") or "postgres",
    }


_PARAMS = _conn_params(DATABASE_URL)


class _Pool:
    """Fixed-size blocking pool. Connections are autocommit (the API only reads),
    so a connection is always returned in a clean, reusable state."""

    def __init__(self, size: int = 5):
        self._size = size
        self._q: queue.Queue = queue.Queue(maxsize=size)
        self._lock = threading.Lock()
        self._opened = False

    def _new(self):
        conn = pg8000.dbapi.connect(**_PARAMS)
        conn.autocommit = True
        return conn

    def open(self) -> None:
        with self._lock:
            if self._opened:
                return
            for _ in range(self._size):
                self._q.put(self._new())
            self._opened = True

    @contextmanager
    def connection(self):
        conn = self._q.get()
        try:
            yield conn
        finally:
            self._q.put(conn)

    def close(self) -> None:
        with self._lock:
            if not self._opened:
                return
            while not self._q.empty():
                try:
                    self._q.get_nowait().close()
                except Exception:
                    pass
            self._opened = False


pool = _Pool(size=5)


def _floatify(row: dict | None) -> dict | None:
    """NUMERIC columns arrive as Decimal; emit JSON numbers, not strings."""
    if row is None:
        return None
    return {k: (float(v) if isinstance(v, Decimal) else v) for k, v in row.items()}


def _dictify(cur) -> list[dict]:
    cols = [d[0] for d in cur.description] if cur.description else []
    return [_floatify(dict(zip(cols, r))) for r in cur.fetchall()]


def query(sql: str, params: tuple = ()) -> list[dict]:
    with pool.connection() as conn:
        cur = conn.cursor()
        try:
            cur.execute(sql, params)
            return _dictify(cur)
        finally:
            cur.close()


def query_one(sql: str, params: tuple = ()) -> dict | None:
    with pool.connection() as conn:
        cur = conn.cursor()
        try:
            cur.execute(sql, params)
            cols = [d[0] for d in cur.description] if cur.description else []
            row = cur.fetchone()
            return _floatify(dict(zip(cols, row))) if row else None
        finally:
            cur.close()


def execute(sql: str, params: tuple = ()) -> None:
    """Run a statement that returns no rows (UPDATE/INSERT without RETURNING)."""
    with pool.connection() as conn:
        cur = conn.cursor()
        try:
            cur.execute(sql, params)
        finally:
            cur.close()
