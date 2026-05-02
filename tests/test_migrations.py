from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from src.db.migrations import default_conversation_ref, migrate_database


def _table_exists(db_path: Path, table_name: str) -> bool:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        ).fetchone()
        return bool(row)
    finally:
        conn.close()


def _column_names(db_path: Path, table_name: str) -> set[str]:
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        return {row[1] for row in rows}
    finally:
        conn.close()


def test_fresh_database_migrates_to_head(tmp_path):
    db_path = tmp_path / "fresh.db"

    migrate_database(str(db_path), include_relationship_state=False)

    assert _table_exists(db_path, "schema_version")
    assert _table_exists(db_path, "conversations")
    assert _table_exists(db_path, "conversation_mode_state")
    assert _table_exists(db_path, "conversation_mode_lock")
    assert _table_exists(db_path, "conversation_photo_gate")
    assert _table_exists(db_path, "jobs")
    assert _table_exists(db_path, "sessions")
    assert _table_exists(db_path, "entitlements")
    assert _table_exists(db_path, "usage_counters")
    assert _table_exists(db_path, "access_grants")
    assert _table_exists(db_path, "explicit_consent")
    assert _table_exists(db_path, "payment_orders")
    assert _table_exists(db_path, "admin_audit_events")
    assert "revoked_at" in _column_names(db_path, "entitlements")
    assert "entitlement_id" in _column_names(db_path, "payment_orders")
    assert "conversation_ref" in _column_names(db_path, "user_messages")
    assert "conversation_ref" in _column_names(db_path, "mode_state")
    assert "conversation_ref" in _column_names(db_path, "mode_lock")
    assert "conversation_ref" in _column_names(db_path, "photo_gate")
    assert "conversation_ref" in _column_names(db_path, "user_events")

    conn = sqlite3.connect(db_path)
    try:
        version = conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()[0]
        assert version == 5
    finally:
        conn.close()



def test_legacy_database_backfills_default_conversation(tmp_path):
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("CREATE TABLE user_profile (user_id INTEGER PRIMARY KEY, preferred_name TEXT, preferred_title TEXT, mode TEXT, mode_picked INTEGER, chat_locked INTEGER, lock_reason TEXT)")
        cur.execute("CREATE TABLE user_messages (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, created_at INTEGER NOT NULL, mode TEXT NOT NULL DEFAULT 'basic')")
        cur.execute("CREATE TABLE mode_state (user_id INTEGER NOT NULL, mode TEXT NOT NULL, state_json TEXT NOT NULL, updated_at INTEGER NOT NULL, PRIMARY KEY (user_id, mode))")
        cur.execute("CREATE TABLE mode_lock (user_id INTEGER NOT NULL, mode TEXT NOT NULL, locked INTEGER NOT NULL DEFAULT 0, reason TEXT NOT NULL DEFAULT '', updated_at INTEGER NOT NULL, PRIMARY KEY (user_id, mode))")
        cur.execute("CREATE TABLE photo_gate (user_id INTEGER PRIMARY KEY, score INTEGER NOT NULL DEFAULT 0, attempts INTEGER NOT NULL DEFAULT 0, last_ask_ts INTEGER NOT NULL DEFAULT 0, cooldown_until_ts INTEGER NOT NULL DEFAULT 0, awaiting_context INTEGER NOT NULL DEFAULT 0, context_asked_ts INTEGER NOT NULL DEFAULT 0, awaiting_image_prompt INTEGER NOT NULL DEFAULT 0, image_cooldown_until_ts INTEGER NOT NULL DEFAULT 0)")
        cur.execute("CREATE TABLE user_events (id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER NOT NULL, user_id INTEGER NOT NULL, chat_id INTEGER NOT NULL DEFAULT 0, username TEXT NOT NULL DEFAULT '', first_name TEXT NOT NULL DEFAULT '', event_type TEXT NOT NULL, mode TEXT NOT NULL DEFAULT '', mode_from TEXT NOT NULL DEFAULT '', mode_to TEXT NOT NULL DEFAULT '', message_id INTEGER NOT NULL DEFAULT 0, text_len INTEGER NOT NULL DEFAULT 0, photo_provider TEXT NOT NULL DEFAULT '', photo_model TEXT NOT NULL DEFAULT '', ok INTEGER NOT NULL DEFAULT 1, note TEXT NOT NULL DEFAULT '')")
        cur.execute("CREATE TABLE relationship_state (user_id INTEGER NOT NULL, mode TEXT NOT NULL, state_json TEXT NOT NULL, updated_at INTEGER NOT NULL, PRIMARY KEY (user_id, mode))")

        cur.execute("INSERT INTO user_profile(user_id, preferred_name, preferred_title, mode, mode_picked, chat_locked, lock_reason) VALUES (1, '', '', 'chef', 1, 0, '')")
        cur.execute("INSERT INTO user_profile(user_id, preferred_name, preferred_title, mode, mode_picked, chat_locked, lock_reason) VALUES (2, '', '', 'whore', 1, 0, '')")
        cur.execute("INSERT INTO user_messages(user_id, role, content, created_at, mode) VALUES (1, 'user', 'hello', 100, 'chef')")
        cur.execute("INSERT INTO user_messages(user_id, role, content, created_at, mode) VALUES (2, 'assistant', 'reply', 101, 'whore')")
        cur.execute("INSERT INTO mode_state(user_id, mode, state_json, updated_at) VALUES (1, 'chef', ?, 200)", (json.dumps({'recap': 'busy'}),))
        cur.execute("INSERT INTO mode_lock(user_id, mode, locked, reason, updated_at) VALUES (2, 'whore', 1, 'GAME OVER', 201)")
        cur.execute("INSERT INTO photo_gate(user_id, score, attempts, last_ask_ts, cooldown_until_ts, awaiting_context, context_asked_ts, awaiting_image_prompt, image_cooldown_until_ts) VALUES (1, 2, 1, 10, 20, 0, 0, 1, 30)")
        cur.execute("INSERT INTO user_events(ts, user_id, event_type, mode, note) VALUES (300, 1, 'message', 'chef', 'legacy')")
        cur.execute("INSERT INTO relationship_state(user_id, mode, state_json, updated_at) VALUES (2, 'whore', ?, 400)", (json.dumps({'stage': 'STRANGER', 'points': 7, 'mood': 'neutral', 'mood_intensity': 0.5, 'user_name': 'T', 'known_facts': [], 'nsfw_unlocked': False, 'warnings_count': 0, 'last_interaction_ts': 0}),))
        conn.commit()
    finally:
        conn.close()

    migrate_database(str(db_path), include_relationship_state=True)

    conn = sqlite3.connect(db_path)
    try:
        conversations = conn.execute(
            "SELECT conversation_ref, user_id, active_mode, is_default, status FROM conversations ORDER BY user_id"
        ).fetchall()
        assert conversations == [
            (default_conversation_ref(1), 1, 'chef', 1, 'active'),
            (default_conversation_ref(2), 2, 'whore', 1, 'active'),
        ]

        assert conn.execute("SELECT conversation_ref FROM user_messages WHERE user_id=1").fetchone()[0] == default_conversation_ref(1)
        assert conn.execute("SELECT conversation_ref FROM mode_state WHERE user_id=1 AND mode='chef'").fetchone()[0] == default_conversation_ref(1)
        assert conn.execute("SELECT conversation_ref FROM mode_lock WHERE user_id=2 AND mode='whore'").fetchone()[0] == default_conversation_ref(2)
        assert conn.execute("SELECT conversation_ref FROM photo_gate WHERE user_id=1").fetchone()[0] == default_conversation_ref(1)
        assert conn.execute("SELECT conversation_ref FROM user_events WHERE user_id=1").fetchone()[0] == default_conversation_ref(1)
        assert conn.execute("SELECT conversation_ref FROM relationship_state WHERE user_id=2 AND mode='whore'").fetchone()[0] == default_conversation_ref(2)
        assert conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()[0] == 5
        assert conn.execute("SELECT COUNT(*) FROM conversation_mode_state").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM conversation_mode_lock").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM conversation_photo_gate").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM conversation_relationship_state").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0
    finally:
        conn.close()



def test_migrator_rerun_is_idempotent(tmp_path):
    db_path = tmp_path / "rerun.db"

    migrate_database(str(db_path), include_relationship_state=True)
    migrate_database(str(db_path), include_relationship_state=True)

    conn = sqlite3.connect(db_path)
    try:
        version = conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()[0]
        assert version == 5
        assert conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0
    finally:
        conn.close()
