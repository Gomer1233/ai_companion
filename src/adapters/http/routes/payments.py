from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import PlainTextResponse

from src.core.monetization import MonetizationService, PaymentStatus
from src.core.payment_providers import TBankSignature, map_tbank_status


router = APIRouter(prefix="/api/payments")


@router.post("/tbank/webhook")
def tbank_webhook(request: Request, payload: dict) -> PlainTextResponse:
    dependencies = request.app.state.dependencies
    settings = dependencies.settings
    if not TBankSignature.verify_notification(payload, settings.tbank_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_tbank_signature")

    order_id = str(payload.get("OrderId") or "")
    if not order_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="missing_order_id")
    order = dependencies.repositories.load_payment_order(order_id)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="payment_order_not_found")
    if int(payload.get("Amount") or 0) != order.amount_minor:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="amount_mismatch")

    mapped_status = map_tbank_status(str(payload.get("Status") or ""))
    service = MonetizationService(dependencies.repositories)
    if mapped_status == PaymentStatus.PAID:
        service.mark_order_paid(
            order_id,
            provider_payment_id=str(payload.get("PaymentId") or ""),
            provider_payload=payload,
            paid_at=int(payload.get("DateTime") or order.paid_at or order.created_at),
        )
        service.fulfill_paid_order(order_id, now_ts=int(payload.get("DateTime") or order.created_at))
    elif mapped_status == PaymentStatus.CANCELLED:
        service.mark_order_cancelled(order_id, cancelled_at=int(payload.get("DateTime") or order.created_at))
    elif mapped_status == PaymentStatus.FAILED:
        service.mark_order_failed(order_id, error_code=str(payload.get("Status") or "FAILED"))

    return PlainTextResponse("OK")
