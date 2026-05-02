from __future__ import annotations

import sqlite3

import pytest

from src.core.contracts import UserRef
from src.core.monetization import PaymentOrder, PaymentProvider, PaymentStatus, ProductId, Tier
from src.db.migrations import migrate_database
from src.db.repositories import SQLiteRepositories


def _make_repo(tmp_path) -> tuple[str, SQLiteRepositories]:
    db_path = tmp_path / "monetization.db"
    migrate_database(str(db_path), include_relationship_state=True)
    return str(db_path), SQLiteRepositories(str(db_path), include_relationship_state=True)


def test_entitlements_usage_and_explicit_consent_round_trip(tmp_path) -> None:
    _, repo = _make_repo(tmp_path)
    user_ref = UserRef("51001")

    repo.upsert_entitlement(
        entitlement_id="ent-active",
        user_ref=user_ref,
        plan_id=ProductId.PREMIUM_30D.value,
        tier=Tier.PREMIUM,
        starts_at=1_000,
        expires_at=2_000,
        source="manual:operator:grant-1",
        created_at=1_000,
        metadata={"messages_per_day": 150},
    )
    repo.upsert_entitlement(
        entitlement_id="ent-expired",
        user_ref=user_ref,
        plan_id=ProductId.PREMIUM_30D.value,
        tier=Tier.PREMIUM,
        starts_at=500,
        expires_at=900,
        source="manual:operator:grant-0",
        created_at=500,
    )

    active = repo.load_active_entitlements(user_ref, now_ts=1_500)
    assert [item.entitlement_id for item in active] == ["ent-active"]
    assert active[0].metadata == {"messages_per_day": 150}

    assert repo.increment_usage(user_ref, "messages", window_start=86_400, window_end=172_800) == 1
    assert repo.increment_usage(user_ref, "messages", window_start=86_400, window_end=172_800, amount=2) == 3
    assert repo.load_usage(user_ref, "messages", window_start=86_400).value == 3

    repo.set_explicit_consent(user_ref, accepted_at=1_234, source="telegram")
    consent = repo.load_explicit_consent(user_ref)
    assert consent is not None
    assert consent.accepted_at == 1_234
    assert consent.revoked_at is None

    revoked = repo.revoke_entitlements(
        user_ref,
        revoked_by="operator:9001",
        revoked_at=1_600,
        reason="manual_support_revoke",
        source_filter="manual:operator:grant-1",
    )
    assert revoked == 1
    assert repo.load_active_entitlements(user_ref, now_ts=1_700) == []


def test_payment_order_fulfillment_is_idempotent_and_reuses_existing_entitlement(tmp_path) -> None:
    _, repo = _make_repo(tmp_path)
    user_ref = UserRef("51002")
    order = PaymentOrder(
        order_id="order-30d",
        user_ref=user_ref,
        provider=PaymentProvider.TELEGRAM_STARS,
        product_id=ProductId.PREMIUM_30D,
        amount_minor=500,
        currency="XTR",
        status=PaymentStatus.PENDING,
        created_at=2_000,
    )

    repo.create_payment_order(order)
    repo.mark_payment_order_paid(
        "order-30d",
        provider_payment_id="tg-payment-1",
        provider_payload_json='{"ok": true}',
        paid_at=2_010,
    )

    fulfilled = repo.fulfill_paid_order_transactionally("order-30d", now_ts=2_020)
    repeated = repo.fulfill_paid_order_transactionally("order-30d", now_ts=2_030)
    loaded_order = repo.load_payment_order("order-30d")

    assert repeated.entitlement_id == fulfilled.entitlement_id
    assert fulfilled.tier == Tier.PREMIUM
    assert fulfilled.expires_at == 2_020 + 30 * 86_400
    assert fulfilled.source == "payment:telegram_stars:order-30d"
    assert loaded_order is not None
    assert loaded_order.status == PaymentStatus.FULFILLED
    assert loaded_order.entitlement_id == fulfilled.entitlement_id


def test_fulfillment_recovers_when_entitlement_exists_before_order_is_fulfilled(tmp_path) -> None:
    _, repo = _make_repo(tmp_path)
    user_ref = UserRef("51003")
    order = PaymentOrder(
        order_id="order-retry",
        user_ref=user_ref,
        provider=PaymentProvider.TELEGRAM_STARS,
        product_id=ProductId.PREMIUM_1Y,
        amount_minor=2000,
        currency="XTR",
        status=PaymentStatus.PENDING,
        created_at=3_000,
    )
    repo.create_payment_order(order)
    repo.mark_payment_order_paid("order-retry", provider_payment_id="tg-payment-2", provider_payload_json="{}", paid_at=3_010)
    repo.upsert_entitlement(
        entitlement_id="ent-existing",
        user_ref=user_ref,
        plan_id=ProductId.PREMIUM_1Y.value,
        tier=Tier.PREMIUM,
        starts_at=3_020,
        expires_at=3_020 + 365 * 86_400,
        source="payment:telegram_stars:order-retry",
        created_at=3_020,
    )

    fulfilled = repo.fulfill_paid_order_transactionally("order-retry", now_ts=3_030)

    assert fulfilled.entitlement_id == "ent-existing"
    assert repo.load_payment_order("order-retry").entitlement_id == "ent-existing"


def test_lifetime_cap_blocks_101st_fulfilled_order(tmp_path) -> None:
    _, repo = _make_repo(tmp_path)
    user_ref = UserRef("51999")
    for index in range(100):
        repo.create_payment_order(
            PaymentOrder(
                order_id=f"life-{index}",
                user_ref=UserRef(str(52000 + index)),
                provider=PaymentProvider.TELEGRAM_STARS,
                product_id=ProductId.LIFETIME_PREMIUM_100,
                amount_minor=3000,
                currency="XTR",
                status=PaymentStatus.FULFILLED,
                entitlement_id=f"life-ent-{index}",
                created_at=4_000 + index,
                paid_at=4_000 + index,
                fulfilled_at=4_000 + index,
            )
        )

    repo.create_payment_order(
        PaymentOrder(
            order_id="life-101",
            user_ref=user_ref,
            provider=PaymentProvider.TELEGRAM_STARS,
            product_id=ProductId.LIFETIME_PREMIUM_100,
            amount_minor=3000,
            currency="XTR",
            status=PaymentStatus.PAID,
            created_at=5_000,
            paid_at=5_010,
        )
    )

    with pytest.raises(ValueError, match="lifetime_cap_reached"):
        repo.fulfill_paid_order_transactionally("life-101", now_ts=5_020)


def test_migration_005_creates_monetization_tables_and_constraints(tmp_path) -> None:
    db_path, _ = _make_repo(tmp_path)
    conn = sqlite3.connect(db_path)
    try:
        version = conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()[0]
        assert version == 5
        for table_name in (
            "entitlements",
            "usage_counters",
            "access_grants",
            "explicit_consent",
            "payment_orders",
            "admin_audit_events",
        ):
            assert conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            ).fetchone()
        entitlement_columns = {row[1] for row in conn.execute("PRAGMA table_info(entitlements)").fetchall()}
        assert {"status", "revoked_at", "revoked_by", "revoked_reason", "metadata_json"} <= entitlement_columns
        payment_columns = {row[1] for row in conn.execute("PRAGMA table_info(payment_orders)").fetchall()}
        assert "entitlement_id" in payment_columns
    finally:
        conn.close()
