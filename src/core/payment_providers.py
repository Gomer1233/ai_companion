from __future__ import annotations

import hashlib
from typing import Any

from src.app.settings import Settings
from src.core.monetization import PaymentOrder, PaymentStatus


class TBankSignature:
    @staticmethod
    def make_token(payload: dict[str, Any], password: str) -> str:
        scalar_items: dict[str, Any] = {}
        for key, value in payload.items():
            if key == "Token" or isinstance(value, (dict, list, tuple)):
                continue
            scalar_items[key] = value
        scalar_items["Password"] = password
        concatenated = "".join(str(scalar_items[key]) for key in sorted(scalar_items))
        return hashlib.sha256(concatenated.encode("utf-8")).hexdigest()

    @classmethod
    def verify_notification(cls, payload: dict[str, Any], password: str) -> bool:
        token = str(payload.get("Token") or "")
        if not token:
            return False
        return token == cls.make_token(payload, password)


class TBankPaymentClient:
    @staticmethod
    def base_url(settings: Settings) -> str:
        # T-Bank e-acquiring uses the same public API host for sandbox credentials.
        return "https://securepay.tinkoff.ru"

    @staticmethod
    def build_init_payload(order: PaymentOrder, settings: Settings) -> dict[str, Any]:
        payload = {
            "TerminalKey": settings.tbank_terminal_key,
            "Amount": order.amount_minor,
            "OrderId": order.order_id,
            "Description": order.product_id.value,
            "NotificationURL": settings.tbank_notification_url,
            "SuccessURL": settings.tbank_success_url,
            "FailURL": settings.tbank_fail_url,
        }
        payload["Token"] = TBankSignature.make_token(payload, settings.tbank_password)
        return payload


def map_tbank_status(status: str) -> PaymentStatus:
    normalized = status.strip().upper()
    if normalized == "CONFIRMED":
        return PaymentStatus.PAID
    if normalized == "AUTHORIZED":
        return PaymentStatus.PENDING
    if normalized in {"REJECTED", "AUTH_FAIL"}:
        return PaymentStatus.FAILED
    if normalized == "CANCELED":
        return PaymentStatus.CANCELLED
    return PaymentStatus.PENDING
