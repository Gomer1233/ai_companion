from __future__ import annotations

from src.db.connection import connect_postgres
from src.db.repositories import SQLiteRepositories
from src.core.contracts import ConversationRecord, ConversationRef, SessionRecord, UserRef


class PostgresRepositories(SQLiteRepositories):
    def __init__(
        self,
        database_url: str,
        *,
        include_relationship_state: bool = False,
        history_limit: int = 12,
    ) -> None:
        super().__init__(
            db_path="",
            include_relationship_state=include_relationship_state,
            history_limit=history_limit,
        )
        self.database_url = database_url

    def _connect(self):
        return connect_postgres(self.database_url)

    def _ensure_user(self, user_ref: UserRef) -> None:
        user_id = self._user_id(user_ref)
        now_ts = self._now()
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO users(user_id, created_at, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                  updated_at=excluded.updated_at
                """,
                (user_id, now_ts, now_ts),
            )
            conn.execute(
                """
                INSERT INTO telegram_accounts(telegram_user_id, user_id, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(telegram_user_id) DO UPDATE SET
                  user_id=excluded.user_id,
                  updated_at=excluded.updated_at
                """,
                (user_id, user_id, now_ts, now_ts),
            )
            conn.commit()
        finally:
            conn.close()

    def ensure_default_conversation(self, user_ref: UserRef, *, active_mode: str = "basic") -> ConversationRecord:
        self._ensure_user(user_ref)
        return super().ensure_default_conversation(user_ref, active_mode=active_mode)

    def create_conversation(
        self,
        user_ref: UserRef,
        *,
        active_mode: str = "basic",
        is_default: bool = False,
        conversation_ref: ConversationRef | None = None,
    ) -> ConversationRecord:
        self._ensure_user(user_ref)
        return super().create_conversation(
            user_ref,
            active_mode=active_mode,
            is_default=is_default,
            conversation_ref=conversation_ref,
        )

    def create_session(
        self,
        user_ref: UserRef,
        *,
        issued_at: int,
        expires_at: int,
        session_token: str | None = None,
    ) -> SessionRecord:
        self._ensure_user(user_ref)
        return super().create_session(
            user_ref,
            issued_at=issued_at,
            expires_at=expires_at,
            session_token=session_token,
        )
