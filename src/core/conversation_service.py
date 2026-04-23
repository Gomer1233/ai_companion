from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class ModeSwitchAuditContext:
    chat_id: int
    username: str
    first_name: str
    message_id: int


class ConversationService:
    def __init__(
        self,
        *,
        repositories: Any,
        user_ref_factory: Callable[[int], Any],
        repo_refs: Callable[[int], tuple[Any, Any]],
        log_user_event: Callable[..., Any],
        default_mode_state: Callable[[str], dict[str, Any]],
    ) -> None:
        self._repositories = repositories
        self._user_ref_factory = user_ref_factory
        self._repo_refs = repo_refs
        self._log_user_event = log_user_event
        self._default_mode_state = default_mode_state

    def switch_mode(
        self,
        user_id: int,
        mode: str,
        *,
        prev_mode: str,
        audit: ModeSwitchAuditContext,
    ) -> None:
        user_ref, conversation_ref = self._repo_refs(user_id)
        self._repositories.set_active_mode(user_ref, conversation_ref, mode)
        self._repositories.set_mode_picked(self._user_ref_factory(user_id), True)
        self._log_user_event(
            ts=int(time.time()),
            user_id=user_id,
            chat_id=audit.chat_id,
            username=audit.username,
            first_name=audit.first_name,
            event_type="switch_mode",
            mode=mode,
            mode_from=prev_mode,
            mode_to=mode,
            message_id=audit.message_id,
            text_len=0,
            ok=1,
        )

    def load_mode_state(self, user_id: int, mode: str) -> dict[str, Any]:
        user_ref, conversation_ref = self._repo_refs(user_id)
        state = self._repositories.load_mode_state(user_ref, conversation_ref, mode)
        if isinstance(state, dict):
            return state
        state = self._default_mode_state(mode)
        self._repositories.save_mode_state(user_ref, conversation_ref, mode, state)
        return state

    def save_mode_state(self, user_id: int, mode: str, state: dict[str, Any]) -> None:
        user_ref, conversation_ref = self._repo_refs(user_id)
        self._repositories.save_mode_state(user_ref, conversation_ref, mode, state)

    def set_chef_submode(self, user_id: int, picked: str) -> dict[str, Any]:
        state = self.load_mode_state(user_id, "chef")
        state["chef_submode"] = picked
        self.save_mode_state(user_id, "chef", state)
        return state

    def ensure_rap_submode(self, user_id: int, default: str = "story") -> dict[str, Any]:
        state = self.load_mode_state(user_id, "oldschool_rep")
        submode = (state.get("rap_submode") or "").strip().lower()
        if not submode:
            state["rap_submode"] = default
            self.save_mode_state(user_id, "oldschool_rep", state)
        return state

    def set_rap_submode(self, user_id: int, picked: str) -> dict[str, Any]:
        state = self.load_mode_state(user_id, "oldschool_rep")
        state["rap_submode"] = picked
        self.save_mode_state(user_id, "oldschool_rep", state)
        return state
