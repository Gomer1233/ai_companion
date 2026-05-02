from __future__ import annotations

import pytest

from src.core.contracts import UserRef
from src.core.monetization import (
    AlphaMonetizationPolicy,
    AlphaProductCatalog,
    LlmCostEstimator,
    MonetizationService,
    PaymentProvider,
    PaymentStatus,
    ProductId,
    Tier,
)
from src.db.migrations import migrate_database
from src.db.repositories import SQLiteRepositories


def test_alpha_products_and_prices_are_fixed() -> None:
    catalog = AlphaProductCatalog.default()

    assert catalog.get("premium_30d").price_rub == 499
    assert catalog.get("premium_30d").price_xtr == 500
    assert catalog.get("premium_30d").duration_days == 30
    assert catalog.get("premium_1y").price_rub == 1990
    assert catalog.get("premium_1y").price_xtr == 2000
    assert catalog.get("premium_1y").duration_days == 365
    assert catalog.get("lifetime_premium_100").price_rub == 2990
    assert catalog.get("lifetime_premium_100").price_xtr == 3000
    assert catalog.get("lifetime_premium_100").duration_days is None
    assert catalog.get("lifetime_premium_100").max_sales == 100


def test_alpha_limits_are_fixed_by_tier() -> None:
    policy = AlphaMonetizationPolicy.default()

    assert policy.limits_for(Tier.FREE).messages_per_day == 30
    assert policy.limits_for(Tier.FREE).explicit_images_per_day == 0
    assert policy.limits_for(Tier.TRIAL).messages_per_day == 100
    assert policy.limits_for(Tier.TRIAL).explicit_images_per_day == 3
    assert policy.limits_for(Tier.PREMIUM).messages_per_day == 300
    assert policy.limits_for(Tier.PREMIUM).explicit_images_per_day == 20


def test_cost_estimator_uses_input_and_output_token_prices() -> None:
    estimator = LlmCostEstimator.default()

    estimate = estimator.estimate("x-ai/grok-4.1-fast", prompt_tokens=1_000_000, completion_tokens=1_000_000)

    assert estimate.usd == 0.70


def _make_service(tmp_path) -> tuple[SQLiteRepositories, MonetizationService]:
    db_path = tmp_path / "monetization-core.db"
    migrate_database(str(db_path), include_relationship_state=True)
    repo = SQLiteRepositories(str(db_path), include_relationship_state=True)
    return repo, MonetizationService(repo)


def test_free_user_cannot_access_premium_persona(tmp_path) -> None:
    _, service = _make_service(tmp_path)

    decision = service.can_use_persona(UserRef("61001"), "coach_premium", now_ts=10_000)

    assert not decision.allowed
    assert decision.reasons == ("premium_required",)


def test_free_user_cannot_access_explicit_persona_even_with_consent(tmp_path) -> None:
    repo, service = _make_service(tmp_path)
    user_ref = UserRef("61002")
    repo.set_explicit_consent(user_ref, accepted_at=9_000, source="telegram")

    decision = service.can_use_persona(user_ref, "whore", now_ts=10_000)

    assert not decision.allowed
    assert decision.reasons == ("explicit_tier_required",)


def test_trial_user_with_consent_can_access_explicit_persona_until_expiry(tmp_path) -> None:
    repo, service = _make_service(tmp_path)
    user_ref = UserRef("61003")
    repo.upsert_entitlement(
        entitlement_id="trial-ent",
        user_ref=user_ref,
        plan_id="manual_trial",
        tier=Tier.TRIAL,
        starts_at=1_000,
        expires_at=20_000,
        source="manual:operator:trial",
        created_at=1_000,
    )
    repo.set_explicit_consent(user_ref, accepted_at=9_000, source="telegram")

    active = service.can_use_persona(user_ref, "whore", now_ts=10_000)
    expired = service.can_use_persona(user_ref, "whore", now_ts=21_000)

    assert active.allowed
    assert not expired.allowed
    assert expired.reasons == ("explicit_tier_required",)


def test_premium_user_without_consent_cannot_access_explicit_persona(tmp_path) -> None:
    repo, service = _make_service(tmp_path)
    user_ref = UserRef("61004")
    repo.upsert_entitlement(
        entitlement_id="premium-ent",
        user_ref=user_ref,
        plan_id="premium_30d",
        tier=Tier.PREMIUM,
        starts_at=1_000,
        expires_at=20_000,
        source="payment:telegram_stars:order",
        created_at=1_000,
    )

    decision = service.can_use_persona(user_ref, "whore", now_ts=10_000)

    assert not decision.allowed
    assert decision.reasons == ("explicit_consent_required",)


def test_custom_trial_grant_overrides_default_limits_for_one_user(tmp_path) -> None:
    repo, service = _make_service(tmp_path)
    user_ref = UserRef("61005")
    repo.upsert_entitlement(
        entitlement_id="custom-trial",
        user_ref=user_ref,
        plan_id="manual_trial",
        tier=Tier.TRIAL,
        starts_at=1_000,
        expires_at=20_000,
        source="manual:operator:trial",
        created_at=1_000,
        metadata={"messages_per_day": 12, "explicit_images_per_day": 1},
    )

    snapshot = service.get_access_snapshot(user_ref, now_ts=10_000)

    assert snapshot.effective_tier == Tier.TRIAL
    assert snapshot.limits.messages_per_day == 12
    assert snapshot.limits.explicit_images_per_day == 1


def test_explicit_image_generation_is_denied_when_daily_usage_reaches_limit(tmp_path) -> None:
    repo, service = _make_service(tmp_path)
    user_ref = UserRef("61006")
    now_ts = 86_400 + 123
    repo.upsert_entitlement(
        entitlement_id="premium-image",
        user_ref=user_ref,
        plan_id="premium_30d",
        tier=Tier.PREMIUM,
        starts_at=1_000,
        expires_at=200_000,
        source="payment:telegram_stars:order-image",
        created_at=1_000,
    )
    repo.set_explicit_consent(user_ref, accepted_at=2_000, source="telegram")
    for _ in range(20):
        service.record_explicit_image_usage(user_ref, now_ts=now_ts)

    decision = service.can_generate_explicit_image(user_ref, now_ts=now_ts)

    assert not decision.allowed
    assert decision.reasons == ("explicit_image_limit_reached",)


def test_service_creates_stars_order_and_fulfills_premium_30d(tmp_path) -> None:
    repo, service = _make_service(tmp_path)
    user_ref = UserRef("61007")

    order = service.create_payment_order(user_ref, PaymentProvider.TELEGRAM_STARS, ProductId.PREMIUM_30D, now_ts=30_000)
    paid = service.mark_order_paid(order.order_id, provider_payment_id="stars-paid-1", provider_payload={}, paid_at=30_010)
    entitlement = service.fulfill_paid_order(order.order_id, now_ts=30_020)

    assert order.amount_minor == 500
    assert order.currency == "XTR"
    assert paid.status == PaymentStatus.PAID
    assert entitlement.tier == Tier.PREMIUM
    assert entitlement.expires_at == 30_020 + 30 * 86_400
    assert repo.load_payment_order(order.order_id).status == PaymentStatus.FULFILLED


def test_service_fulfills_one_year_and_lifetime_products(tmp_path) -> None:
    _, service = _make_service(tmp_path)
    user_ref = UserRef("61008")

    yearly = service.create_payment_order(user_ref, PaymentProvider.TELEGRAM_STARS, ProductId.PREMIUM_1Y, now_ts=40_000)
    service.mark_order_paid(yearly.order_id, provider_payment_id="stars-paid-2", provider_payload={}, paid_at=40_010)
    yearly_entitlement = service.fulfill_paid_order(yearly.order_id, now_ts=40_020)

    lifetime = service.create_payment_order(user_ref, PaymentProvider.TELEGRAM_STARS, ProductId.LIFETIME_PREMIUM_100, now_ts=50_000)
    service.mark_order_paid(lifetime.order_id, provider_payment_id="stars-paid-3", provider_payload={}, paid_at=50_010)
    lifetime_entitlement = service.fulfill_paid_order(lifetime.order_id, now_ts=50_020)

    assert yearly_entitlement.expires_at == 40_020 + 365 * 86_400
    assert lifetime_entitlement.expires_at is None


def test_service_fulfillment_is_idempotent(tmp_path) -> None:
    _, service = _make_service(tmp_path)
    user_ref = UserRef("61009")
    order = service.create_payment_order(user_ref, PaymentProvider.TELEGRAM_STARS, ProductId.PREMIUM_30D, now_ts=60_000)
    service.mark_order_paid(order.order_id, provider_payment_id="stars-paid-4", provider_payload={}, paid_at=60_010)

    first = service.fulfill_paid_order(order.order_id, now_ts=60_020)
    second = service.fulfill_paid_order(order.order_id, now_ts=60_030)

    assert second.entitlement_id == first.entitlement_id


def test_service_marks_refund_and_cancel_states_without_user_refund_actions(tmp_path) -> None:
    repo, service = _make_service(tmp_path)
    user_ref = UserRef("61010")
    refund_order = service.create_payment_order(user_ref, PaymentProvider.TELEGRAM_STARS, ProductId.PREMIUM_30D, now_ts=70_000)
    cancel_order = service.create_payment_order(user_ref, PaymentProvider.TELEGRAM_STARS, ProductId.PREMIUM_1Y, now_ts=70_100)

    service.mark_order_refunded(refund_order.order_id, refunded_at=70_200)
    service.mark_order_cancelled(cancel_order.order_id, cancelled_at=70_300)

    assert repo.load_payment_order(refund_order.order_id).status == PaymentStatus.REFUNDED
    assert repo.load_payment_order(cancel_order.order_id).status == PaymentStatus.CANCELLED
    assert service.user_payment_actions(refund_order.order_id) == ()


def test_manual_trial_grant_accepts_custom_limits_and_writes_audit(tmp_path) -> None:
    repo, service = _make_service(tmp_path)
    target_ref = UserRef("61011")

    entitlement = service.grant_manual_access(
        operator_ref=UserRef("9001"),
        target_ref=target_ref,
        tier=Tier.TRIAL,
        now_ts=80_000,
        duration_days=5,
        reason="support_trial",
        messages_per_day=12,
        explicit_images_per_day=1,
    )
    snapshot = service.get_access_snapshot(target_ref, now_ts=80_100)

    assert entitlement.tier == Tier.TRIAL
    assert entitlement.expires_at == 80_000 + 5 * 86_400
    assert snapshot.limits.messages_per_day == 12
    assert snapshot.limits.explicit_images_per_day == 1
    assert repo.count_admin_audit_events(action="grant_access", target_user_id=61011) == 1


def test_manual_lifetime_grant_counts_against_lifetime_cap(tmp_path) -> None:
    _, service = _make_service(tmp_path)
    for index in range(100):
        service.grant_manual_access(
            operator_ref=UserRef("9001"),
            target_ref=UserRef(str(63000 + index)),
            tier=Tier.PREMIUM,
            now_ts=90_000 + index,
            duration_days=None,
            reason="lifetime",
            product_id=ProductId.LIFETIME_PREMIUM_100,
        )

    with pytest.raises(ValueError, match="lifetime_cap_reached"):
        service.grant_manual_access(
            operator_ref=UserRef("9001"),
            target_ref=UserRef("63101"),
            tier=Tier.PREMIUM,
            now_ts=91_000,
            duration_days=None,
            reason="lifetime",
            product_id=ProductId.LIFETIME_PREMIUM_100,
        )


def test_revoke_manual_access_writes_audit(tmp_path) -> None:
    repo, service = _make_service(tmp_path)
    target_ref = UserRef("61012")
    service.grant_manual_access(
        operator_ref=UserRef("9001"),
        target_ref=target_ref,
        tier=Tier.PREMIUM,
        now_ts=100_000,
        duration_days=30,
        reason="support",
    )

    revoked = service.revoke_manual_access(
        operator_ref=UserRef("9001"),
        target_ref=target_ref,
        now_ts=100_100,
        reason="refund",
    )

    assert revoked == 1
    assert repo.count_admin_audit_events(action="revoke_access", target_user_id=61012) == 1


def test_fulfill_order_repair_writes_audit(tmp_path) -> None:
    repo, service = _make_service(tmp_path)
    order = service.create_payment_order(
        UserRef("61013"),
        PaymentProvider.TELEGRAM_STARS,
        ProductId.PREMIUM_30D,
        now_ts=110_000,
    )
    service.mark_order_paid(order.order_id, provider_payment_id="repair-payment", provider_payload={}, paid_at=110_010)

    entitlement = service.fulfill_order_repair(
        operator_ref=UserRef("9001"),
        order_id=order.order_id,
        now_ts=110_020,
        reason="paid_not_fulfilled",
    )

    assert entitlement.entitlement_id == repo.load_payment_order(order.order_id).entitlement_id
    assert repo.count_admin_audit_events(action="fulfill_order", target_user_id=None) == 1


def test_paid_but_not_fulfilled_orders_are_visible_to_operator(tmp_path) -> None:
    _, service = _make_service(tmp_path)
    order = service.create_payment_order(
        UserRef("61014"),
        PaymentProvider.TELEGRAM_STARS,
        ProductId.PREMIUM_30D,
        now_ts=120_000,
    )
    service.mark_order_paid(order.order_id, provider_payment_id="paid-visible", provider_payload={}, paid_at=120_010)

    visible = service.list_paid_unfulfilled_orders()

    assert [item.order_id for item in visible] == [order.order_id]


def test_admin_user_summaries_support_filter_sort_and_cost(tmp_path) -> None:
    repo, service = _make_service(tmp_path)
    premium_ref = UserRef("61015")
    trial_ref = UserRef("61016")
    service.grant_manual_access(
        operator_ref=UserRef("9001"),
        target_ref=premium_ref,
        tier=Tier.PREMIUM,
        now_ts=130_000,
        duration_days=30,
        reason="support",
    )
    service.grant_manual_access(
        operator_ref=UserRef("9001"),
        target_ref=trial_ref,
        tier=Tier.TRIAL,
        now_ts=130_000,
        duration_days=5,
        reason="support",
        messages_per_day=12,
    )
    repo.increment_usage(premium_ref, "messages", window_start=86_400, window_end=172_800, amount=7)
    repo.increment_usage(trial_ref, "messages", window_start=86_400, window_end=172_800, amount=1)
    conn = repo._connect()
    try:
        conn.execute(
            """
            INSERT INTO user_events(ts, user_id, chat_id, username, first_name, event_type, mode, prompt_tokens, completion_tokens)
            VALUES(?,?,?,?,?,?,?,?,?)
            """,
            (130_010, 61015, 1, "premium_user", "Premium", "message", "basic", 1_000_000, 1_000_000),
        )
        conn.execute(
            """
            INSERT INTO user_events(ts, user_id, chat_id, username, first_name, event_type, mode, prompt_tokens, completion_tokens)
            VALUES(?,?,?,?,?,?,?,?,?)
            """,
            (130_020, 61016, 1, "trial_user", "Trial", "message", "basic", 1, 1),
        )
        conn.commit()
    finally:
        conn.close()

    summaries = service.list_admin_user_summaries(
        now_ts=130_100,
        q="premium",
        tier="premium",
        sort="cost",
        desc=True,
        page=1,
    )

    assert [item.telegram_user_id for item in summaries] == [61015]
    assert summaries[0].username == "premium_user"
    assert summaries[0].messages_used == 7
    assert summaries[0].estimated_cost_usd == 0.70
