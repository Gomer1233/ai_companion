from __future__ import annotations

import json
from dataclasses import dataclass

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.core.monetization import (
    AlphaProductCatalog,
    Entitlement,
    MonetizationService,
    PaymentOrder,
    PaymentProvider,
    ProductId,
)


PRODUCT_LABELS = {
    ProductId.PREMIUM_30D: "Premium 30d",
    ProductId.PREMIUM_1Y: "Premium 1y",
    ProductId.LIFETIME_PREMIUM_100: "Lifetime",
}


@dataclass(frozen=True, slots=True)
class StarsInvoice:
    title: str
    description: str
    payload: str
    currency: str
    prices: list[tuple[str, int]]


@dataclass(frozen=True, slots=True)
class PreCheckoutDecision:
    allowed: bool
    reason: str = ""


def build_stars_invoice(order: PaymentOrder) -> StarsInvoice:
    if order.provider != PaymentProvider.TELEGRAM_STARS:
        raise ValueError("stars_invoice_requires_stars_order")
    product_label = PRODUCT_LABELS[order.product_id]
    payload = json.dumps(
        {
            "order_id": order.order_id,
            "product_id": order.product_id.value,
            "provider": PaymentProvider.TELEGRAM_STARS.value,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return StarsInvoice(
        title=product_label,
        description=f"{product_label} access",
        payload=payload,
        currency="XTR",
        prices=[(product_label, order.amount_minor)],
    )


def build_stars_buy_keyboard(*, lifetime_available: bool) -> InlineKeyboardMarkup:
    catalog = AlphaProductCatalog.default()
    product_ids = [ProductId.PREMIUM_30D, ProductId.PREMIUM_1Y]
    if lifetime_available:
        product_ids.append(ProductId.LIFETIME_PREMIUM_100)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{PRODUCT_LABELS[product_id]} - {catalog.get(product_id).price_xtr} XTR",
                    callback_data=f"buy_stars:{product_id.value}",
                )
            ]
            for product_id in product_ids
        ]
    )


def validate_pre_checkout_payload(service: MonetizationService, payload: str) -> PreCheckoutDecision:
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return PreCheckoutDecision(False, "invalid_payload")

    if parsed.get("provider") != PaymentProvider.TELEGRAM_STARS.value:
        return PreCheckoutDecision(False, "provider_mismatch")
    order_id = str(parsed.get("order_id") or "")
    if not order_id:
        return PreCheckoutDecision(False, "order_missing")
    order = service.repositories.load_payment_order(order_id)
    if order is None:
        return PreCheckoutDecision(False, "order_not_found")
    if parsed.get("product_id") != order.product_id.value:
        return PreCheckoutDecision(False, "product_mismatch")
    if order.provider != PaymentProvider.TELEGRAM_STARS:
        return PreCheckoutDecision(False, "provider_mismatch")
    if order.product_id == ProductId.LIFETIME_PREMIUM_100 and not service.has_lifetime_capacity():
        return PreCheckoutDecision(False, "lifetime_cap_reached")
    return PreCheckoutDecision(True)


def fulfill_successful_stars_payment(
    service: MonetizationService,
    payload: str,
    *,
    telegram_payment_charge_id: str,
    paid_at: int,
) -> Entitlement:
    decision = validate_pre_checkout_payload(service, payload)
    if not decision.allowed:
        raise ValueError(decision.reason)
    parsed = json.loads(payload)
    order_id = str(parsed["order_id"])
    order = service.repositories.load_payment_order(order_id)
    if order is not None and order.entitlement_id:
        existing = service.repositories.fulfill_paid_order_transactionally(order_id, now_ts=paid_at)
        return existing
    service.mark_order_paid(
        order_id,
        provider_payment_id=telegram_payment_charge_id,
        provider_payload={"telegram_payment_charge_id": telegram_payment_charge_id},
        paid_at=paid_at,
    )
    return service.fulfill_paid_order(order_id, now_ts=paid_at)
