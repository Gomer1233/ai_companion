from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from time import time
from typing import Any


SOURCE_CUTOVER_TABLES = (
    "users",
    "telegram_accounts",
    "user_profile",
    "user_settings",
    "conversations",
    "messages",
    "user_messages",
    "mode_state",
    "mode_lock",
    "mode_locks",
    "conversation_mode_state",
    "conversation_mode_lock",
    "photo_gate",
    "conversation_photo_gate",
    "events",
    "user_events",
    "relationship_state",
    "conversation_relationship_state",
    "jobs",
    "sessions",
    "plans",
    "entitlements",
    "usage_counters",
    "access_grants",
    "explicit_consent",
    "payment_orders",
    "admin_audit_events",
)

IMPORT_TABLE_ORDER = (
    "users",
    "telegram_accounts",
    "user_profile",
    "user_settings",
    "plans",
    "conversations",
    "messages",
    "user_messages",
    "mode_state",
    "mode_lock",
    "mode_locks",
    "conversation_mode_state",
    "conversation_mode_lock",
    "photo_gate",
    "conversation_photo_gate",
    "events",
    "user_events",
    "relationship_state",
    "conversation_relationship_state",
    "sessions",
    "jobs",
    "entitlements",
    "usage_counters",
    "access_grants",
    "explicit_consent",
    "payment_orders",
    "admin_audit_events",
)

IDENTITY_COLUMNS = {
    "messages": {"id"},
    "user_messages": {"id"},
    "events": {"id"},
    "user_events": {"id"},
}


@dataclass(frozen=True, slots=True)
class CutoverSnapshot:
    tables: dict[str, list[dict[str, Any]]]


@dataclass(frozen=True, slots=True)
class CutoverImportResult:
    imported_counts: dict[str, int]


def export_sqlite_snapshot(db_path: str) -> CutoverSnapshot:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        tables = {
            table_name: _select_all(conn, table_name)
            for table_name in SOURCE_CUTOVER_TABLES
            if _table_exists(conn, table_name)
        }
    finally:
        conn.close()

    user_ids = _collect_user_ids(tables)
    tables["users"] = _normalized_user_rows(tables.get("users", []), user_ids, tables)
    if not tables.get("telegram_accounts"):
        tables["telegram_accounts"] = _derived_telegram_accounts(tables["users"])
    if tables.get("mode_lock") and not tables.get("mode_locks"):
        tables["mode_locks"] = [dict(row) for row in tables["mode_lock"]]
    return CutoverSnapshot(tables=tables)


def snapshot_counts(snapshot: CutoverSnapshot) -> dict[str, int]:
    return {
        table_name: len(rows)
        for table_name, rows in sorted(snapshot.tables.items())
        if rows
    }


def import_snapshot_to_repositories(snapshot: CutoverSnapshot, repositories) -> CutoverImportResult:
    counts: dict[str, int] = {}
    conn = repositories._connect()
    try:
        for table_name in IMPORT_TABLE_ORDER:
            rows = snapshot.tables.get(table_name, [])
            if not rows or not _target_table_exists(conn, table_name):
                continue
            counts[table_name] = _insert_rows(conn, table_name, rows)
        conn.commit()
    finally:
        conn.close()
    return CutoverImportResult(imported_counts=counts)


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return bool(row)


def _select_all(conn: sqlite3.Connection, table_name: str) -> list[dict[str, Any]]:
    rows = conn.execute(f"SELECT * FROM {table_name}").fetchall()
    return [dict(row) for row in rows]


def _collect_user_ids(tables: dict[str, list[dict[str, Any]]]) -> set[int]:
    user_ids: set[int] = set()
    for rows in tables.values():
        for row in rows:
            if row.get("user_id") is not None:
                user_ids.add(int(row["user_id"]))
    return user_ids


def _normalized_user_rows(
    existing_rows: list[dict[str, Any]],
    user_ids: set[int],
    tables: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    timestamp_bounds = _user_timestamp_bounds(tables)
    rows_by_user: dict[int, dict[str, Any]] = {}
    for row in existing_rows:
        user_id = int(row["user_id"])
        created_at, updated_at = timestamp_bounds.get(user_id, _fallback_timestamp_bounds())
        rows_by_user[user_id] = {
            "user_id": user_id,
            "created_at": int(row.get("created_at") or created_at),
            "updated_at": int(row.get("updated_at") or updated_at),
        }

    for user_id in user_ids:
        if user_id in rows_by_user:
            continue
        created_at, updated_at = timestamp_bounds.get(user_id, _fallback_timestamp_bounds())
        rows_by_user[user_id] = {
            "user_id": user_id,
            "created_at": created_at,
            "updated_at": updated_at,
        }
    return [rows_by_user[user_id] for user_id in sorted(rows_by_user)]


def _derived_telegram_accounts(user_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "telegram_user_id": int(row["user_id"]),
            "user_id": int(row["user_id"]),
            "username": "",
            "first_name": "",
            "created_at": int(row["created_at"]),
            "updated_at": int(row["updated_at"]),
        }
        for row in user_rows
    ]


def _user_timestamp_bounds(tables: dict[str, list[dict[str, Any]]]) -> dict[int, tuple[int, int]]:
    bounds: dict[int, tuple[int, int]] = {}
    timestamp_columns = ("created_at", "updated_at", "ts", "issued_at", "last_seen_at", "expires_at")
    for rows in tables.values():
        for row in rows:
            if row.get("user_id") is None:
                continue
            values = [int(row[column]) for column in timestamp_columns if row.get(column) is not None]
            if not values:
                continue
            user_id = int(row["user_id"])
            current = bounds.get(user_id)
            row_min = min(values)
            row_max = max(values)
            if current is None:
                bounds[user_id] = (row_min, row_max)
            else:
                bounds[user_id] = (min(current[0], row_min), max(current[1], row_max))
    return bounds


def _fallback_timestamp_bounds() -> tuple[int, int]:
    now_ts = int(time())
    return now_ts, now_ts


def _target_table_exists(conn: Any, table_name: str) -> bool:
    if isinstance(conn, sqlite3.Connection):
        return _table_exists(conn, table_name)
    row = conn.execute(
        """
        SELECT EXISTS (
          SELECT 1
          FROM information_schema.tables
          WHERE table_schema='public' AND table_name=?
        )
        """,
        (table_name,),
    ).fetchone()
    return bool(row and row[0])


def _target_columns(conn: Any, table_name: str) -> list[str]:
    if isinstance(conn, sqlite3.Connection):
        return [row[1] for row in conn.execute(f"PRAGMA table_info({_quote_identifier(table_name)})").fetchall()]
    rows = conn.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=?
        ORDER BY ordinal_position
        """,
        (table_name,),
    ).fetchall()
    return [str(row[0]) for row in rows]


def _insert_rows(conn: Any, table_name: str, rows: list[dict[str, Any]]) -> int:
    target_columns = _target_columns(conn, table_name)
    if not target_columns:
        return 0
    source_columns = {column for row in rows for column in row}
    ignored_columns = IDENTITY_COLUMNS.get(table_name, set())
    columns = [column for column in target_columns if column in source_columns and column not in ignored_columns]
    if not columns:
        return 0

    table_sql = _quote_identifier(table_name)
    column_sql = ", ".join(_quote_identifier(column) for column in columns)
    placeholders = ", ".join("?" for _ in columns)
    sql = f"INSERT INTO {table_sql} ({column_sql}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
    for row in rows:
        conn.execute(sql, tuple(row.get(column) for column in columns))
    return len(rows)


def _quote_identifier(identifier: str) -> str:
    if not identifier.replace("_", "").isalnum():
        raise ValueError(f"Unsafe SQL identifier: {identifier}")
    return f'"{identifier}"'
