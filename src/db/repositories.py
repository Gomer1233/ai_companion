from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from typing import Any

from src.core.contracts import (
    AnalyticsEvent,
    AnalyticsEventType,
    ConversationRecord,
    ConversationRef,
    ConversationStatus,
    DeferredJob,
    JobStatus,
    JobType,
    UserRef,
)
from src.db.connection import connect_sqlite
from src.db.migrations import default_conversation_ref


DEFAULT_PHOTO_GATE = {
    "score": 0,
    "attempts": 0,
    "last_ask_ts": 0,
    "cooldown_until_ts": 0,
    "awaiting_context": 0,
    "context_asked_ts": 0,
    "awaiting_image_prompt": 0,
    "image_cooldown_until_ts": 0,
}

TERMINAL_JOB_STATUSES = {
    JobStatus.COMPLETED.value,
    JobStatus.FAILED.value,
    JobStatus.CANCELLED.value,
}


def legacy_user_ref(user_id: int) -> UserRef:
    return UserRef(str(user_id))


def legacy_conversation_ref(user_id: int) -> ConversationRef:
    return ConversationRef(default_conversation_ref(user_id))


@dataclass(slots=True)
class SQLiteRepositories:
    db_path: str
    include_relationship_state: bool = False
    history_limit: int = 12

    def _connect(self):
        return connect_sqlite(self.db_path)

    def _user_id(self, user_ref: UserRef) -> int:
        try:
            return int(user_ref.value)
        except ValueError as exc:
            raise ValueError("SQLiteRepositories currently requires numeric UserRef values") from exc

    def _resolve_conversation_ref(self, user_ref: UserRef, conversation_ref: ConversationRef | None) -> ConversationRef:
        if conversation_ref is not None:
            return conversation_ref
        return self.ensure_default_conversation(user_ref).conversation_ref

    def _now(self) -> int:
        return int(time.time())

    def ensure_default_conversation(self, user_ref: UserRef, *, active_mode: str = "basic") -> ConversationRecord:
        user_id = self._user_id(user_ref)
        conversation_ref = legacy_conversation_ref(user_id)
        now_ts = self._now()
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO conversations(
                  conversation_ref, user_id, status, is_default, active_mode, created_at, updated_at
                )
                VALUES (?, ?, ?, 1, ?, ?, ?)
                ON CONFLICT(conversation_ref) DO UPDATE SET
                  updated_at = excluded.updated_at
                """,
                (
                    conversation_ref.value,
                    user_id,
                    ConversationStatus.ACTIVE.value,
                    active_mode,
                    now_ts,
                    now_ts,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return self.load_conversation(user_ref, conversation_ref) or ConversationRecord(
            user_ref=user_ref,
            conversation_ref=conversation_ref,
            active_mode=active_mode,
            status=ConversationStatus.ACTIVE,
            is_default=True,
        )

    def create_conversation(
        self,
        user_ref: UserRef,
        *,
        active_mode: str = "basic",
        is_default: bool = False,
        conversation_ref: ConversationRef | None = None,
    ) -> ConversationRecord:
        user_id = self._user_id(user_ref)
        resolved_ref = conversation_ref or ConversationRef(f"conv-{user_id}-{uuid.uuid4().hex[:12]}")
        now_ts = self._now()
        conn = self._connect()
        try:
            if is_default:
                existing = conn.execute(
                    "SELECT conversation_ref FROM conversations WHERE user_id=? AND is_default=1",
                    (user_id,),
                ).fetchone()
                if existing and existing[0] != resolved_ref.value:
                    raise ValueError("A user cannot have more than one default conversation")

            conn.execute(
                """
                INSERT INTO conversations(
                  conversation_ref, user_id, status, is_default, active_mode, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    resolved_ref.value,
                    user_id,
                    ConversationStatus.ACTIVE.value,
                    1 if is_default else 0,
                    active_mode,
                    now_ts,
                    now_ts,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return ConversationRecord(
            user_ref=user_ref,
            conversation_ref=resolved_ref,
            active_mode=active_mode,
            status=ConversationStatus.ACTIVE,
            is_default=is_default,
        )

    def archive_conversation(self, user_ref: UserRef, conversation_ref: ConversationRef) -> None:
        user_id = self._user_id(user_ref)
        conn = self._connect()
        try:
            conn.execute(
                """
                UPDATE conversations
                SET status=?, updated_at=?
                WHERE user_id=? AND conversation_ref=?
                """,
                (ConversationStatus.ARCHIVED.value, self._now(), user_id, conversation_ref.value),
            )
            conn.commit()
        finally:
            conn.close()

    def load_conversation(self, user_ref: UserRef, conversation_ref: ConversationRef) -> ConversationRecord | None:
        user_id = self._user_id(user_ref)
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT conversation_ref, active_mode, status, is_default
                FROM conversations
                WHERE user_id=? AND conversation_ref=?
                """,
                (user_id, conversation_ref.value),
            ).fetchone()
        finally:
            conn.close()
        if not row:
            return None
        return ConversationRecord(
            user_ref=user_ref,
            conversation_ref=ConversationRef(str(row[0])),
            active_mode=str(row[1] or "basic"),
            status=ConversationStatus(str(row[2] or ConversationStatus.ACTIVE.value)),
            is_default=bool(int(row[3] or 0)),
        )

    def load_active_conversation_for_user(self, user_ref: UserRef) -> ConversationRecord | None:
        user_id = self._user_id(user_ref)
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT conversation_ref, active_mode, status, is_default
                FROM conversations
                WHERE user_id=? AND status=?
                ORDER BY updated_at DESC, created_at DESC
                LIMIT 1
                """,
                (user_id, ConversationStatus.ACTIVE.value),
            ).fetchone()
        finally:
            conn.close()
        if not row:
            return None
        return ConversationRecord(
            user_ref=user_ref,
            conversation_ref=ConversationRef(str(row[0])),
            active_mode=str(row[1] or "basic"),
            status=ConversationStatus(str(row[2] or ConversationStatus.ACTIVE.value)),
            is_default=bool(int(row[3] or 0)),
        )

    def append_history(
        self,
        user_ref: UserRef,
        conversation_ref: ConversationRef,
        mode: str,
        role: str,
        content: str,
        *,
        created_at: int | None = None,
    ) -> None:
        user_id = self._user_id(user_ref)
        now_ts = self._now() if created_at is None else created_at
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO user_messages(user_id, conversation_ref, mode, role, content, created_at)
                VALUES(?,?,?,?,?,?)
                """,
                (user_id, conversation_ref.value, mode, role, content, now_ts),
            )
            conn.execute(
                """
                DELETE FROM user_messages
                WHERE user_id = ?
                  AND conversation_ref = ?
                  AND mode = ?
                  AND id NOT IN (
                    SELECT id FROM user_messages
                    WHERE user_id = ?
                      AND conversation_ref = ?
                      AND mode = ?
                    ORDER BY id DESC
                    LIMIT ?
                  )
                """,
                (
                    user_id,
                    conversation_ref.value,
                    mode,
                    user_id,
                    conversation_ref.value,
                    mode,
                    self.history_limit,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def load_history(
        self,
        user_ref: UserRef,
        conversation_ref: ConversationRef,
        mode: str,
    ) -> list[dict[str, Any]]:
        user_id = self._user_id(user_ref)
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT role, content
                FROM user_messages
                WHERE user_id = ?
                  AND conversation_ref = ?
                  AND mode = ?
                ORDER BY id ASC
                """,
                (user_id, conversation_ref.value, mode),
            ).fetchall()
        finally:
            conn.close()
        return [{"role": role, "content": content} for role, content in rows]

    def clear_history(
        self,
        user_ref: UserRef,
        conversation_ref: ConversationRef,
        *,
        mode: str | None = None,
    ) -> None:
        user_id = self._user_id(user_ref)
        conn = self._connect()
        try:
            if mode:
                conn.execute(
                    """
                    DELETE FROM user_messages
                    WHERE user_id=? AND conversation_ref=? AND mode=?
                    """,
                    (user_id, conversation_ref.value, mode),
                )
            else:
                conn.execute(
                    "DELETE FROM user_messages WHERE user_id=? AND conversation_ref=?",
                    (user_id, conversation_ref.value),
                )
            conn.commit()
        finally:
            conn.close()

    def set_active_mode(self, user_ref: UserRef, conversation_ref: ConversationRef, mode: str) -> None:
        user_id = self._user_id(user_ref)
        now_ts = self._now()
        conn = self._connect()
        try:
            conn.execute(
                """
                UPDATE conversations
                SET active_mode=?, updated_at=?
                WHERE user_id=? AND conversation_ref=?
                """,
                (mode, now_ts, user_id, conversation_ref.value),
            )
            conn.execute(
                """
                INSERT INTO user_profile(user_id, preferred_name, preferred_title, mode)
                VALUES(?,?,?,?)
                ON CONFLICT(user_id) DO UPDATE SET mode=excluded.mode
                """,
                (user_id, "", "", mode),
            )
            conn.commit()
        finally:
            conn.close()

    def get_active_mode(self, user_ref: UserRef, conversation_ref: ConversationRef) -> str:
        conversation = self.load_conversation(user_ref, conversation_ref)
        if conversation is not None:
            return conversation.active_mode
        return "basic"


    def get_active_dialog_stats(self, user_ref: UserRef) -> dict[str, int]:
        user_id = self._user_id(user_ref)
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT mode, COUNT(*) as cnt
                FROM user_messages
                WHERE user_id = ?
                GROUP BY mode
                """,
                (user_id,),
            ).fetchall()
        finally:
            conn.close()
        return {str(mode): int(count) for mode, count in rows if mode}

    def get_user_profile(self, user_ref: UserRef) -> dict[str, str]:
        user_id = self._user_id(user_ref)
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT
                  preferred_name,
                  preferred_title,
                  COALESCE(mode, ''),
                  COALESCE(chat_locked, 0),
                  COALESCE(mode_picked, 0),
                  COALESCE(lock_reason, '')
                FROM user_profile
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
        finally:
            conn.close()
        if not row:
            return {
                "preferred_name": "",
                "preferred_title": "",
                "mode": "",
                "mode_picked": "0",
                "chat_locked": "0",
                "lock_reason": "",
            }
        return {
            "preferred_name": str(row[0] or ""),
            "preferred_title": str(row[1] or ""),
            "mode": str(row[2] or ""),
            "chat_locked": str(int(row[3] or 0)),
            "mode_picked": str(int(row[4] or 0)),
            "lock_reason": str(row[5] or ""),
        }

    def set_user_profile(
        self,
        user_ref: UserRef,
        *,
        preferred_name: str | None = None,
        preferred_title: str | None = None,
        mode: str | None = None,
    ) -> None:
        user_id = self._user_id(user_ref)
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO user_profile(user_id, preferred_name, preferred_title, mode)
                VALUES(?,?,?,?)
                ON CONFLICT(user_id) DO UPDATE SET
                  preferred_name = COALESCE(excluded.preferred_name, user_profile.preferred_name),
                  preferred_title = COALESCE(excluded.preferred_title, user_profile.preferred_title),
                  mode = COALESCE(excluded.mode, user_profile.mode)
                """,
                (user_id, preferred_name, preferred_title, mode),
            )
            conn.commit()
        finally:
            conn.close()

    def set_mode_picked(self, user_ref: UserRef, picked: bool) -> None:
        user_id = self._user_id(user_ref)
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO user_profile(user_id, preferred_name, preferred_title, mode, mode_picked)
                VALUES(?,?,?,?,?)
                ON CONFLICT(user_id) DO UPDATE SET
                  mode_picked=excluded.mode_picked
                """,
                (user_id, "", "", "basic", 1 if picked else 0),
            )
            conn.commit()
        finally:
            conn.close()

    def lock_chat(self, user_ref: UserRef, reason: str = "") -> None:
        user_id = self._user_id(user_ref)
        conn = self._connect()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO user_profile(user_id, preferred_name, preferred_title, mode) VALUES(?,?,?,?)",
                (user_id, "", "", "basic"),
            )
            conn.execute(
                """
                UPDATE user_profile
                SET chat_locked = 1,
                    lock_reason = ?
                WHERE user_id = ?
                """,
                (reason or "", user_id),
            )
            conn.commit()
        finally:
            conn.close()

    def unlock_chat(self, user_ref: UserRef) -> None:
        user_id = self._user_id(user_ref)
        conn = self._connect()
        try:
            conn.execute(
                """
                UPDATE user_profile
                SET chat_locked = 0,
                    lock_reason = ''
                WHERE user_id = ?
                """,
                (user_id,),
            )
            conn.commit()
        finally:
            conn.close()

    def get_user_model(self, user_ref: UserRef, *, default_model: str) -> str:
        user_id = self._user_id(user_ref)
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT model FROM user_settings WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if row and row[0]:
                return str(row[0])
            conn.execute(
                """
                INSERT INTO user_settings(user_id, model)
                VALUES(?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                  model=excluded.model
                """,
                (user_id, default_model),
            )
            conn.commit()
            return default_model
        finally:
            conn.close()

    def set_user_model(self, user_ref: UserRef, model: str) -> None:
        user_id = self._user_id(user_ref)
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO user_settings(user_id, model)
                VALUES(?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                  model=excluded.model
                """,
                (user_id, model),
            )
            conn.commit()
        finally:
            conn.close()

    def load_mode_state(
        self,
        user_ref: UserRef,
        conversation_ref: ConversationRef,
        mode: str,
    ) -> dict[str, Any] | None:
        user_id = self._user_id(user_ref)
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT state_json
                FROM conversation_mode_state
                WHERE user_id=? AND conversation_ref=? AND mode=?
                """,
                (user_id, conversation_ref.value, mode),
            ).fetchone()
        finally:
            conn.close()
        if not row or not row[0]:
            return None
        try:
            value = json.loads(row[0])
        except json.JSONDecodeError:
            return None
        return value if isinstance(value, dict) else None

    def save_mode_state(
        self,
        user_ref: UserRef,
        conversation_ref: ConversationRef,
        mode: str,
        state: dict[str, Any],
    ) -> None:
        user_id = self._user_id(user_ref)
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO conversation_mode_state(user_id, conversation_ref, mode, state_json, updated_at)
                VALUES(?,?,?,?,?)
                ON CONFLICT(user_id, conversation_ref, mode) DO UPDATE SET
                  state_json=excluded.state_json,
                  updated_at=excluded.updated_at
                """,
                (user_id, conversation_ref.value, mode, json.dumps(state, ensure_ascii=False), self._now()),
            )
            conn.commit()
        finally:
            conn.close()

    def get_photo_gate(self, user_ref: UserRef, conversation_ref: ConversationRef) -> dict[str, int]:
        user_id = self._user_id(user_ref)
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT
                  score,
                  attempts,
                  last_ask_ts,
                  cooldown_until_ts,
                  awaiting_context,
                  context_asked_ts,
                  awaiting_image_prompt,
                  image_cooldown_until_ts
                FROM conversation_photo_gate
                WHERE user_id=? AND conversation_ref=?
                """,
                (user_id, conversation_ref.value),
            ).fetchone()
        finally:
            conn.close()
        if not row:
            return dict(DEFAULT_PHOTO_GATE)
        keys = list(DEFAULT_PHOTO_GATE.keys())
        return {key: int(row[index] or 0) for index, key in enumerate(keys)}

    def upsert_photo_gate(self, user_ref: UserRef, conversation_ref: ConversationRef, gate: dict[str, int]) -> None:
        user_id = self._user_id(user_ref)
        values = {**DEFAULT_PHOTO_GATE, **gate}
        conn = self._connect()
        try:
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
                VALUES(?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(user_id, conversation_ref) DO UPDATE SET
                  score=excluded.score,
                  attempts=excluded.attempts,
                  last_ask_ts=excluded.last_ask_ts,
                  cooldown_until_ts=excluded.cooldown_until_ts,
                  awaiting_context=excluded.awaiting_context,
                  context_asked_ts=excluded.context_asked_ts,
                  awaiting_image_prompt=excluded.awaiting_image_prompt,
                  image_cooldown_until_ts=excluded.image_cooldown_until_ts
                """,
                (
                    user_id,
                    conversation_ref.value,
                    values["score"],
                    values["attempts"],
                    values["last_ask_ts"],
                    values["cooldown_until_ts"],
                    values["awaiting_context"],
                    values["context_asked_ts"],
                    values["awaiting_image_prompt"],
                    values["image_cooldown_until_ts"],
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def lock_mode(self, user_ref: UserRef, conversation_ref: ConversationRef, mode: str, reason: str = "") -> None:
        user_id = self._user_id(user_ref)
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO conversation_mode_lock(user_id, conversation_ref, mode, locked, reason, updated_at)
                VALUES(?,?,?,?,?,?)
                ON CONFLICT(user_id, conversation_ref, mode) DO UPDATE SET
                  locked=excluded.locked,
                  reason=excluded.reason,
                  updated_at=excluded.updated_at
                """,
                (user_id, conversation_ref.value, mode, 1, reason.strip(), self._now()),
            )
            conn.commit()
        finally:
            conn.close()

    def unlock_mode(self, user_ref: UserRef, conversation_ref: ConversationRef, mode: str) -> None:
        user_id = self._user_id(user_ref)
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO conversation_mode_lock(user_id, conversation_ref, mode, locked, reason, updated_at)
                VALUES(?,?,?,?,?,?)
                ON CONFLICT(user_id, conversation_ref, mode) DO UPDATE SET
                  locked=excluded.locked,
                  reason=excluded.reason,
                  updated_at=excluded.updated_at
                """,
                (user_id, conversation_ref.value, mode, 0, "", self._now()),
            )
            conn.commit()
        finally:
            conn.close()

    def is_mode_locked(self, user_ref: UserRef, conversation_ref: ConversationRef, mode: str) -> tuple[bool, str]:
        user_id = self._user_id(user_ref)
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT locked, reason
                FROM conversation_mode_lock
                WHERE user_id=? AND conversation_ref=? AND mode=?
                """,
                (user_id, conversation_ref.value, mode),
            ).fetchone()
        finally:
            conn.close()
        if not row:
            return False, ""
        return bool(int(row[0] or 0)), str(row[1] or "")

    def create_job(self, job: DeferredJob) -> DeferredJob:
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO jobs(
                  job_id,
                  user_id,
                  conversation_ref,
                  mode,
                  job_type,
                  status,
                  progress,
                  error_code,
                  result_ref,
                  created_at,
                  updated_at
                )
                VALUES(?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    job.job_id,
                    self._user_id(job.user_ref),
                    job.conversation_ref.value,
                    job.mode,
                    job.job_type.value,
                    job.status.value,
                    job.progress,
                    job.error_code,
                    job.result_ref,
                    job.created_at,
                    job.updated_at,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return job

    def load_job(self, job_id: str) -> DeferredJob | None:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT job_id, user_id, conversation_ref, mode, job_type, status, progress, error_code, result_ref, created_at, updated_at
                FROM jobs
                WHERE job_id=?
                """,
                (job_id,),
            ).fetchone()
        finally:
            conn.close()
        if not row:
            return None
        return DeferredJob(
            job_id=str(row[0]),
            user_ref=legacy_user_ref(int(row[1])),
            conversation_ref=ConversationRef(str(row[2])),
            mode=str(row[3]),
            job_type=JobType(str(row[4])),
            status=JobStatus(str(row[5])),
            progress=int(row[6] or 0),
            error_code=row[7],
            result_ref=row[8],
            created_at=int(row[9] or 0),
            updated_at=int(row[10] or 0),
        )

    def update_job_status(
        self,
        job_id: str,
        next_status: JobStatus,
        *,
        progress: int | None = None,
        error_code: str | None = None,
        result_ref: str | None = None,
    ) -> DeferredJob:
        conn = self._connect()
        try:
            with conn:
                row = conn.execute(
                    """
                    SELECT job_id, user_id, conversation_ref, mode, job_type, status, progress, error_code, result_ref, created_at, updated_at
                    FROM jobs
                    WHERE job_id=?
                    """,
                    (job_id,),
                ).fetchone()
                if not row:
                    raise KeyError(f"Unknown job_id: {job_id}")

                current = DeferredJob(
                    job_id=str(row[0]),
                    user_ref=legacy_user_ref(int(row[1])),
                    conversation_ref=ConversationRef(str(row[2])),
                    mode=str(row[3]),
                    job_type=JobType(str(row[4])),
                    status=JobStatus(str(row[5])),
                    progress=int(row[6] or 0),
                    error_code=row[7],
                    result_ref=row[8],
                    created_at=int(row[9] or 0),
                    updated_at=int(row[10] or 0),
                )
                updated = current.with_status(
                    next_status,
                    progress=progress,
                    error_code=error_code,
                    result_ref=result_ref,
                    updated_at=self._now(),
                )
                conn.execute(
                    """
                    UPDATE jobs
                    SET status=?, progress=?, error_code=?, result_ref=?, updated_at=?
                    WHERE job_id=?
                    """,
                    (
                        updated.status.value,
                        updated.progress,
                        updated.error_code,
                        updated.result_ref,
                        updated.updated_at,
                        updated.job_id,
                    ),
                )
            return updated
        finally:
            conn.close()

    def load_relationship_state(
        self,
        user_ref: UserRef,
        conversation_ref: ConversationRef,
        mode: str,
    ) -> dict[str, Any] | None:
        if not self.include_relationship_state:
            return None
        user_id = self._user_id(user_ref)
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT state_json
                FROM conversation_relationship_state
                WHERE user_id=? AND conversation_ref=? AND mode=?
                """,
                (user_id, conversation_ref.value, mode),
            ).fetchone()
        finally:
            conn.close()
        if not row or not row[0]:
            return None
        value = json.loads(row[0])
        return value if isinstance(value, dict) else None

    def save_relationship_state(
        self,
        user_ref: UserRef,
        conversation_ref: ConversationRef,
        mode: str,
        state: dict[str, Any],
    ) -> None:
        if not self.include_relationship_state:
            return
        user_id = self._user_id(user_ref)
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO conversation_relationship_state(user_id, conversation_ref, mode, state_json, updated_at)
                VALUES(?,?,?,?,?)
                ON CONFLICT(user_id, conversation_ref, mode) DO UPDATE SET
                  state_json=excluded.state_json,
                  updated_at=excluded.updated_at
                """,
                (user_id, conversation_ref.value, mode, json.dumps(state, ensure_ascii=False), self._now()),
            )
            conn.commit()
        finally:
            conn.close()

    def append_event(self, event: AnalyticsEvent) -> None:
        user_id = self._user_id(event.user_ref)
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO user_events(
                  ts,
                  user_id,
                  event_type,
                  mode,
                  ok,
                  note,
                  conversation_ref
                )
                VALUES(?,?,?,?,?,?,?)
                """,
                (
                    event.ts,
                    user_id,
                    event.event_type.value,
                    event.mode or "",
                    1 if event.ok else 0,
                    event.note or "",
                    event.conversation_ref.value if event.conversation_ref else None,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def reset_conversation(self, user_ref: UserRef, conversation_ref: ConversationRef) -> None:
        user_id = self._user_id(user_ref)
        now_ts = self._now()
        conn = self._connect()
        try:
            with conn:
                conn.execute(
                    """
                    UPDATE jobs
                    SET status=?, updated_at=?
                    WHERE user_id=? AND conversation_ref=? AND status NOT IN ('completed', 'failed', 'cancelled')
                    """,
                    (JobStatus.CANCELLED.value, now_ts, user_id, conversation_ref.value),
                )
                conn.execute(
                    "DELETE FROM user_messages WHERE user_id=? AND conversation_ref=?",
                    (user_id, conversation_ref.value),
                )
                conn.execute(
                    "DELETE FROM conversation_mode_state WHERE user_id=? AND conversation_ref=?",
                    (user_id, conversation_ref.value),
                )
                conn.execute(
                    "DELETE FROM conversation_mode_lock WHERE user_id=? AND conversation_ref=?",
                    (user_id, conversation_ref.value),
                )
                conn.execute(
                    "DELETE FROM conversation_photo_gate WHERE user_id=? AND conversation_ref=?",
                    (user_id, conversation_ref.value),
                )
                if self.include_relationship_state:
                    conn.execute(
                        "DELETE FROM conversation_relationship_state WHERE user_id=? AND conversation_ref=?",
                        (user_id, conversation_ref.value),
                    )
                conn.execute(
                    """
                    UPDATE conversations
                    SET active_mode='basic', updated_at=?
                    WHERE user_id=? AND conversation_ref=?
                    """,
                    (now_ts, user_id, conversation_ref.value),
                )
                conn.execute("UPDATE user_profile SET mode='basic' WHERE user_id=?", (user_id,))
        finally:
            conn.close()

    def reset_mode_in_conversation(self, user_ref: UserRef, conversation_ref: ConversationRef, mode: str) -> None:
        user_id = self._user_id(user_ref)
        now_ts = self._now()
        conn = self._connect()
        try:
            with conn:
                conn.execute(
                    """
                    UPDATE jobs
                    SET status=?, updated_at=?
                    WHERE user_id=? AND conversation_ref=? AND mode=? AND status NOT IN ('completed', 'failed', 'cancelled')
                    """,
                    (JobStatus.CANCELLED.value, now_ts, user_id, conversation_ref.value, mode),
                )
                conn.execute(
                    """
                    DELETE FROM conversation_mode_state
                    WHERE user_id=? AND conversation_ref=? AND mode=?
                    """,
                    (user_id, conversation_ref.value, mode),
                )
                conn.execute(
                    """
                    DELETE FROM user_messages
                    WHERE user_id=? AND conversation_ref=? AND mode=?
                    """,
                    (user_id, conversation_ref.value, mode),
                )
                conn.execute(
                    """
                    DELETE FROM conversation_mode_lock
                    WHERE user_id=? AND conversation_ref=? AND mode=?
                    """,
                    (user_id, conversation_ref.value, mode),
                )
                if self.include_relationship_state:
                    conn.execute(
                        """
                        DELETE FROM conversation_relationship_state
                        WHERE user_id=? AND conversation_ref=? AND mode=?
                        """,
                        (user_id, conversation_ref.value, mode),
                    )
                row = conn.execute(
                    """
                    SELECT active_mode
                    FROM conversations
                    WHERE user_id=? AND conversation_ref=?
                    """,
                    (user_id, conversation_ref.value),
                ).fetchone()
                current_mode = str(row[0] or "basic") if row else "basic"
                if current_mode == mode:
                    conn.execute(
                        """
                        UPDATE conversations
                        SET active_mode='basic', updated_at=?
                        WHERE user_id=? AND conversation_ref=?
                        """,
                        (now_ts, user_id, conversation_ref.value),
                    )
                    conn.execute("UPDATE user_profile SET mode='basic' WHERE user_id=?", (user_id,))
        finally:
            conn.close()

    def reset_user_all(self, user_ref: UserRef) -> None:
        user_id = self._user_id(user_ref)
        now_ts = self._now()
        conn = self._connect()
        try:
            with conn:
                conn.execute(
                    """
                    UPDATE jobs
                    SET status=?, updated_at=?
                    WHERE user_id=? AND status NOT IN ('completed', 'failed', 'cancelled')
                    """,
                    (JobStatus.CANCELLED.value, now_ts, user_id),
                )
                conn.execute("DELETE FROM user_messages WHERE user_id=?", (user_id,))
                conn.execute("DELETE FROM conversation_mode_state WHERE user_id=?", (user_id,))
                conn.execute("DELETE FROM conversation_mode_lock WHERE user_id=?", (user_id,))
                conn.execute("DELETE FROM conversation_photo_gate WHERE user_id=?", (user_id,))
                if self.include_relationship_state:
                    conn.execute("DELETE FROM conversation_relationship_state WHERE user_id=?", (user_id,))
                conn.execute(
                    """
                    UPDATE conversations
                    SET active_mode='basic', updated_at=?
                    WHERE user_id=?
                    """,
                    (now_ts, user_id),
                )
                conn.execute(
                    """
                    UPDATE user_profile
                    SET mode='basic', mode_picked=0, chat_locked=0, lock_reason=''
                    WHERE user_id=?
                    """,
                    (user_id,),
                )
        finally:
            conn.close()
