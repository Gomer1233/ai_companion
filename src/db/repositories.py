from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from typing import Any

from src.core.monetization import (
    AlphaProductCatalog,
    Entitlement,
    ExplicitConsent,
    PaymentOrder,
    PaymentProvider,
    PaymentStatus,
    ProductId,
    Tier,
    UsageCounter,
)
from src.core.contracts import (
    AnalyticsEvent,
    ConversationRecord,
    ConversationRef,
    ConversationStatus,
    DeferredJob,
    JobStatus,
    JobType,
    SessionRecord,
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

    def create_session(
        self,
        user_ref: UserRef,
        *,
        issued_at: int,
        expires_at: int,
        session_token: str | None = None,
    ) -> SessionRecord:
        user_id = self._user_id(user_ref)
        resolved_token = session_token or uuid.uuid4().hex
        record = SessionRecord(
            session_token=resolved_token,
            user_ref=user_ref,
            issued_at=issued_at,
            expires_at=expires_at,
            last_seen_at=issued_at,
        )
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO sessions(session_token, user_id, issued_at, expires_at, last_seen_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    record.session_token,
                    user_id,
                    record.issued_at,
                    record.expires_at,
                    record.last_seen_at,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return record

    def load_session(self, session_token: str) -> SessionRecord | None:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT session_token, user_id, issued_at, expires_at, last_seen_at
                FROM sessions
                WHERE session_token=?
                """,
                (session_token,),
            ).fetchone()
        finally:
            conn.close()
        if not row:
            return None
        return SessionRecord(
            session_token=str(row[0]),
            user_ref=legacy_user_ref(int(row[1])),
            issued_at=int(row[2]),
            expires_at=int(row[3]),
            last_seen_at=int(row[4]),
        )

    def touch_session(self, session_token: str, *, last_seen_at: int | None = None) -> SessionRecord | None:
        current = self.load_session(session_token)
        if current is None:
            return None
        resolved_last_seen = current.last_seen_at if last_seen_at is None else last_seen_at
        conn = self._connect()
        try:
            conn.execute(
                """
                UPDATE sessions
                SET last_seen_at=?
                WHERE session_token=?
                """,
                (resolved_last_seen, session_token),
            )
            conn.commit()
        finally:
            conn.close()
        return SessionRecord(
            session_token=current.session_token,
            user_ref=current.user_ref,
            issued_at=current.issued_at,
            expires_at=current.expires_at,
            last_seen_at=resolved_last_seen,
        )

    def delete_session(self, session_token: str) -> None:
        conn = self._connect()
        try:
            conn.execute("DELETE FROM sessions WHERE session_token=?", (session_token,))
            conn.commit()
        finally:
            conn.close()

    def delete_expired_sessions(self, *, now_ts: int | None = None) -> int:
        resolved_now = self._now() if now_ts is None else now_ts
        conn = self._connect()
        try:
            cursor = conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (resolved_now,))
            conn.commit()
            return int(cursor.rowcount or 0)
        finally:
            conn.close()

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

    def reconcile_stale_jobs(self, *, now_ts: int, stale_before_ts: int, error_code: str) -> int:
        conn = self._connect()
        try:
            cursor = conn.execute(
                """
                UPDATE jobs
                SET status=?, error_code=?, updated_at=?
                WHERE status IN ('queued', 'running') AND updated_at <= ?
                """,
                (JobStatus.FAILED.value, error_code, now_ts, stale_before_ts),
            )
            conn.commit()
            return int(cursor.rowcount or 0)
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

    def _ensure_storage_user(self, user_ref: UserRef) -> None:
        ensure_user = getattr(self, "_ensure_user", None)
        if ensure_user is not None:
            ensure_user(user_ref)

    def upsert_entitlement(
        self,
        *,
        entitlement_id: str,
        user_ref: UserRef,
        plan_id: str,
        tier: Tier | str,
        starts_at: int,
        expires_at: int | None,
        source: str,
        created_at: int,
        status: str = "active",
        revoked_at: int | None = None,
        revoked_by: str | None = None,
        revoked_reason: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> Entitlement:
        self._ensure_storage_user(user_ref)
        user_id = self._user_id(user_ref)
        resolved_tier = Tier(tier)
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True)
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO entitlements(
                  entitlement_id, user_id, plan_id, tier, starts_at, expires_at, status, source, created_at,
                  revoked_at, revoked_by, revoked_reason, metadata_json
                )
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(entitlement_id) DO UPDATE SET
                  plan_id=excluded.plan_id,
                  tier=excluded.tier,
                  starts_at=excluded.starts_at,
                  expires_at=excluded.expires_at,
                  status=excluded.status,
                  source=excluded.source,
                  revoked_at=excluded.revoked_at,
                  revoked_by=excluded.revoked_by,
                  revoked_reason=excluded.revoked_reason,
                  metadata_json=excluded.metadata_json
                """,
                (
                    entitlement_id,
                    user_id,
                    plan_id,
                    resolved_tier.value,
                    int(starts_at),
                    expires_at,
                    status,
                    source,
                    int(created_at),
                    revoked_at,
                    revoked_by,
                    revoked_reason,
                    metadata_json,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return Entitlement(
            entitlement_id=entitlement_id,
            user_ref=user_ref,
            plan_id=plan_id,
            tier=resolved_tier,
            starts_at=int(starts_at),
            expires_at=expires_at,
            status=status,
            source=source,
            created_at=int(created_at),
            revoked_at=revoked_at,
            revoked_by=revoked_by,
            revoked_reason=revoked_reason,
            metadata=metadata or {},
        )

    def load_active_entitlements(self, user_ref: UserRef, now_ts: int) -> list[Entitlement]:
        user_id = self._user_id(user_ref)
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT entitlement_id, user_id, plan_id, tier, starts_at, expires_at, status, source, created_at,
                       revoked_at, revoked_by, revoked_reason, metadata_json
                FROM entitlements
                WHERE user_id=?
                  AND starts_at <= ?
                  AND (expires_at IS NULL OR expires_at > ?)
                  AND status='active'
                  AND revoked_at IS NULL
                ORDER BY starts_at DESC, created_at DESC
                """,
                (user_id, int(now_ts), int(now_ts)),
            ).fetchall()
        finally:
            conn.close()
        return [self._entitlement_from_row(row) for row in rows]

    def count_fulfilled_product(self, product_id: ProductId | str) -> int:
        resolved_product = ProductId(product_id)
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT COUNT(*)
                FROM payment_orders
                WHERE product_id=? AND status=?
                """,
                (resolved_product.value, PaymentStatus.FULFILLED.value),
            ).fetchone()
        finally:
            conn.close()
        return int(row[0] if row else 0)

    def increment_usage(
        self,
        user_ref: UserRef,
        counter_key: str,
        *,
        window_start: int,
        window_end: int,
        amount: int = 1,
    ) -> int:
        self._ensure_storage_user(user_ref)
        user_id = self._user_id(user_ref)
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO usage_counters(user_id, counter_key, window_start, window_end, value)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(user_id, counter_key, window_start) DO UPDATE SET
                  window_end=excluded.window_end,
                  value=usage_counters.value + excluded.value
                """,
                (user_id, counter_key, int(window_start), int(window_end), int(amount)),
            )
            row = conn.execute(
                """
                SELECT value FROM usage_counters
                WHERE user_id=? AND counter_key=? AND window_start=?
                """,
                (user_id, counter_key, int(window_start)),
            ).fetchone()
            conn.commit()
        finally:
            conn.close()
        return int(row[0])

    def load_usage(self, user_ref: UserRef, counter_key: str, *, window_start: int) -> UsageCounter:
        user_id = self._user_id(user_ref)
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT user_id, counter_key, window_start, window_end, value
                FROM usage_counters
                WHERE user_id=? AND counter_key=? AND window_start=?
                """,
                (user_id, counter_key, int(window_start)),
            ).fetchone()
        finally:
            conn.close()
        if not row:
            return UsageCounter(user_ref=user_ref, counter_key=counter_key, window_start=window_start, window_end=window_start, value=0)
        return UsageCounter(
            user_ref=legacy_user_ref(int(row[0])),
            counter_key=str(row[1]),
            window_start=int(row[2]),
            window_end=int(row[3]),
            value=int(row[4]),
        )

    def set_explicit_consent(self, user_ref: UserRef, *, accepted_at: int, source: str) -> ExplicitConsent:
        self._ensure_storage_user(user_ref)
        user_id = self._user_id(user_ref)
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO explicit_consent(user_id, accepted_at, revoked_at, source)
                VALUES(?, ?, NULL, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                  accepted_at=excluded.accepted_at,
                  revoked_at=NULL,
                  source=excluded.source
                """,
                (user_id, int(accepted_at), source),
            )
            conn.commit()
        finally:
            conn.close()
        return ExplicitConsent(user_ref=user_ref, accepted_at=int(accepted_at), revoked_at=None, source=source)

    def revoke_explicit_consent(
        self,
        user_ref: UserRef,
        *,
        revoked_at: int,
        source: str,
    ) -> ExplicitConsent | None:
        user_id = self._user_id(user_ref)
        existing = self.load_explicit_consent(user_ref)
        if existing is None or existing.revoked_at is not None:
            return existing
        conn = self._connect()
        try:
            conn.execute(
                """
                UPDATE explicit_consent
                SET revoked_at=?, source=?
                WHERE user_id=? AND revoked_at IS NULL
                """,
                (int(revoked_at), source, user_id),
            )
            conn.commit()
        finally:
            conn.close()
        return self.load_explicit_consent(user_ref)

    def load_explicit_consent(self, user_ref: UserRef) -> ExplicitConsent | None:
        user_id = self._user_id(user_ref)
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT user_id, accepted_at, revoked_at, source FROM explicit_consent WHERE user_id=?",
                (user_id,),
            ).fetchone()
        finally:
            conn.close()
        if not row:
            return None
        return ExplicitConsent(
            user_ref=legacy_user_ref(int(row[0])),
            accepted_at=int(row[1]),
            revoked_at=None if row[2] is None else int(row[2]),
            source=str(row[3]),
        )

    def create_payment_order(self, order: PaymentOrder) -> PaymentOrder:
        self._ensure_storage_user(order.user_ref)
        user_id = self._user_id(order.user_ref)
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO payment_orders(
                  order_id, user_id, provider, product_id, amount_minor, currency, status, entitlement_id,
                  provider_payment_id, provider_payload_json, created_at, paid_at, fulfilled_at, refunded_at,
                  cancelled_at, error_code
                )
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    order.order_id,
                    user_id,
                    order.provider.value,
                    order.product_id.value,
                    order.amount_minor,
                    order.currency,
                    order.status.value,
                    order.entitlement_id,
                    order.provider_payment_id,
                    order.provider_payload_json or "{}",
                    order.created_at,
                    order.paid_at,
                    order.fulfilled_at,
                    order.refunded_at,
                    order.cancelled_at,
                    order.error_code,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return order

    def load_payment_order(self, order_id: str) -> PaymentOrder | None:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT order_id, user_id, provider, product_id, amount_minor, currency, status, entitlement_id,
                       provider_payment_id, provider_payload_json, created_at, paid_at, fulfilled_at, refunded_at,
                       cancelled_at, error_code
                FROM payment_orders
                WHERE order_id=?
                """,
                (order_id,),
            ).fetchone()
        finally:
            conn.close()
        if not row:
            return None
        return self._payment_order_from_row(row)

    def list_paid_unfulfilled_orders(self) -> list[PaymentOrder]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT order_id, user_id, provider, product_id, amount_minor, currency, status, entitlement_id,
                       provider_payment_id, provider_payload_json, created_at, paid_at, fulfilled_at, refunded_at,
                       cancelled_at, error_code
                FROM payment_orders
                WHERE status=? AND entitlement_id IS NULL
                ORDER BY paid_at ASC, created_at ASC
                """,
                (PaymentStatus.PAID.value,),
            ).fetchall()
        finally:
            conn.close()
        return [self._payment_order_from_row(row) for row in rows]

    def mark_payment_order_paid(
        self,
        order_id: str,
        *,
        provider_payment_id: str,
        provider_payload_json: str,
        paid_at: int,
    ) -> PaymentOrder:
        conn = self._connect()
        try:
            conn.execute(
                """
                UPDATE payment_orders
                SET status=?, provider_payment_id=?, provider_payload_json=?, paid_at=?
                WHERE order_id=? AND status IN (?, ?)
                """,
                (
                    PaymentStatus.PAID.value,
                    provider_payment_id,
                    provider_payload_json or "{}",
                    int(paid_at),
                    order_id,
                    PaymentStatus.PENDING.value,
                    PaymentStatus.PAID.value,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        order = self.load_payment_order(order_id)
        if order is None:
            raise ValueError("payment_order_not_found")
        return order

    def mark_payment_order_refunded(self, order_id: str, *, refunded_at: int) -> PaymentOrder:
        conn = self._connect()
        try:
            conn.execute(
                """
                UPDATE payment_orders
                SET status=?, refunded_at=?
                WHERE order_id=?
                """,
                (PaymentStatus.REFUNDED.value, int(refunded_at), order_id),
            )
            conn.commit()
        finally:
            conn.close()
        order = self.load_payment_order(order_id)
        if order is None:
            raise ValueError("payment_order_not_found")
        return order

    def mark_payment_order_cancelled(self, order_id: str, *, cancelled_at: int) -> PaymentOrder:
        conn = self._connect()
        try:
            conn.execute(
                """
                UPDATE payment_orders
                SET status=?, cancelled_at=?
                WHERE order_id=?
                """,
                (PaymentStatus.CANCELLED.value, int(cancelled_at), order_id),
            )
            conn.commit()
        finally:
            conn.close()
        order = self.load_payment_order(order_id)
        if order is None:
            raise ValueError("payment_order_not_found")
        return order

    def mark_payment_order_failed(self, order_id: str, *, error_code: str) -> PaymentOrder:
        conn = self._connect()
        try:
            conn.execute(
                """
                UPDATE payment_orders
                SET status=?, error_code=?
                WHERE order_id=?
                """,
                (PaymentStatus.FAILED.value, error_code, order_id),
            )
            conn.commit()
        finally:
            conn.close()
        order = self.load_payment_order(order_id)
        if order is None:
            raise ValueError("payment_order_not_found")
        return order

    def fulfill_paid_order_transactionally(self, order_id: str, *, now_ts: int) -> Entitlement:
        conn = self._connect()
        try:
            with conn:
                order_row = conn.execute(
                    """
                    SELECT order_id, user_id, provider, product_id, amount_minor, currency, status, entitlement_id,
                           provider_payment_id, provider_payload_json, created_at, paid_at, fulfilled_at, refunded_at,
                           cancelled_at, error_code
                    FROM payment_orders
                    WHERE order_id=?
                    """,
                    (order_id,),
                ).fetchone()
                if not order_row:
                    raise ValueError("payment_order_not_found")
                order = self._payment_order_from_row(order_row)
                source = f"payment:{order.provider.value}:{order.order_id}"

                existing_row = conn.execute(
                    """
                    SELECT entitlement_id, user_id, plan_id, tier, starts_at, expires_at, status, source, created_at,
                           revoked_at, revoked_by, revoked_reason, metadata_json
                    FROM entitlements
                    WHERE source=?
                    """,
                    (source,),
                ).fetchone()
                existing = self._entitlement_from_row(existing_row) if existing_row else None
                if order.status == PaymentStatus.FULFILLED:
                    if existing is not None:
                        return existing
                    if order.entitlement_id:
                        entitlement = self._load_entitlement_by_id_in_conn(conn, order.entitlement_id)
                        if entitlement is not None:
                            return entitlement
                    raise ValueError("fulfilled_order_missing_entitlement")
                if order.status != PaymentStatus.PAID:
                    raise ValueError("payment_order_not_paid")

                if existing is None:
                    if order.product_id == ProductId.LIFETIME_PREMIUM_100:
                        count_row = conn.execute(
                            """
                            SELECT
                              (
                                SELECT COUNT(*)
                                FROM entitlements
                                WHERE plan_id=? AND status='active' AND revoked_at IS NULL
                              ) + (
                                SELECT COUNT(*)
                                FROM payment_orders orders
                                WHERE orders.product_id=? AND orders.status=?
                                  AND NOT EXISTS (
                                    SELECT 1
                                    FROM entitlements ent
                                    WHERE ent.entitlement_id=orders.entitlement_id
                                      AND ent.plan_id=orders.product_id
                                      AND ent.status='active'
                                      AND ent.revoked_at IS NULL
                                  )
                              )
                            """,
                            (
                                ProductId.LIFETIME_PREMIUM_100.value,
                                ProductId.LIFETIME_PREMIUM_100.value,
                                PaymentStatus.FULFILLED.value,
                            ),
                        ).fetchone()
                        if int(count_row[0] if count_row else 0) >= 100:
                            raise ValueError("lifetime_cap_reached")
                    product = AlphaProductCatalog.default().get(order.product_id)
                    entitlement_id = uuid.uuid4().hex
                    expires_at = None
                    if product.duration_days is not None:
                        expires_at = int(now_ts) + product.duration_days * 86_400
                    conn.execute(
                        """
                        INSERT INTO entitlements(
                          entitlement_id, user_id, plan_id, tier, starts_at, expires_at, status, source, created_at,
                          revoked_at, revoked_by, revoked_reason, metadata_json
                        )
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            entitlement_id,
                            self._user_id(order.user_ref),
                            order.product_id.value,
                            product.tier.value,
                            int(now_ts),
                            expires_at,
                            "active",
                            source,
                            int(now_ts),
                            None,
                            None,
                            None,
                            "{}",
                        ),
                    )
                    existing = self._load_entitlement_by_id_in_conn(conn, entitlement_id)
                    if existing is None:
                        raise ValueError("created_entitlement_not_found")

                conn.execute(
                    """
                    UPDATE payment_orders
                    SET status=?, entitlement_id=?, fulfilled_at=?
                    WHERE order_id=?
                    """,
                    (PaymentStatus.FULFILLED.value, existing.entitlement_id, int(now_ts), order_id),
                )
                return existing
        finally:
            conn.close()

    def revoke_entitlements(
        self,
        user_ref: UserRef,
        *,
        revoked_by: str,
        revoked_at: int,
        reason: str,
        source_filter: str | None = None,
    ) -> int:
        user_id = self._user_id(user_ref)
        params: list[Any] = ["revoked", int(revoked_at), revoked_by, reason, user_id]
        source_sql = ""
        if source_filter is not None:
            source_sql = " AND source=?"
            params.append(source_filter)
        conn = self._connect()
        try:
            cursor = conn.execute(
                f"""
                UPDATE entitlements
                SET status=?, revoked_at=?, revoked_by=?, revoked_reason=?
                WHERE user_id=? AND status='active' AND revoked_at IS NULL{source_sql}
                """,
                tuple(params),
            )
            conn.commit()
            return int(cursor.rowcount or 0)
        finally:
            conn.close()

    def append_admin_audit_event(
        self,
        *,
        audit_id: str,
        operator_user_id: str,
        action: str,
        result: str,
        created_at: int,
        target_user_id: int | None = None,
        target_order_id: str | None = None,
        reason: str = "",
        metadata: dict[str, object] | None = None,
    ) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO admin_audit_events(
                  audit_id, operator_user_id, target_user_id, target_order_id, action, result, reason, created_at, metadata_json
                )
                VALUES(?,?,?,?,?,?,?,?,?)
                """,
                (
                    audit_id,
                    operator_user_id,
                    target_user_id,
                    target_order_id,
                    action,
                    result,
                    reason,
                    int(created_at),
                    json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def count_admin_audit_events(self, *, action: str, target_user_id: int | None = None) -> int:
        params: list[Any] = [action]
        target_sql = ""
        if target_user_id is not None:
            target_sql = " AND target_user_id=?"
            params.append(target_user_id)
        conn = self._connect()
        try:
            row = conn.execute(
                f"SELECT COUNT(*) FROM admin_audit_events WHERE action=?{target_sql}",
                tuple(params),
            ).fetchone()
        finally:
            conn.close()
        return int(row[0] if row else 0)

    def load_manual_lifetime_entitlement_count(self) -> int:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT
                  (
                    SELECT COUNT(*)
                    FROM entitlements
                    WHERE plan_id=? AND status='active' AND revoked_at IS NULL
                  ) + (
                    SELECT COUNT(*)
                    FROM payment_orders orders
                    WHERE orders.product_id=? AND orders.status=?
                      AND NOT EXISTS (
                        SELECT 1
                        FROM entitlements ent
                        WHERE ent.entitlement_id=orders.entitlement_id
                          AND ent.plan_id=orders.product_id
                          AND ent.status='active'
                          AND ent.revoked_at IS NULL
                      )
                  )
                """,
                (
                    ProductId.LIFETIME_PREMIUM_100.value,
                    ProductId.LIFETIME_PREMIUM_100.value,
                    PaymentStatus.FULFILLED.value,
                ),
            ).fetchone()
        finally:
            conn.close()
        return int(row[0] if row else 0)

    def list_admin_user_identities(self, *, q: str | None = None) -> list[dict[str, Any]]:
        query = (q or "").strip().lower()
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                WITH known_users AS (
                  SELECT user_id FROM user_profile
                  UNION
                  SELECT user_id FROM user_events
                  UNION
                  SELECT user_id FROM entitlements
                  UNION
                  SELECT user_id FROM payment_orders
                  UNION
                  SELECT user_id FROM usage_counters
                )
                SELECT
                  known_users.user_id,
                  COALESCE(
                    NULLIF((
                      SELECT first_name
                      FROM user_events latest_name
                      WHERE latest_name.user_id = known_users.user_id AND latest_name.first_name <> ''
                      ORDER BY latest_name.ts DESC, latest_name.id DESC
                      LIMIT 1
                    ), ''),
                    NULLIF(profile.preferred_name, ''),
                    ''
                  ) AS name,
                  COALESCE(
                    NULLIF((
                      SELECT username
                      FROM user_events latest_username
                      WHERE latest_username.user_id = known_users.user_id AND latest_username.username <> ''
                      ORDER BY latest_username.ts DESC, latest_username.id DESC
                      LIMIT 1
                    ), ''),
                    ''
                  ) AS username,
                  (
                    SELECT MAX(ts)
                    FROM user_events latest_event
                    WHERE latest_event.user_id = known_users.user_id
                  ) AS last_active_at
                FROM known_users
                LEFT JOIN user_profile profile ON profile.user_id = known_users.user_id
                ORDER BY known_users.user_id ASC
                """
            ).fetchall()
        finally:
            conn.close()
        identities = [
            {
                "telegram_user_id": int(row[0]),
                "name": str(row[1] or ""),
                "username": str(row[2] or ""),
                "last_active_at": None if row[3] is None else int(row[3]),
            }
            for row in rows
        ]
        if not query:
            return identities
        filtered: list[dict[str, Any]] = []
        for identity in identities:
            name = str(identity.get("name") or "")
            username = str(identity.get("username") or "")
            if query in str(identity["telegram_user_id"]) or query in name.lower() or query in username.lower():
                filtered.append(identity)
        return filtered

    def load_latest_payment_status(self, user_ref: UserRef) -> str:
        user_id = self._user_id(user_ref)
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT status
                FROM payment_orders
                WHERE user_id=?
                ORDER BY COALESCE(fulfilled_at, paid_at, created_at) DESC, created_at DESC
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()
        finally:
            conn.close()
        return str(row[0]) if row else "none"

    def load_llm_token_totals(self, user_ref: UserRef) -> tuple[int, int]:
        user_id = self._user_id(user_ref)
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT COALESCE(SUM(prompt_tokens), 0), COALESCE(SUM(completion_tokens), 0)
                FROM user_events
                WHERE user_id=?
                """,
                (user_id,),
            ).fetchone()
        finally:
            conn.close()
        if not row:
            return 0, 0
        return int(row[0] or 0), int(row[1] or 0)

    def _load_entitlement_by_id_in_conn(self, conn: Any, entitlement_id: str) -> Entitlement | None:
        row = conn.execute(
            """
            SELECT entitlement_id, user_id, plan_id, tier, starts_at, expires_at, status, source, created_at,
                   revoked_at, revoked_by, revoked_reason, metadata_json
            FROM entitlements
            WHERE entitlement_id=?
            """,
            (entitlement_id,),
        ).fetchone()
        return self._entitlement_from_row(row) if row else None

    def _entitlement_from_row(self, row: Any) -> Entitlement:
        metadata_json = row[12] or "{}"
        metadata = json.loads(metadata_json)
        return Entitlement(
            entitlement_id=str(row[0]),
            user_ref=legacy_user_ref(int(row[1])),
            plan_id=str(row[2] or ""),
            tier=Tier(str(row[3])),
            starts_at=int(row[4]),
            expires_at=None if row[5] is None else int(row[5]),
            status=str(row[6]),
            source=str(row[7]),
            created_at=int(row[8]),
            revoked_at=None if row[9] is None else int(row[9]),
            revoked_by=None if row[10] is None else str(row[10]),
            revoked_reason=None if row[11] is None else str(row[11]),
            metadata=metadata if isinstance(metadata, dict) else {},
        )

    def _payment_order_from_row(self, row: Any) -> PaymentOrder:
        return PaymentOrder(
            order_id=str(row[0]),
            user_ref=legacy_user_ref(int(row[1])),
            provider=PaymentProvider(str(row[2])),
            product_id=ProductId(str(row[3])),
            amount_minor=int(row[4]),
            currency=str(row[5]),
            status=PaymentStatus(str(row[6])),
            entitlement_id=None if row[7] is None else str(row[7]),
            provider_payment_id=None if row[8] is None else str(row[8]),
            provider_payload_json=None if row[9] is None else str(row[9]),
            created_at=int(row[10]),
            paid_at=None if row[11] is None else int(row[11]),
            fulfilled_at=None if row[12] is None else int(row[12]),
            refunded_at=None if row[13] is None else int(row[13]),
            cancelled_at=None if row[14] is None else int(row[14]),
            error_code=None if row[15] is None else str(row[15]),
        )

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
