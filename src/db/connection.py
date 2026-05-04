from __future__ import annotations

import sqlite3
from typing import Any


def connect_sqlite(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


class PostgresConnectionAdapter:
    def __init__(self, raw_connection: Any):
        self._raw_connection = raw_connection

    def __enter__(self):
        self._raw_connection.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._raw_connection.__exit__(exc_type, exc, tb)

    def execute(self, sql: str, params: tuple[Any, ...] | None = None):
        translated_sql = _translate_sqlite_placeholders(sql)
        if params is None:
            return self._raw_connection.execute(translated_sql)
        return self._raw_connection.execute(translated_sql, params)

    def cursor(self):
        return PostgresCursorAdapter(self._raw_connection.cursor())

    def commit(self) -> None:
        self._raw_connection.commit()

    def close(self) -> None:
        self._raw_connection.close()


def connect_postgres(database_url: str) -> PostgresConnectionAdapter:
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("Postgres backend requires the psycopg package") from exc

    return PostgresConnectionAdapter(psycopg.connect(database_url))


def _translate_sqlite_placeholders(sql: str) -> str:
    return sql.replace("?", "%s")


class PostgresCursorAdapter:
    def __init__(self, raw_cursor: Any):
        self._raw_cursor = raw_cursor

    def execute(self, sql: str, params: tuple[Any, ...] | None = None):
        translated_sql = _translate_sqlite_placeholders(sql)
        if params is None:
            return self._raw_cursor.execute(translated_sql)
        return self._raw_cursor.execute(translated_sql, params)

    def fetchone(self):
        return self._raw_cursor.fetchone()

    def fetchall(self):
        return self._raw_cursor.fetchall()
