from __future__ import annotations

from src.core.reset_service import ResetAuditContext, ResetService


class FakeRepositories:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple]] = []

    def reset_mode_in_conversation(self, user_ref, conversation_ref, mode: str) -> None:
        self.calls.append(("reset_mode_in_conversation", (user_ref, conversation_ref, mode)))

    def reset_user_all(self, user_ref) -> None:
        self.calls.append(("reset_user_all", (user_ref,)))


def test_reset_service_resets_current_mode_and_whore_relationship() -> None:
    repo = FakeRepositories()
    logs: list[dict] = []
    resets: list[tuple[str, int, str]] = []

    service = ResetService(
        repositories=repo,
        user_ref_factory=lambda user_id: f"user:{user_id}",
        repo_refs=lambda user_id: (f"user:{user_id}", f"conv:{user_id}"),
        log_user_event=lambda **kwargs: logs.append(kwargs),
        reset_relationship_state=lambda db_path, user_id, mode: resets.append((db_path, user_id, mode)),
        db_path="db.sqlite",
    )

    mode = service.reset_current_mode(
        5,
        "whore",
        note="scope=mode",
        audit=ResetAuditContext(chat_id=10, username="u", first_name="f", message_id=11, text_len=12),
    )

    assert mode == "whore"
    assert repo.calls == [("reset_mode_in_conversation", ("user:5", "conv:5", "whore"))]
    assert logs[-1]["note"] == "scope=mode"
    assert resets == [("db.sqlite", 5, "whore")]


def test_reset_service_resets_user_all_and_logs_transition() -> None:
    repo = FakeRepositories()
    logs: list[dict] = []
    resets: list[tuple[str, int, str]] = []

    service = ResetService(
        repositories=repo,
        user_ref_factory=lambda user_id: f"user:{user_id}",
        repo_refs=lambda user_id: (f"user:{user_id}", f"conv:{user_id}"),
        log_user_event=lambda **kwargs: logs.append(kwargs),
        reset_relationship_state=lambda db_path, user_id, mode: resets.append((db_path, user_id, mode)),
        db_path="db.sqlite",
    )

    service.reset_user_all(
        8,
        prev_mode="chef",
        audit=ResetAuditContext(chat_id=20, username="u2", first_name="f2", message_id=21, text_len=22),
    )

    assert repo.calls == [("reset_user_all", ("user:8",))]
    assert logs[-1]["mode_from"] == "chef"
    assert logs[-1]["mode_to"] == "basic"
    assert resets == [("db.sqlite", 8, "whore")]
