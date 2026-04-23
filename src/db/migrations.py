from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass

from src.db.connection import connect_sqlite


SCHEMA_VERSION = 3


@dataclass(frozen=True, slots=True)
class MigrationContext:
    include_relationship_state: bool = False


def migrate_database(db_path: str, *, include_relationship_state: bool = False) -> None:
    context = MigrationContext(include_relationship_state=include_relationship_state)
    conn = connect_sqlite(db_path)
    try:
        _ensure_schema_version_table(conn)
        current_version = _get_schema_version(conn)

        if current_version < 1:
            _migration_001_legacy_schema(conn, context)
            _set_schema_version(conn, 1)
            current_version = 1

        if current_version < 2:
            _migration_002_conversations_backfill(conn, context)
            _set_schema_version(conn, 2)
            current_version = 2

        if current_version < 3:
            _migration_003_repository_state(conn, context)
            _set_schema_version(conn, 3)

        if context.include_relationship_state:
            _ensure_relationship_state_at_schema_head(conn)

        conn.commit()
    finally:
        conn.close()


def _ensure_schema_version_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
          id INTEGER PRIMARY KEY CHECK (id = 1),
          version INTEGER NOT NULL,
          updated_at INTEGER NOT NULL
        )
        """
    )


def _get_schema_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()
    if not row:
        return 0
    return int(row[0])


def _set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(
        """
        INSERT INTO schema_version(id, version, updated_at)
        VALUES (1, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
          version = excluded.version,
          updated_at = excluded.updated_at
        """,
        (version, int(time.time())),
    )


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row[1] for row in rows}


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    return bool(row)


def _add_column_if_missing(conn: sqlite3.Connection, table_name: str, column_name: str, ddl: str) -> None:
    if column_name not in _table_columns(conn, table_name):
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}")


def _ensure_relationship_state_at_schema_head(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS relationship_state (
          user_id INTEGER NOT NULL,
          mode TEXT NOT NULL,
          state_json TEXT NOT NULL,
          updated_at INTEGER NOT NULL,
          conversation_ref TEXT,
          PRIMARY KEY (user_id, mode)
        )
        """
    )
    _add_column_if_missing(conn, "relationship_state", "conversation_ref", "TEXT")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_relationship_state_conversation_ref ON relationship_state(conversation_ref)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS conversation_relationship_state (
          user_id INTEGER NOT NULL,
          conversation_ref TEXT NOT NULL,
          mode TEXT NOT NULL,
          state_json TEXT NOT NULL,
          updated_at INTEGER NOT NULL,
          PRIMARY KEY (user_id, conversation_ref, mode)
        )
        """
    )
    conn.execute(
        """
        INSERT INTO conversation_relationship_state(user_id, conversation_ref, mode, state_json, updated_at)
        SELECT
          user_id,
          COALESCE(conversation_ref, 'legacy-user-' || user_id || '-default'),
          mode,
          state_json,
          updated_at
        FROM relationship_state
        WHERE 1 = 1
        ON CONFLICT(user_id, conversation_ref, mode) DO UPDATE SET
          state_json = excluded.state_json,
          updated_at = excluded.updated_at
        """
    )


def _migration_001_legacy_schema(conn: sqlite3.Connection, context: MigrationContext) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_profile (
          user_id INTEGER PRIMARY KEY,
          preferred_name TEXT,
          preferred_title TEXT
        )
        """
    )
    _add_column_if_missing(conn, "user_profile", "mode", "TEXT")
    _add_column_if_missing(conn, "user_profile", "chat_locked", "INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing(conn, "user_profile", "lock_reason", "TEXT NOT NULL DEFAULT ''")
    _add_column_if_missing(conn, "user_profile", "mode_picked", "INTEGER NOT NULL DEFAULT 0")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mode_state (
          user_id INTEGER NOT NULL,
          mode TEXT NOT NULL,
          state_json TEXT NOT NULL,
          updated_at INTEGER NOT NULL,
          PRIMARY KEY (user_id, mode)
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS photo_gate (
          user_id INTEGER PRIMARY KEY,
          score INTEGER NOT NULL DEFAULT 0,
          attempts INTEGER NOT NULL DEFAULT 0,
          last_ask_ts INTEGER NOT NULL DEFAULT 0,
          cooldown_until_ts INTEGER NOT NULL DEFAULT 0,
          awaiting_context INTEGER NOT NULL DEFAULT 0,
          context_asked_ts INTEGER NOT NULL DEFAULT 0,
          awaiting_image_prompt INTEGER NOT NULL DEFAULT 0,
          image_cooldown_until_ts INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    _add_column_if_missing(conn, "photo_gate", "awaiting_prompt", "INTEGER NOT NULL DEFAULT 0")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS mode_lock (
          user_id INTEGER NOT NULL,
          mode TEXT NOT NULL,
          locked INTEGER NOT NULL DEFAULT 0,
          reason TEXT NOT NULL DEFAULT '',
          updated_at INTEGER NOT NULL,
          PRIMARY KEY (user_id, mode)
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_settings (
          user_id INTEGER PRIMARY KEY,
          model TEXT NOT NULL,
          image_model TEXT NOT NULL DEFAULT '',
          image_provider TEXT NOT NULL DEFAULT 'openrouter'
        )
        """
    )
    _add_column_if_missing(conn, "user_settings", "image_model", "TEXT NOT NULL DEFAULT ''")
    _add_column_if_missing(conn, "user_settings", "image_provider", "TEXT NOT NULL DEFAULT 'openrouter'")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_messages (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id INTEGER NOT NULL,
          role TEXT NOT NULL CHECK(role IN ('user','assistant')),
          content TEXT NOT NULL,
          created_at INTEGER NOT NULL
        )
        """
    )
    _add_column_if_missing(conn, "user_messages", "mode", "TEXT NOT NULL DEFAULT 'basic'")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_messages_user_id ON user_messages(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_messages_user_id_mode ON user_messages(user_id, mode)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          ts INTEGER NOT NULL,
          user_id INTEGER NOT NULL,
          chat_id INTEGER NOT NULL DEFAULT 0,
          username TEXT NOT NULL DEFAULT '',
          first_name TEXT NOT NULL DEFAULT '',
          event_type TEXT NOT NULL,
          mode TEXT NOT NULL DEFAULT '',
          mode_from TEXT NOT NULL DEFAULT '',
          mode_to TEXT NOT NULL DEFAULT '',
          message_id INTEGER NOT NULL DEFAULT 0,
          text_len INTEGER NOT NULL DEFAULT 0,
          photo_provider TEXT NOT NULL DEFAULT '',
          photo_model TEXT NOT NULL DEFAULT '',
          ok INTEGER NOT NULL DEFAULT 1,
          note TEXT NOT NULL DEFAULT ''
        )
        """
    )
    for column_name, ddl in {
        "llm_provider": "TEXT NOT NULL DEFAULT ''",
        "llm_model": "TEXT NOT NULL DEFAULT ''",
        "prompt_tokens": "INTEGER NOT NULL DEFAULT 0",
        "completion_tokens": "INTEGER NOT NULL DEFAULT 0",
        "total_tokens": "INTEGER NOT NULL DEFAULT 0",
        "tokens_source": "TEXT NOT NULL DEFAULT ''",
    }.items():
        _add_column_if_missing(conn, "user_events", column_name, ddl)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_events_user_ts ON user_events(user_id, ts)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_events_ts ON user_events(ts)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_events_type ON user_events(event_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_events_llm ON user_events(date(ts, 'unixepoch'), llm_model)")

    if context.include_relationship_state:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS relationship_state (
              user_id INTEGER NOT NULL,
              mode TEXT NOT NULL,
              state_json TEXT NOT NULL,
              updated_at INTEGER NOT NULL,
              PRIMARY KEY (user_id, mode)
            )
            """
        )


def _migration_002_conversations_backfill(conn: sqlite3.Connection, context: MigrationContext) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS conversations (
          conversation_ref TEXT PRIMARY KEY,
          user_id INTEGER NOT NULL,
          status TEXT NOT NULL DEFAULT 'active',
          is_default INTEGER NOT NULL DEFAULT 0,
          active_mode TEXT NOT NULL DEFAULT 'basic',
          created_at INTEGER NOT NULL,
          updated_at INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_conversations_single_default_per_user
        ON conversations(user_id)
        WHERE is_default = 1
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id)")

    for table_name in ("user_messages", "mode_state", "mode_lock", "photo_gate", "user_events"):
        _add_column_if_missing(conn, table_name, "conversation_ref", "TEXT")
        conn.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{table_name}_conversation_ref ON {table_name}(conversation_ref)"
        )

    if context.include_relationship_state and _table_exists(conn, "relationship_state"):
        _add_column_if_missing(conn, "relationship_state", "conversation_ref", "TEXT")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_relationship_state_conversation_ref ON relationship_state(conversation_ref)"
        )

    now_ts = int(time.time())
    user_ids = _collect_user_ids(conn, context)
    for user_id in user_ids:
        conversation_ref = _default_conversation_ref(user_id)
        active_mode = _legacy_active_mode(conn, user_id)
        conn.execute(
            """
            INSERT INTO conversations(
              conversation_ref, user_id, status, is_default, active_mode, created_at, updated_at
            )
            VALUES (?, ?, 'active', 1, ?, ?, ?)
            ON CONFLICT(conversation_ref) DO UPDATE SET
              active_mode = excluded.active_mode,
              updated_at = excluded.updated_at
            """,
            (conversation_ref, user_id, active_mode, now_ts, now_ts),
        )

        for table_name in ("user_messages", "mode_state", "mode_lock", "photo_gate", "user_events"):
            conn.execute(
                f"UPDATE {table_name} SET conversation_ref=? WHERE user_id=? AND conversation_ref IS NULL",
                (conversation_ref, user_id),
            )

        if context.include_relationship_state and _table_exists(conn, "relationship_state"):
            conn.execute(
                """
                UPDATE relationship_state
                SET conversation_ref=?
                WHERE user_id=? AND conversation_ref IS NULL
                """,
                (conversation_ref, user_id),
            )


def _migration_003_repository_state(conn: sqlite3.Connection, context: MigrationContext) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS conversation_mode_state (
          user_id INTEGER NOT NULL,
          conversation_ref TEXT NOT NULL,
          mode TEXT NOT NULL,
          state_json TEXT NOT NULL,
          updated_at INTEGER NOT NULL,
          PRIMARY KEY (user_id, conversation_ref, mode)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS conversation_mode_lock (
          user_id INTEGER NOT NULL,
          conversation_ref TEXT NOT NULL,
          mode TEXT NOT NULL,
          locked INTEGER NOT NULL DEFAULT 0,
          reason TEXT NOT NULL DEFAULT '',
          updated_at INTEGER NOT NULL,
          PRIMARY KEY (user_id, conversation_ref, mode)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS conversation_photo_gate (
          user_id INTEGER NOT NULL,
          conversation_ref TEXT NOT NULL,
          score INTEGER NOT NULL DEFAULT 0,
          attempts INTEGER NOT NULL DEFAULT 0,
          last_ask_ts INTEGER NOT NULL DEFAULT 0,
          cooldown_until_ts INTEGER NOT NULL DEFAULT 0,
          awaiting_context INTEGER NOT NULL DEFAULT 0,
          context_asked_ts INTEGER NOT NULL DEFAULT 0,
          awaiting_image_prompt INTEGER NOT NULL DEFAULT 0,
          image_cooldown_until_ts INTEGER NOT NULL DEFAULT 0,
          PRIMARY KEY (user_id, conversation_ref)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
          job_id TEXT PRIMARY KEY,
          user_id INTEGER NOT NULL,
          conversation_ref TEXT NOT NULL,
          mode TEXT NOT NULL,
          job_type TEXT NOT NULL,
          status TEXT NOT NULL,
          progress INTEGER NOT NULL DEFAULT 0,
          error_code TEXT,
          result_ref TEXT,
          created_at INTEGER NOT NULL,
          updated_at INTEGER NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON jobs(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_conversation_ref ON jobs(conversation_ref)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")

    if context.include_relationship_state:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_relationship_state (
              user_id INTEGER NOT NULL,
              conversation_ref TEXT NOT NULL,
              mode TEXT NOT NULL,
              state_json TEXT NOT NULL,
              updated_at INTEGER NOT NULL,
              PRIMARY KEY (user_id, conversation_ref, mode)
            )
            """
        )

    conn.execute(
        """
        INSERT INTO conversation_mode_state(user_id, conversation_ref, mode, state_json, updated_at)
        SELECT user_id, COALESCE(conversation_ref, 'legacy-user-' || user_id || '-default'), mode, state_json, updated_at
        FROM mode_state
        WHERE 1 = 1
        ON CONFLICT(user_id, conversation_ref, mode) DO UPDATE SET
          state_json = excluded.state_json,
          updated_at = excluded.updated_at
        """
    )
    conn.execute(
        """
        INSERT INTO conversation_mode_lock(user_id, conversation_ref, mode, locked, reason, updated_at)
        SELECT user_id, COALESCE(conversation_ref, 'legacy-user-' || user_id || '-default'), mode, locked, reason, updated_at
        FROM mode_lock
        WHERE 1 = 1
        ON CONFLICT(user_id, conversation_ref, mode) DO UPDATE SET
          locked = excluded.locked,
          reason = excluded.reason,
          updated_at = excluded.updated_at
        """
    )
    conn.execute(
        """
        INSERT INTO conversation_photo_gate(
          user_id,
          conversation_ref,
          score,
          attempts,
          last_ask_ts,
          cooldown_until_ts,
          awaiting_context,
          context_asked_ts,
          awaiting_image_prompt,
          image_cooldown_until_ts
        )
        SELECT
          user_id,
          COALESCE(conversation_ref, 'legacy-user-' || user_id || '-default'),
          score,
          attempts,
          last_ask_ts,
          cooldown_until_ts,
          awaiting_context,
          context_asked_ts,
          awaiting_image_prompt,
          image_cooldown_until_ts
        FROM photo_gate
        WHERE 1 = 1
        ON CONFLICT(user_id, conversation_ref) DO UPDATE SET
          score = excluded.score,
          attempts = excluded.attempts,
          last_ask_ts = excluded.last_ask_ts,
          cooldown_until_ts = excluded.cooldown_until_ts,
          awaiting_context = excluded.awaiting_context,
          context_asked_ts = excluded.context_asked_ts,
          awaiting_image_prompt = excluded.awaiting_image_prompt,
          image_cooldown_until_ts = excluded.image_cooldown_until_ts
        """
    )

    if context.include_relationship_state and _table_exists(conn, "relationship_state"):
        conn.execute(
            """
            INSERT INTO conversation_relationship_state(user_id, conversation_ref, mode, state_json, updated_at)
            SELECT user_id, COALESCE(conversation_ref, 'legacy-user-' || user_id || '-default'), mode, state_json, updated_at
            FROM relationship_state
            WHERE 1 = 1
            ON CONFLICT(user_id, conversation_ref, mode) DO UPDATE SET
              state_json = excluded.state_json,
              updated_at = excluded.updated_at
            """
        )


def _collect_user_ids(conn: sqlite3.Connection, context: MigrationContext) -> list[int]:
    user_ids: set[int] = set()
    sources = [
        ("user_profile", "user_id"),
        ("user_messages", "user_id"),
        ("mode_state", "user_id"),
        ("mode_lock", "user_id"),
        ("photo_gate", "user_id"),
        ("user_events", "user_id"),
    ]
    if context.include_relationship_state and _table_exists(conn, "relationship_state"):
        sources.append(("relationship_state", "user_id"))

    for table_name, column_name in sources:
        if not _table_exists(conn, table_name):
            continue
        rows = conn.execute(f"SELECT DISTINCT {column_name} FROM {table_name}").fetchall()
        for row in rows:
            if row[0] is not None:
                user_ids.add(int(row[0]))
    return sorted(user_ids)


def _legacy_active_mode(conn: sqlite3.Connection, user_id: int) -> str:
    row = conn.execute("SELECT mode FROM user_profile WHERE user_id=?", (user_id,)).fetchone()
    if row and row[0]:
        return str(row[0])
    return "basic"


def _default_conversation_ref(user_id: int) -> str:
    return f"legacy-user-{user_id}-default"


def default_conversation_ref(user_id: int) -> str:
    return _default_conversation_ref(user_id)
