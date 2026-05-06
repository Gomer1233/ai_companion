from __future__ import annotations

import sqlite3
import time

import pytest

from src.core.contracts import AnalyticsEvent, AnalyticsEventType, ConversationStatus, DeferredJob, JobStatus, JobType, UserRef
from src.core.chat_service import ensure_miniapp_conversation
from src.db.migrations import migrate_database
from src.db.repositories import SQLiteRepositories


def _make_repo(tmp_path, *, include_relationship_state: bool = True, history_limit: int = 3):
    db_path = tmp_path / "repo.db"
    migrate_database(str(db_path), include_relationship_state=include_relationship_state)
    return db_path, SQLiteRepositories(
        str(db_path),
        include_relationship_state=include_relationship_state,
        history_limit=history_limit,
    )


def test_repositories_isolate_conversations_and_active_mode(tmp_path) -> None:
    _, repo = _make_repo(tmp_path)
    user_ref = UserRef("101")

    default_conv = repo.ensure_default_conversation(user_ref, active_mode="basic")
    chef_conv = repo.create_conversation(user_ref, active_mode="chef")

    repo.append_history(user_ref, default_conv.conversation_ref, "basic", "user", "hello-basic")
    repo.append_history(user_ref, chef_conv.conversation_ref, "chef", "user", "hello-chef")
    repo.save_mode_state(user_ref, chef_conv.conversation_ref, "chef", {"recap": "busy"})
    repo.lock_mode(user_ref, chef_conv.conversation_ref, "chef", "GAME OVER")
    repo.upsert_photo_gate(user_ref, chef_conv.conversation_ref, {"awaiting_image_prompt": 1, "score": 3})
    repo.save_relationship_state(user_ref, chef_conv.conversation_ref, "whore", {"stage": "FLIRTING"})
    repo.set_active_mode(user_ref, chef_conv.conversation_ref, "oldschool_rep")
    repo.archive_conversation(user_ref, chef_conv.conversation_ref)

    assert repo.load_history(user_ref, default_conv.conversation_ref, "basic") == [{"role": "user", "content": "hello-basic"}]
    assert repo.load_history(user_ref, chef_conv.conversation_ref, "chef") == [{"role": "user", "content": "hello-chef"}]
    assert repo.load_mode_state(user_ref, chef_conv.conversation_ref, "chef") == {"recap": "busy"}
    assert repo.load_mode_state(user_ref, default_conv.conversation_ref, "chef") is None
    assert repo.is_mode_locked(user_ref, chef_conv.conversation_ref, "chef") == (True, "GAME OVER")
    assert repo.is_mode_locked(user_ref, default_conv.conversation_ref, "chef") == (False, "")
    assert repo.get_photo_gate(user_ref, chef_conv.conversation_ref)["awaiting_image_prompt"] == 1
    assert repo.get_photo_gate(user_ref, default_conv.conversation_ref)["awaiting_image_prompt"] == 0
    assert repo.load_relationship_state(user_ref, chef_conv.conversation_ref, "whore") == {"stage": "FLIRTING"}
    assert repo.get_active_mode(user_ref, chef_conv.conversation_ref) == "oldschool_rep"
    assert repo.load_conversation(user_ref, chef_conv.conversation_ref).status == ConversationStatus.ARCHIVED
    assert repo.load_active_conversation_for_user(user_ref).conversation_ref == default_conv.conversation_ref


def test_history_limit_applies_per_conversation_and_mode(tmp_path) -> None:
    _, repo = _make_repo(tmp_path, history_limit=2)
    user_ref = UserRef("102")
    conv = repo.ensure_default_conversation(user_ref)

    repo.append_history(user_ref, conv.conversation_ref, "basic", "user", "one")
    repo.append_history(user_ref, conv.conversation_ref, "basic", "assistant", "two")
    repo.append_history(user_ref, conv.conversation_ref, "basic", "user", "three")
    repo.append_history(user_ref, conv.conversation_ref, "chef", "user", "chef-only")

    assert repo.load_history(user_ref, conv.conversation_ref, "basic") == [
        {"role": "assistant", "content": "two"},
        {"role": "user", "content": "three"},
    ]
    assert repo.load_history(user_ref, conv.conversation_ref, "chef") == [{"role": "user", "content": "chef-only"}]


def test_miniapp_conversations_are_deterministic_and_isolated_by_mode(tmp_path) -> None:
    _, repo = _make_repo(tmp_path)
    user_ref = UserRef("601")

    basic = ensure_miniapp_conversation(repo, user_ref, "basic")
    brainstorm = ensure_miniapp_conversation(repo, user_ref, "brainstorm")
    same_basic = ensure_miniapp_conversation(repo, user_ref, "basic")

    assert same_basic.conversation_ref == basic.conversation_ref
    assert basic.conversation_ref.value == "miniapp:601:basic"
    assert brainstorm.conversation_ref.value == "miniapp:601:brainstorm"

    repo.append_history(user_ref, basic.conversation_ref, "basic", "user", "basic thread")
    repo.append_history(user_ref, brainstorm.conversation_ref, "brainstorm", "user", "brainstorm thread")

    assert repo.load_history(user_ref, basic.conversation_ref, "basic") == [
        {"role": "user", "content": "basic thread"}
    ]
    assert repo.load_history(user_ref, brainstorm.conversation_ref, "brainstorm") == [
        {"role": "user", "content": "brainstorm thread"}
    ]


def test_job_transitions_block_cancelled_to_completed_or_failed(tmp_path) -> None:
    _, repo = _make_repo(tmp_path)
    user_ref = UserRef("103")
    conv = repo.ensure_default_conversation(user_ref)
    now_ts = int(time.time())
    job = DeferredJob(
        job_id="job-1",
        user_ref=user_ref,
        conversation_ref=conv.conversation_ref,
        mode="basic",
        job_type=JobType.IMAGE,
        status=JobStatus.QUEUED,
        progress=0,
        created_at=now_ts,
        updated_at=now_ts,
    )

    repo.create_job(job)
    running = repo.update_job_status("job-1", JobStatus.RUNNING, progress=25)
    cancelled = repo.update_job_status("job-1", JobStatus.CANCELLED, progress=25, error_code="cancelled")

    assert running.status == JobStatus.RUNNING
    assert cancelled.status == JobStatus.CANCELLED
    assert repo.load_job("job-1").status == JobStatus.CANCELLED

    with pytest.raises(ValueError, match="Invalid job status transition"):
        repo.update_job_status("job-1", JobStatus.COMPLETED, result_ref="image.png")

    with pytest.raises(ValueError, match="Invalid job status transition"):
        repo.update_job_status("job-1", JobStatus.FAILED, error_code="late-failure")


def test_reconcile_stale_jobs_marks_non_terminal_jobs_failed(tmp_path) -> None:
    _, repo = _make_repo(tmp_path)
    user_ref = UserRef("109")
    conv = repo.ensure_default_conversation(user_ref)
    stale_ts = 10_000
    fresh_ts = 20_000

    for job_id, status, updated_at in (
        ("queued-stale", JobStatus.QUEUED, stale_ts),
        ("running-stale", JobStatus.RUNNING, stale_ts),
        ("running-fresh", JobStatus.RUNNING, fresh_ts),
        ("completed-stale", JobStatus.COMPLETED, stale_ts),
        ("cancelled-stale", JobStatus.CANCELLED, stale_ts),
    ):
        repo.create_job(
            DeferredJob(
                job_id=job_id,
                user_ref=user_ref,
                conversation_ref=conv.conversation_ref,
                mode="basic",
                job_type=JobType.IMAGE,
                status=status,
                progress=50,
                created_at=updated_at,
                updated_at=updated_at,
            )
        )

    reconciled = repo.reconcile_stale_jobs(
        now_ts=30_000,
        stale_before_ts=15_000,
        error_code="stale_on_startup",
    )

    assert reconciled == 2
    assert repo.load_job("queued-stale").status == JobStatus.FAILED
    assert repo.load_job("queued-stale").error_code == "stale_on_startup"
    assert repo.load_job("queued-stale").updated_at == 30_000
    assert repo.load_job("running-stale").status == JobStatus.FAILED
    assert repo.load_job("running-fresh").status == JobStatus.RUNNING
    assert repo.load_job("completed-stale").status == JobStatus.COMPLETED
    assert repo.load_job("cancelled-stale").status == JobStatus.CANCELLED


def test_reset_mode_in_conversation_clears_only_mode_bound_state(tmp_path) -> None:
    _, repo = _make_repo(tmp_path)
    user_ref = UserRef("104")
    conv = repo.ensure_default_conversation(user_ref, active_mode="chef")
    now_ts = int(time.time())

    repo.append_history(user_ref, conv.conversation_ref, "chef", "user", "drop-history")
    repo.save_mode_state(user_ref, conv.conversation_ref, "chef", {"recap": "remove me"})
    repo.lock_mode(user_ref, conv.conversation_ref, "chef", "GAME OVER")
    repo.upsert_photo_gate(user_ref, conv.conversation_ref, {"awaiting_image_prompt": 1})
    repo.save_relationship_state(user_ref, conv.conversation_ref, "chef", {"stage": "STRANGER"})
    repo.create_job(
        DeferredJob(
            job_id="job-mode",
            user_ref=user_ref,
            conversation_ref=conv.conversation_ref,
            mode="chef",
            job_type=JobType.IMAGE,
            status=JobStatus.RUNNING,
            progress=50,
            created_at=now_ts,
            updated_at=now_ts,
        )
    )

    repo.reset_mode_in_conversation(user_ref, conv.conversation_ref, "chef")

    assert repo.load_history(user_ref, conv.conversation_ref, "chef") == []
    assert repo.load_mode_state(user_ref, conv.conversation_ref, "chef") is None
    assert repo.is_mode_locked(user_ref, conv.conversation_ref, "chef") == (False, "")
    assert repo.get_photo_gate(user_ref, conv.conversation_ref)["awaiting_image_prompt"] == 1
    assert repo.load_relationship_state(user_ref, conv.conversation_ref, "chef") is None
    assert repo.load_job("job-mode").status == JobStatus.CANCELLED
    assert repo.get_active_mode(user_ref, conv.conversation_ref) == "basic"


def test_reset_conversation_clears_conversation_state_and_cancels_jobs(tmp_path) -> None:
    _, repo = _make_repo(tmp_path)
    user_ref = UserRef("105")
    default_conv = repo.ensure_default_conversation(user_ref, active_mode="basic")
    extra_conv = repo.create_conversation(user_ref, active_mode="whore")
    now_ts = int(time.time())

    repo.append_history(user_ref, extra_conv.conversation_ref, "whore", "user", "conversation-only")
    repo.append_history(user_ref, default_conv.conversation_ref, "basic", "user", "keep-default")
    repo.save_mode_state(user_ref, extra_conv.conversation_ref, "whore", {"stage": 1})
    repo.lock_mode(user_ref, extra_conv.conversation_ref, "whore", "stop")
    repo.upsert_photo_gate(user_ref, extra_conv.conversation_ref, {"awaiting_context": 1})
    repo.save_relationship_state(user_ref, extra_conv.conversation_ref, "whore", {"stage": "DATING"})
    repo.create_job(
        DeferredJob(
            job_id="job-conv",
            user_ref=user_ref,
            conversation_ref=extra_conv.conversation_ref,
            mode="whore",
            job_type=JobType.AUDIO,
            status=JobStatus.RUNNING,
            progress=80,
            created_at=now_ts,
            updated_at=now_ts,
        )
    )

    repo.reset_conversation(user_ref, extra_conv.conversation_ref)

    assert repo.load_history(user_ref, extra_conv.conversation_ref, "whore") == []
    assert repo.load_mode_state(user_ref, extra_conv.conversation_ref, "whore") is None
    assert repo.is_mode_locked(user_ref, extra_conv.conversation_ref, "whore") == (False, "")
    assert repo.get_photo_gate(user_ref, extra_conv.conversation_ref)["awaiting_context"] == 0
    assert repo.load_relationship_state(user_ref, extra_conv.conversation_ref, "whore") is None
    assert repo.load_job("job-conv").status == JobStatus.CANCELLED
    assert repo.get_active_mode(user_ref, extra_conv.conversation_ref) == "basic"
    assert repo.load_history(user_ref, default_conv.conversation_ref, "basic") == [{"role": "user", "content": "keep-default"}]


def test_reset_user_all_clears_all_conversation_state_and_appends_events(tmp_path) -> None:
    db_path, repo = _make_repo(tmp_path)
    user_ref = UserRef("106")
    default_conv = repo.ensure_default_conversation(user_ref, active_mode="basic")
    extra_conv = repo.create_conversation(user_ref, active_mode="chef")
    now_ts = int(time.time())

    repo.append_history(user_ref, default_conv.conversation_ref, "basic", "user", "d1")
    repo.append_history(user_ref, extra_conv.conversation_ref, "chef", "user", "d2")
    repo.save_mode_state(user_ref, extra_conv.conversation_ref, "chef", {"recap": "temp"})
    repo.upsert_photo_gate(user_ref, default_conv.conversation_ref, {"score": 2})
    repo.create_job(
        DeferredJob(
            job_id="job-user",
            user_ref=user_ref,
            conversation_ref=extra_conv.conversation_ref,
            mode="chef",
            job_type=JobType.IMAGE,
            status=JobStatus.RUNNING,
            progress=10,
            created_at=now_ts,
            updated_at=now_ts,
        )
    )
    repo.append_event(
        AnalyticsEvent(
            event_type=AnalyticsEventType.RESET_USER_ALL,
            user_ref=user_ref,
            conversation_ref=extra_conv.conversation_ref,
            mode="chef",
            job_id="job-user",
            ts=now_ts,
            ok=True,
            note="before reset",
        )
    )

    repo.reset_user_all(user_ref)

    assert repo.load_history(user_ref, default_conv.conversation_ref, "basic") == []
    assert repo.load_history(user_ref, extra_conv.conversation_ref, "chef") == []
    assert repo.load_mode_state(user_ref, extra_conv.conversation_ref, "chef") is None
    assert repo.get_photo_gate(user_ref, default_conv.conversation_ref)["score"] == 0
    assert repo.load_job("job-user").status == JobStatus.CANCELLED
    assert repo.get_active_mode(user_ref, default_conv.conversation_ref) == "basic"
    assert repo.get_active_mode(user_ref, extra_conv.conversation_ref) == "basic"

    conn = sqlite3.connect(db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM user_events WHERE user_id=106").fetchone()[0] == 1
    finally:
        conn.close()


def test_session_lifecycle_and_expiry_cleanup(tmp_path) -> None:
    _, repo = _make_repo(tmp_path)
    user_ref = UserRef("107")
    now_ts = int(time.time())

    created = repo.create_session(
        user_ref,
        issued_at=now_ts,
        expires_at=now_ts + 3600,
    )

    loaded = repo.load_session(created.session_token)
    assert loaded is not None
    assert loaded.user_ref == user_ref
    assert loaded.issued_at == now_ts
    assert loaded.expires_at == now_ts + 3600
    assert loaded.last_seen_at == now_ts

    touched = repo.touch_session(created.session_token, last_seen_at=now_ts + 10)
    assert touched is not None
    assert touched.last_seen_at == now_ts + 10

    expired = repo.create_session(
        user_ref,
        issued_at=now_ts - 100,
        expires_at=now_ts - 1,
    )
    assert repo.delete_expired_sessions(now_ts=now_ts) == 1
    assert repo.load_session(expired.session_token) is None

    repo.delete_session(created.session_token)
    assert repo.load_session(created.session_token) is None
