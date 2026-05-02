from __future__ import annotations

import json

from src.core.contracts import UserRef
from src.core.monetization import MonetizationService, PaymentProvider, PaymentStatus, ProductId
from src.db.migrations import migrate_database
from src.db.repositories import SQLiteRepositories


def _make_service(tmp_path) -> tuple[SQLiteRepositories, MonetizationService]:
    db_path = tmp_path / "payments.db"
    migrate_database(str(db_path), include_relationship_state=True)
    repo = SQLiteRepositories(str(db_path), include_relationship_state=True)
    return repo, MonetizationService(repo)


def test_telegram_stars_invoice_payload_contains_internal_order_id(tmp_path) -> None:
    from src.adapters.telegram.payments import build_stars_invoice

    _, service = _make_service(tmp_path)
    order = service.create_payment_order(
        UserRef("62001"),
        PaymentProvider.TELEGRAM_STARS,
        ProductId.PREMIUM_30D,
        now_ts=10_000,
    )

    invoice = build_stars_invoice(order)
    payload = json.loads(invoice.payload)

    assert payload == {
        "order_id": order.order_id,
        "product_id": "premium_30d",
        "provider": "telegram_stars",
    }
    assert invoice.currency == "XTR"
    assert invoice.prices == [("Premium 30d", 500)]


def test_telegram_stars_buy_keyboard_does_not_expose_tbank() -> None:
    from src.adapters.telegram.payments import build_stars_buy_keyboard

    keyboard = build_stars_buy_keyboard(lifetime_available=True)
    texts = [button.text for row in keyboard.inline_keyboard for button in row]
    callback_data = [button.callback_data for row in keyboard.inline_keyboard for button in row]

    assert texts == ["Premium 30d - 500 XTR", "Premium 1y - 2000 XTR", "Lifetime - 3000 XTR"]
    assert all("tbank" not in str(value).lower() for value in callback_data)


def test_pre_checkout_rejects_unknown_or_mismatched_order(tmp_path) -> None:
    from src.adapters.telegram.payments import validate_pre_checkout_payload

    _, service = _make_service(tmp_path)
    order = service.create_payment_order(
        UserRef("62002"),
        PaymentProvider.TELEGRAM_STARS,
        ProductId.PREMIUM_30D,
        now_ts=20_000,
    )
    mismatched_payload = json.dumps(
        {
            "order_id": order.order_id,
            "product_id": "premium_1y",
            "provider": "telegram_stars",
        }
    )

    assert not validate_pre_checkout_payload(service, "missing-order").allowed
    decision = validate_pre_checkout_payload(service, mismatched_payload)
    assert not decision.allowed
    assert decision.reason == "product_mismatch"


def test_pre_checkout_rejects_lifetime_when_cap_is_full(tmp_path) -> None:
    from src.adapters.telegram.payments import validate_pre_checkout_payload

    _, service = _make_service(tmp_path)
    for index in range(100):
        service.grant_manual_access(
            operator_ref=UserRef("9001"),
            target_ref=UserRef(str(64000 + index)),
            tier="premium",
            now_ts=10_000 + index,
            duration_days=None,
            reason="manual_lifetime",
            product_id=ProductId.LIFETIME_PREMIUM_100,
        )
    order = service.create_payment_order(
        UserRef("64101"),
        PaymentProvider.TELEGRAM_STARS,
        ProductId.LIFETIME_PREMIUM_100,
        now_ts=20_000,
    )

    decision = validate_pre_checkout_payload(
        service,
        build_payload(order_id=order.order_id, product_id=ProductId.LIFETIME_PREMIUM_100),
    )

    assert not decision.allowed
    assert decision.reason == "lifetime_cap_reached"


def test_successful_payment_marks_order_paid_and_fulfills_once(tmp_path) -> None:
    from src.adapters.telegram.payments import fulfill_successful_stars_payment

    repo, service = _make_service(tmp_path)
    order = service.create_payment_order(
        UserRef("62003"),
        PaymentProvider.TELEGRAM_STARS,
        ProductId.PREMIUM_30D,
        now_ts=30_000,
    )
    payload = build_payload(order_id=order.order_id, product_id=ProductId.PREMIUM_30D)

    first = fulfill_successful_stars_payment(
        service,
        payload,
        telegram_payment_charge_id="stars-charge-1",
        paid_at=30_010,
    )
    second = fulfill_successful_stars_payment(
        service,
        payload,
        telegram_payment_charge_id="stars-charge-1",
        paid_at=30_020,
    )

    loaded_order = repo.load_payment_order(order.order_id)
    assert first.entitlement_id == second.entitlement_id
    assert loaded_order.status == PaymentStatus.FULFILLED
    assert loaded_order.provider_payment_id == "stars-charge-1"


def test_tbank_sandbox_init_payload_and_token() -> None:
    from src.app.settings import Settings
    from src.core.payment_providers import TBankPaymentClient, TBankSignature

    settings = Settings.from_env(
        {
            "TBANK_ENV": "sandbox",
            "TBANK_TERMINAL_KEY": "terminal",
            "TBANK_PASSWORD": "secret",
            "TBANK_SUCCESS_URL": "https://example.test/success",
            "TBANK_FAIL_URL": "https://example.test/fail",
            "TBANK_NOTIFICATION_URL": "https://example.test/webhook",
        }
    )
    order = service_order_stub(order_id="tb-order", amount_minor=49_900)

    payload = TBankPaymentClient.build_init_payload(order, settings)
    token = TBankSignature.make_token(payload, "secret")

    assert TBankPaymentClient.base_url(settings) == "https://securepay.tinkoff.ru"
    assert payload["TerminalKey"] == "terminal"
    assert payload["Amount"] == 49_900
    assert payload["OrderId"] == "tb-order"
    assert payload["NotificationURL"] == "https://example.test/webhook"
    assert payload["SuccessURL"] == "https://example.test/success"
    assert payload["FailURL"] == "https://example.test/fail"
    assert token == TBankSignature.make_token(payload | {"Token": "ignored"}, "secret")


def test_tbank_notification_verification_excludes_token_and_nested_payloads() -> None:
    from src.core.payment_providers import TBankSignature

    payload = {
        "TerminalKey": "terminal",
        "OrderId": "tb-order",
        "Success": True,
        "Status": "CONFIRMED",
        "PaymentId": "pay-1",
        "Amount": 49_900,
        "Data": {"ignored": True},
        "Receipt": {"ignored": True},
    }
    token = TBankSignature.make_token(payload, "secret")

    assert TBankSignature.verify_notification(payload | {"Token": token}, "secret")
    assert not TBankSignature.verify_notification(payload | {"Token": "bad"}, "secret")


def test_tbank_status_mapping() -> None:
    from src.core.payment_providers import map_tbank_status

    assert map_tbank_status("CONFIRMED") == PaymentStatus.PAID
    assert map_tbank_status("AUTHORIZED") == PaymentStatus.PENDING
    assert map_tbank_status("REJECTED") == PaymentStatus.FAILED
    assert map_tbank_status("AUTH_FAIL") == PaymentStatus.FAILED
    assert map_tbank_status("CANCELED") == PaymentStatus.CANCELLED


def build_payload(*, order_id: str, product_id: ProductId) -> str:
    return json.dumps(
        {
            "order_id": order_id,
            "product_id": product_id.value,
            "provider": "telegram_stars",
        }
    )


def service_order_stub(*, order_id: str, amount_minor: int):
    from src.core.monetization import PaymentOrder

    return PaymentOrder(
        order_id=order_id,
        user_ref=UserRef("62999"),
        provider=PaymentProvider.TBANK,
        product_id=ProductId.PREMIUM_30D,
        amount_minor=amount_minor,
        currency="RUB",
        status=PaymentStatus.PENDING,
        created_at=1,
    )
