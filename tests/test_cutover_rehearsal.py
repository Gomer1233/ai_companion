from __future__ import annotations

import sqlite3
import time

from src.core.contracts import DeferredJob, JobStatus, JobType, UserRef
from src.core.monetization import PaymentOrder, PaymentProvider, PaymentStatus, ProductId
from src.db.cutover import export_sqlite_snapshot, import_snapshot_to_repositories, snapshot_counts
from src.db.migrations import migrate_database
from src.db.repositories import SQLiteRepositories


def _make_repo(db_path) -> SQLiteRepositories:
    migrate_database(str(db_path), include_relationship_state=True)
    return SQLiteRepositories(str(db_path), include_relationship_state=True, history_limit=10)


def test_cutover_snapshot_exports_runtime_tables_from_sqlite_fixture(tmp_path) -> None:
    source_db = tmp_path / "source.db"
    source = _make_repo(source_db)
    user_ref = UserRef("71001")
    now_ts = int(time.time())
    conversation = source.ensure_default_conversation(user_ref, active_mode="chef")
    source.append_history(user_ref, conversation.conversation_ref, "chef", "user", "hello", created_at=now_ts)
    source.save_mode_state(user_ref, conversation.conversation_ref, "chef", {"recap": "busy"})
    source.lock_mode(user_ref, conversation.conversation_ref, "chef", "GAME OVER")
    source.upsert_photo_gate(user_ref, conversation.conversation_ref, {"score": 2, "awaiting_image_prompt": 1})
    source.save_relationship_state(user_ref, conversation.conversation_ref, "chef", {"stage": "DATING"})
    source.create_session(user_ref, issued_at=now_ts, expires_at=now_ts + 900, session_token="session-cutover")
    source.create_job(
        DeferredJob(
            job_id="job-cutover",
            user_ref=user_ref,
            conversation_ref=conversation.conversation_ref,
            mode="chef",
            job_type=JobType.IMAGE,
            status=JobStatus.RUNNING,
            progress=35,
            created_at=now_ts,
            updated_at=now_ts,
        )
    )
    conn = sqlite3.connect(source_db)
    try:
        conn.execute(
            """
            INSERT INTO user_profile(user_id, preferred_name, preferred_title, mode, chat_locked, lock_reason, mode_picked)
            VALUES(?, 'Lina', 'alpha', 'chef', 1, 'manual', 1)
            """,
            (int(user_ref.value),),
        )
        conn.execute(
            """
            INSERT INTO user_settings(user_id, model, image_model, image_provider)
            VALUES(?, 'openai/gpt-4o-mini', 'image-model', 'openrouter')
            """,
            (int(user_ref.value),),
        )
        conn.execute(
            """
            INSERT INTO user_events(ts, user_id, chat_id, username, first_name, event_type, mode, ok, note, conversation_ref)
            VALUES(?, ?, 71001, 'tester', 'Test', 'mode_switch', 'chef', 1, 'cutover', ?)
            """,
            (now_ts, int(user_ref.value), conversation.conversation_ref.value),
        )
        conn.commit()
    finally:
        conn.close()

    snapshot = export_sqlite_snapshot(str(source_db))

    assert snapshot_counts(snapshot) == {
        "conversations": 1,
        "conversation_mode_lock": 1,
        "conversation_mode_state": 1,
        "conversation_photo_gate": 1,
        "conversation_relationship_state": 1,
        "jobs": 1,
        "sessions": 1,
        "telegram_accounts": 1,
        "user_events": 1,
        "user_messages": 1,
        "user_profile": 1,
        "user_settings": 1,
        "users": 1,
    }
    for table_name in (
        "access_grants",
        "admin_audit_events",
        "entitlements",
        "explicit_consent",
        "payment_orders",
        "usage_counters",
    ):
        assert table_name in snapshot.tables
    assert snapshot.tables["users"][0]["user_id"] == 71001
    assert snapshot.tables["users"][0]["created_at"] == now_ts
    assert snapshot.tables["telegram_accounts"][0]["telegram_user_id"] == 71001


def test_cutover_rehearsal_imports_snapshot_into_repository_target(tmp_path) -> None:
    source_db = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    source = _make_repo(source_db)
    target = _make_repo(target_db)
    user_ref = UserRef("71002")
    now_ts = int(time.time())
    conversation = source.ensure_default_conversation(user_ref, active_mode="whore")
    source.append_history(user_ref, conversation.conversation_ref, "whore", "assistant", "reply", created_at=now_ts)
    source.save_mode_state(user_ref, conversation.conversation_ref, "whore", {"score": 7})
    source.upsert_photo_gate(user_ref, conversation.conversation_ref, {"attempts": 3})
    source.save_relationship_state(user_ref, conversation.conversation_ref, "whore", {"stage": "FLIRTING"})
    source.upsert_entitlement(
        entitlement_id="cutover-entitlement",
        user_ref=user_ref,
        plan_id="premium_30d",
        tier="premium",
        starts_at=now_ts,
        expires_at=now_ts + 30 * 86_400,
        source="payment:telegram_stars:cutover-order",
        created_at=now_ts,
    )
    source.set_explicit_consent(user_ref, accepted_at=now_ts, source="telegram")
    source.create_payment_order(
        PaymentOrder(
            order_id="cutover-order",
            user_ref=user_ref,
            provider=PaymentProvider.TELEGRAM_STARS,
            product_id=ProductId.PREMIUM_30D,
            amount_minor=500,
            currency="XTR",
            status=PaymentStatus.FULFILLED,
            entitlement_id="cutover-entitlement",
            created_at=now_ts,
            paid_at=now_ts,
            fulfilled_at=now_ts,
        )
    )
    source.create_session(user_ref, issued_at=now_ts, expires_at=now_ts + 900, session_token="session-import")
    source.create_job(
        DeferredJob(
            job_id="job-import",
            user_ref=user_ref,
            conversation_ref=conversation.conversation_ref,
            mode="whore",
            job_type=JobType.IMAGE,
            status=JobStatus.RUNNING,
            progress=60,
            created_at=now_ts,
            updated_at=now_ts,
        )
    )

    snapshot = export_sqlite_snapshot(str(source_db))
    result = import_snapshot_to_repositories(snapshot, target)

    imported_conversation = target.load_conversation(user_ref, conversation.conversation_ref)
    assert result.imported_counts["conversations"] == 1
    assert snapshot.tables["users"][0]["user_id"] == 71002
    assert imported_conversation is not None
    assert imported_conversation.active_mode == "whore"
    assert target.load_history(user_ref, conversation.conversation_ref, "whore") == [
        {"role": "assistant", "content": "reply"}
    ]
    assert target.load_mode_state(user_ref, conversation.conversation_ref, "whore") == {"score": 7}
    assert target.get_photo_gate(user_ref, conversation.conversation_ref)["attempts"] == 3
    assert target.load_relationship_state(user_ref, conversation.conversation_ref, "whore") == {"stage": "FLIRTING"}
    assert target.load_active_entitlements(user_ref, now_ts=now_ts)[0].entitlement_id == "cutover-entitlement"
    assert target.load_explicit_consent(user_ref).accepted_at == now_ts
    assert target.load_payment_order("cutover-order").entitlement_id == "cutover-entitlement"
    assert target.load_session("session-import").user_ref == user_ref
    assert target.load_job("job-import").progress == 60

    conn = sqlite3.connect(target_db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM conversations WHERE user_id=71002").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM user_messages WHERE user_id=71002").fetchone()[0] == 1
    finally:
        conn.close()
