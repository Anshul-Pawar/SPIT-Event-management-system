"""Tiny helpers for reading the MySQL views with parameterized SQL (never string-format user input)."""
import json

from django.db import connection

JSON_COLUMNS = ("old_data", "new_data")


def _clean(row: dict) -> dict:
    for key in JSON_COLUMNS:
        value = row.get(key)
        if isinstance(value, (str, bytes)):
            try:
                row[key] = json.loads(value)
            except ValueError:
                pass
    return row


def fetch_all(sql: str, params=None) -> list[dict]:
    with connection.cursor() as cur:
        cur.execute(sql, params or [])
        cols = [c[0] for c in cur.description]
        return [_clean(dict(zip(cols, row))) for row in cur.fetchall()]


def fetch_one(sql: str, params=None) -> dict | None:
    rows = fetch_all(sql, params)
    return rows[0] if rows else None
