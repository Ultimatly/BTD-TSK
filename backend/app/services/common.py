from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any


def now_text() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def fetch_all(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def fetch_one(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> dict[str, Any] | None:
    row = conn.execute(sql, params).fetchone()
    return None if row is None else dict(row)

