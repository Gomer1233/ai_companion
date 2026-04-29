from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

from src.core.contracts import ConversationRef, DeferredJob, JobStatus, JobType, UserRef


CUTOVER_TABLES = (
    "conversations",
    "user_messages",
    "conversation_mode_state",
    "conversation_mode_lock",
    "conversation_photo_gate",
    "conversation_relationship_state",
    "jobs",
    "sessions",
)


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
        tables = {table_name: _select_all(conn, table_name) for table_name in CUTOVER_TABLES if _table_exists(conn, table_name)}
    finally:
        conn.close()

    user_ids = _collect_user_ids(tables)
    tables["users"] = [{"user_id": user_id} for user_id in sorted(user_ids)]
    return CutoverSnapshot(tables=tables)


def snapshot_counts(snapshot: CutoverSnapshot) -> dict[str, int]:
    return {
        table_name: len(rows)
        for table_name, rows in sorted(snapshot.tables.items())
        if rows
    }


def import_snapshot_to_repositories(snapshot: CutoverSnapshot, repositories) -> CutoverImportResult:
    counts: dict[str, int] = {}

    for row in snapshot.tables.get("conversations", []):
        user_ref = UserRef(str(row["user_id"]))
        conversation_ref = ConversationRef(str(row["conversation_ref"]))
        if bool(int(row.get("is_default") or 0)):
            repositories.ensure_default_conversation(user_ref, active_mode=str(row.get("active_mode") or "basic"))
        else:
            repositories.create_conversation(
                user_ref,
                active_mode=str(row.get("active_mode") or "basic"),
                is_default=False,
                conversation_ref=conversation_ref,
            )
        repositories.set_active_mode(user_ref, conversation_ref, str(row.get("active_mode") or "basic"))
        counts["conversations"] = counts.get("conversations", 0) + 1

    for row in snapshot.tables.get("user_messages", []):
        repositories.append_history(
            UserRef(str(row["user_id"])),
            ConversationRef(str(row["conversation_ref"])),
            str(row.get("mode") or "basic"),
            str(row["role"]),
            str(row["content"]),
            created_at=int(row.get("created_at") or 0),
        )
        counts["user_messages"] = counts.get("user_messages", 0) + 1

    for row in snapshot.tables.get("conversation_mode_state", []):
        repositories.save_mode_state(
            UserRef(str(row["user_id"])),
            ConversationRef(str(row["conversation_ref"])),
            str(row["mode"]),
            _decode_state(row.get("state_json")),
        )
        counts["conversation_mode_state"] = counts.get("conversation_mode_state", 0) + 1

    for row in snapshot.tables.get("conversation_mode_lock", []):
        user_ref = UserRef(str(row["user_id"]))
        conversation_ref = ConversationRef(str(row["conversation_ref"]))
        mode = str(row["mode"])
        if bool(int(row.get("locked") or 0)):
            repositories.lock_mode(user_ref, conversation_ref, mode, reason=str(row.get("reason") or ""))
        else:
            repositories.unlock_mode(user_ref, conversation_ref, mode)
        counts["conversation_mode_lock"] = counts.get("conversation_mode_lock", 0) + 1

    for row in snapshot.tables.get("conversation_photo_gate", []):
        repositories.upsert_photo_gate(
            UserRef(str(row["user_id"])),
            ConversationRef(str(row["conversation_ref"])),
            {
                "score": int(row.get("score") or 0),
                "attempts": int(row.get("attempts") or 0),
                "last_ask_ts": int(row.get("last_ask_ts") or 0),
                "cooldown_until_ts": int(row.get("cooldown_until_ts") or 0),
                "awaiting_context": int(row.get("awaiting_context") or 0),
                "context_asked_ts": int(row.get("context_asked_ts") or 0),
                "awaiting_image_prompt": int(row.get("awaiting_image_prompt") or 0),
                "image_cooldown_until_ts": int(row.get("image_cooldown_until_ts") or 0),
            },
        )
        counts["conversation_photo_gate"] = counts.get("conversation_photo_gate", 0) + 1

    for row in snapshot.tables.get("conversation_relationship_state", []):
        repositories.save_relationship_state(
            UserRef(str(row["user_id"])),
            ConversationRef(str(row["conversation_ref"])),
            str(row["mode"]),
            _decode_state(row.get("state_json")),
        )
        counts["conversation_relationship_state"] = counts.get("conversation_relationship_state", 0) + 1

    for row in snapshot.tables.get("sessions", []):
        repositories.create_session(
            UserRef(str(row["user_id"])),
            issued_at=int(row["issued_at"]),
            expires_at=int(row["expires_at"]),
            session_token=str(row["session_token"]),
        )
        if int(row.get("last_seen_at") or row["issued_at"]) != int(row["issued_at"]):
            repositories.touch_session(str(row["session_token"]), last_seen_at=int(row["last_seen_at"]))
        counts["sessions"] = counts.get("sessions", 0) + 1

    for row in snapshot.tables.get("jobs", []):
        repositories.create_job(
            DeferredJob(
                job_id=str(row["job_id"]),
                user_ref=UserRef(str(row["user_id"])),
                conversation_ref=ConversationRef(str(row["conversation_ref"])),
                mode=str(row["mode"]),
                job_type=JobType(str(row["job_type"])),
                status=JobStatus(str(row["status"])),
                progress=int(row.get("progress") or 0),
                error_code=row.get("error_code"),
                result_ref=row.get("result_ref"),
                created_at=int(row.get("created_at") or 0),
                updated_at=int(row.get("updated_at") or 0),
            )
        )
        counts["jobs"] = counts.get("jobs", 0) + 1

    counts["users"] = len(snapshot.tables.get("users", []))
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


def _decode_state(value: Any) -> dict[str, Any]:
    import json

    if not value:
        return {}
    decoded = json.loads(str(value))
    return decoded if isinstance(decoded, dict) else {}
