from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ResetAuditContext:
    chat_id: int
    username: str
    first_name: str
    message_id: int
    text_len: int


class ResetService:
    def __init__(
        self,
        *,
        repositories: Any,
        user_ref_factory: Callable[[int], Any],
        repo_refs: Callable[[int], tuple[Any, Any]],
        log_user_event: Callable[..., Any],
        reset_relationship_state: Callable[[str, int, str], None],
        db_path: str,
    ) -> None:
        self._repositories = repositories
        self._user_ref_factory = user_ref_factory
        self._repo_refs = repo_refs
        self._log_user_event = log_user_event
        self._reset_relationship_state = reset_relationship_state
        self._db_path = db_path

    def reset_current_mode(self, user_id: int, mode: str, *, note: str, audit: ResetAuditContext) -> str:
        now_ts = int(time.time())
        self._log_user_event(
            ts=now_ts,
            user_id=user_id,
            chat_id=audit.chat_id,
            username=audit.username,
            first_name=audit.first_name,
            event_type="reset",
            mode=mode,
            message_id=audit.message_id,
            text_len=audit.text_len,
            ok=1,
            note=note,
        )

        user_ref, conversation_ref = self._repo_refs(user_id)
        self._repositories.reset_mode_in_conversation(user_ref, conversation_ref, mode)
        if mode == "whore":
            self._reset_relationship_state(self._db_path, user_id, mode)
        return mode

    def reset_user_all(self, user_id: int, *, prev_mode: str, audit: ResetAuditContext) -> None:
        self._log_user_event(
            ts=int(time.time()),
            user_id=user_id,
            chat_id=audit.chat_id,
            username=audit.username,
            first_name=audit.first_name,
            event_type="reset",
            mode="basic",
            mode_from=prev_mode,
            mode_to="basic",
            message_id=audit.message_id,
            text_len=audit.text_len,
            ok=1,
            note="scope=all",
        )

        user_ref = self._user_ref_factory(user_id)
        self._repositories.reset_user_all(user_ref)
        self._reset_relationship_state(self._db_path, user_id, "whore")
