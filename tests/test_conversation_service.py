from __future__ import annotations

from src.core.conversation_service import ConversationService, ModeSwitchAuditContext


class FakeRepositories:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple]] = []
        self.states: dict[tuple[str, str], dict] = {}

    def set_active_mode(self, user_ref, conversation_ref, mode: str) -> None:
        self.calls.append(("set_active_mode", (user_ref, conversation_ref, mode)))

    def set_mode_picked(self, user_ref, picked: bool) -> None:
        self.calls.append(("set_mode_picked", (user_ref, picked)))

    def load_mode_state(self, user_ref, conversation_ref, mode: str):
        self.calls.append(("load_mode_state", (user_ref, conversation_ref, mode)))
        return self.states.get((str(user_ref), mode))

    def save_mode_state(self, user_ref, conversation_ref, mode: str, state: dict) -> None:
        self.calls.append(("save_mode_state", (user_ref, conversation_ref, mode, state)))
        self.states[(str(user_ref), mode)] = dict(state)


def test_conversation_service_switches_mode_and_logs_transition() -> None:
    repo = FakeRepositories()
    logs: list[dict] = []
    service = ConversationService(
        repositories=repo,
        user_ref_factory=lambda user_id: f"user:{user_id}",
        repo_refs=lambda user_id: (f"user:{user_id}", f"conv:{user_id}"),
        log_user_event=lambda **kwargs: logs.append(kwargs),
        default_mode_state=lambda mode: {"genre": mode},
    )

    service.switch_mode(
        5,
        "chef",
        prev_mode="basic",
        audit=ModeSwitchAuditContext(chat_id=10, username="u", first_name="f", message_id=11),
    )

    assert repo.calls[:2] == [
        ("set_active_mode", ("user:5", "conv:5", "chef")),
        ("set_mode_picked", ("user:5", True)),
    ]
    assert logs[-1]["event_type"] == "switch_mode"
    assert logs[-1]["mode_from"] == "basic"
    assert logs[-1]["mode_to"] == "chef"


def test_conversation_service_sets_submodes_in_mode_state() -> None:
    repo = FakeRepositories()
    service = ConversationService(
        repositories=repo,
        user_ref_factory=lambda user_id: f"user:{user_id}",
        repo_refs=lambda user_id: (f"user:{user_id}", f"conv:{user_id}"),
        log_user_event=lambda **kwargs: None,
        default_mode_state=lambda mode: {"genre": mode},
    )

    chef_state = service.set_chef_submode(7, "restaurant")
    rap_state = service.ensure_rap_submode(7, "story")
    updated_rap_state = service.set_rap_submode(7, "street")

    assert chef_state["chef_submode"] == "restaurant"
    assert rap_state["rap_submode"] == "story"
    assert updated_rap_state["rap_submode"] == "street"
