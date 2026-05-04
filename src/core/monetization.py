from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Protocol

from src.core.contracts import UserRef


class Tier(str, Enum):
    FREE = "free"
    TRIAL = "trial"
    PREMIUM = "premium"


class ProductId(str, Enum):
    PREMIUM_30D = "premium_30d"
    PREMIUM_1Y = "premium_1y"
    LIFETIME_PREMIUM_100 = "lifetime_premium_100"


class PaymentProvider(str, Enum):
    TELEGRAM_STARS = "telegram_stars"
    TBANK = "tbank"


class PaymentStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    FULFILLED = "fulfilled"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


@dataclass(frozen=True, slots=True)
class UsageLimits:
    messages_per_day: int
    explicit_images_per_day: int


@dataclass(frozen=True, slots=True)
class Product:
    product_id: ProductId
    tier: Tier
    duration_days: int | None
    price_rub: int
    price_xtr: int
    max_sales: int | None = None


@dataclass(frozen=True, slots=True)
class Entitlement:
    entitlement_id: str
    user_ref: UserRef
    plan_id: str
    tier: Tier
    starts_at: int
    expires_at: int | None
    status: str
    source: str
    created_at: int
    revoked_at: int | None = None
    revoked_by: str | None = None
    revoked_reason: str | None = None
    metadata: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class UsageCounter:
    user_ref: UserRef
    counter_key: str
    window_start: int
    window_end: int
    value: int


@dataclass(frozen=True, slots=True)
class ExplicitConsent:
    user_ref: UserRef
    accepted_at: int
    revoked_at: int | None
    source: str


@dataclass(frozen=True, slots=True)
class PaymentOrder:
    order_id: str
    user_ref: UserRef
    provider: PaymentProvider
    product_id: ProductId
    amount_minor: int
    currency: str
    status: PaymentStatus
    created_at: int
    entitlement_id: str | None = None
    provider_payment_id: str | None = None
    provider_payload_json: str | None = None
    paid_at: int | None = None
    fulfilled_at: int | None = None
    refunded_at: int | None = None
    cancelled_at: int | None = None
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class AlphaProductCatalog:
    products: dict[ProductId, Product]

    @classmethod
    def default(cls) -> "AlphaProductCatalog":
        return cls(
            products={
                ProductId.PREMIUM_30D: Product(
                    product_id=ProductId.PREMIUM_30D,
                    tier=Tier.PREMIUM,
                    duration_days=30,
                    price_rub=499,
                    price_xtr=500,
                ),
                ProductId.PREMIUM_1Y: Product(
                    product_id=ProductId.PREMIUM_1Y,
                    tier=Tier.PREMIUM,
                    duration_days=365,
                    price_rub=1990,
                    price_xtr=2000,
                ),
                ProductId.LIFETIME_PREMIUM_100: Product(
                    product_id=ProductId.LIFETIME_PREMIUM_100,
                    tier=Tier.PREMIUM,
                    duration_days=None,
                    price_rub=2990,
                    price_xtr=3000,
                    max_sales=100,
                ),
            }
        )

    def get(self, product_id: ProductId | str) -> Product:
        resolved_id = ProductId(product_id)
        return self.products[resolved_id]


@dataclass(frozen=True, slots=True)
class AlphaMonetizationPolicy:
    limits_by_tier: dict[Tier, UsageLimits]

    @classmethod
    def default(cls) -> "AlphaMonetizationPolicy":
        return cls(
            limits_by_tier={
                Tier.FREE: UsageLimits(messages_per_day=30, explicit_images_per_day=0),
                Tier.TRIAL: UsageLimits(messages_per_day=100, explicit_images_per_day=3),
                Tier.PREMIUM: UsageLimits(messages_per_day=300, explicit_images_per_day=20),
            }
        )

    def limits_for(self, tier: Tier | str) -> UsageLimits:
        resolved_tier = Tier(tier)
        return self.limits_by_tier[resolved_tier]


@dataclass(frozen=True, slots=True)
class UsageSnapshot:
    messages_used: int
    explicit_images_used: int
    reset_at: int


@dataclass(frozen=True, slots=True)
class AccessSnapshot:
    user_ref: UserRef
    effective_tier: Tier
    tier_expires_at: int | None
    explicit_consent: bool
    limits: UsageLimits
    usage: UsageSnapshot
    blocked_reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AccessDecision:
    allowed: bool
    reasons: tuple[str, ...] = ()


class MonetizationRepositories(Protocol):
    def load_active_entitlements(self, user_ref: UserRef, now_ts: int) -> list[Entitlement]: ...
    def load_usage(self, user_ref: UserRef, counter_key: str, *, window_start: int) -> UsageCounter: ...
    def load_explicit_consent(self, user_ref: UserRef) -> ExplicitConsent | None: ...
    def revoke_explicit_consent(
        self,
        user_ref: UserRef,
        *,
        revoked_at: int,
        source: str,
    ) -> ExplicitConsent | None: ...
    def increment_usage(
        self,
        user_ref: UserRef,
        counter_key: str,
        *,
        window_start: int,
        window_end: int,
        amount: int = 1,
    ) -> int: ...
    def create_payment_order(self, order: PaymentOrder) -> PaymentOrder: ...
    def load_payment_order(self, order_id: str) -> PaymentOrder | None: ...
    def mark_payment_order_paid(
        self,
        order_id: str,
        *,
        provider_payment_id: str,
        provider_payload_json: str,
        paid_at: int,
    ) -> PaymentOrder: ...
    def mark_payment_order_refunded(self, order_id: str, *, refunded_at: int) -> PaymentOrder: ...
    def mark_payment_order_cancelled(self, order_id: str, *, cancelled_at: int) -> PaymentOrder: ...
    def mark_payment_order_failed(self, order_id: str, *, error_code: str) -> PaymentOrder: ...
    def fulfill_paid_order_transactionally(self, order_id: str, *, now_ts: int) -> Entitlement: ...
    def upsert_entitlement(
        self,
        *,
        entitlement_id: str,
        user_ref: UserRef,
        plan_id: str,
        tier: Tier | str,
        starts_at: int,
        expires_at: int | None,
        source: str,
        created_at: int,
        status: str = "active",
        revoked_at: int | None = None,
        revoked_by: str | None = None,
        revoked_reason: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> Entitlement: ...
    def revoke_entitlements(
        self,
        user_ref: UserRef,
        *,
        revoked_by: str,
        revoked_at: int,
        reason: str,
        source_filter: str | None = None,
    ) -> int: ...
    def list_paid_unfulfilled_orders(self) -> list[PaymentOrder]: ...
    def load_manual_lifetime_entitlement_count(self) -> int: ...
    def list_admin_user_identities(self, *, q: str | None = None) -> list[dict[str, Any]]: ...
    def load_latest_payment_status(self, user_ref: UserRef) -> str: ...
    def load_llm_token_totals(self, user_ref: UserRef) -> tuple[int, int]: ...
    def append_admin_audit_event(
        self,
        *,
        audit_id: str,
        operator_user_id: str,
        action: str,
        result: str,
        created_at: int,
        target_user_id: int | None = None,
        target_order_id: str | None = None,
        reason: str = "",
        metadata: dict[str, object] | None = None,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class AdminUserSummary:
    telegram_user_id: int
    name: str
    username: str
    tier: str
    expires_at: int | None
    payment_status: str
    messages_used: int
    explicit_images_used: int
    estimated_cost_usd: float
    explicit_consent: bool
    last_active_at: int | None
    actions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MonetizationService:
    repositories: MonetizationRepositories
    policy: AlphaMonetizationPolicy = AlphaMonetizationPolicy.default()
    catalog: AlphaProductCatalog = AlphaProductCatalog.default()

    def get_effective_tier(self, user_ref: UserRef, now_ts: int) -> tuple[Tier, int | None, dict[str, object]]:
        entitlements = self.repositories.load_active_entitlements(user_ref, now_ts)
        if not entitlements:
            return Tier.FREE, None, {}

        premium = [item for item in entitlements if item.tier == Tier.PREMIUM]
        if premium:
            selected = sorted(premium, key=lambda item: (item.expires_at is None, item.expires_at or 0), reverse=True)[0]
            return Tier.PREMIUM, selected.expires_at, selected.metadata or {}

        trial = [item for item in entitlements if item.tier == Tier.TRIAL]
        if trial:
            selected = sorted(trial, key=lambda item: item.expires_at or 0, reverse=True)[0]
            return Tier.TRIAL, selected.expires_at, selected.metadata or {}

        return Tier.FREE, None, {}

    def get_access_snapshot(self, user_ref: UserRef, now_ts: int) -> AccessSnapshot:
        tier, expires_at, metadata = self.get_effective_tier(user_ref, now_ts)
        limits = self._limits_for(tier, metadata)
        window_start, window_end = self._daily_window(now_ts)
        message_usage = self.repositories.load_usage(user_ref, "messages", window_start=window_start)
        image_usage = self.repositories.load_usage(user_ref, "explicit_images", window_start=window_start)
        consent = self.repositories.load_explicit_consent(user_ref)
        has_consent = bool(consent and consent.revoked_at is None and consent.accepted_at <= now_ts)
        return AccessSnapshot(
            user_ref=user_ref,
            effective_tier=tier,
            tier_expires_at=expires_at,
            explicit_consent=has_consent,
            limits=limits,
            usage=UsageSnapshot(
                messages_used=message_usage.value,
                explicit_images_used=image_usage.value,
                reset_at=window_end,
            ),
        )

    def can_use_persona(self, user_ref: UserRef, persona: str, now_ts: int) -> AccessDecision:
        snapshot = self.get_access_snapshot(user_ref, now_ts)
        normalized_persona = persona.strip().lower()
        if self._is_premium_persona(normalized_persona) and snapshot.effective_tier != Tier.PREMIUM:
            return AccessDecision(False, ("premium_required",))
        if self._is_explicit_persona(normalized_persona):
            if snapshot.effective_tier not in {Tier.TRIAL, Tier.PREMIUM}:
                return AccessDecision(False, ("explicit_tier_required",))
            if not snapshot.explicit_consent:
                return AccessDecision(False, ("explicit_consent_required",))
        return AccessDecision(True)

    def can_generate_explicit_image(self, user_ref: UserRef, now_ts: int) -> AccessDecision:
        snapshot = self.get_access_snapshot(user_ref, now_ts)
        if snapshot.effective_tier not in {Tier.TRIAL, Tier.PREMIUM}:
            return AccessDecision(False, ("explicit_tier_required",))
        if not snapshot.explicit_consent:
            return AccessDecision(False, ("explicit_consent_required",))
        if snapshot.usage.explicit_images_used >= snapshot.limits.explicit_images_per_day:
            return AccessDecision(False, ("explicit_image_limit_reached",))
        return AccessDecision(True)

    def can_send_message(self, user_ref: UserRef, now_ts: int) -> AccessDecision:
        snapshot = self.get_access_snapshot(user_ref, now_ts)
        if snapshot.usage.messages_used >= snapshot.limits.messages_per_day:
            return AccessDecision(False, ("message_limit_reached",))
        return AccessDecision(True)

    def record_message_usage(self, user_ref: UserRef, now_ts: int) -> int:
        window_start, window_end = self._daily_window(now_ts)
        return self.repositories.increment_usage(user_ref, "messages", window_start=window_start, window_end=window_end)

    def record_explicit_image_usage(self, user_ref: UserRef, now_ts: int) -> int:
        window_start, window_end = self._daily_window(now_ts)
        return self.repositories.increment_usage(
            user_ref,
            "explicit_images",
            window_start=window_start,
            window_end=window_end,
        )

    def create_payment_order(
        self,
        user_ref: UserRef,
        provider: PaymentProvider | str,
        product_id: ProductId | str,
        *,
        now_ts: int,
    ) -> PaymentOrder:
        resolved_provider = PaymentProvider(provider)
        resolved_product_id = ProductId(product_id)
        product = self.catalog.get(resolved_product_id)
        if resolved_provider == PaymentProvider.TELEGRAM_STARS:
            amount_minor = product.price_xtr
            currency = "XTR"
        elif resolved_provider == PaymentProvider.TBANK:
            amount_minor = product.price_rub * 100
            currency = "RUB"
        else:
            raise ValueError("unsupported_payment_provider")
        order = PaymentOrder(
            order_id=uuid.uuid4().hex,
            user_ref=user_ref,
            provider=resolved_provider,
            product_id=resolved_product_id,
            amount_minor=amount_minor,
            currency=currency,
            status=PaymentStatus.PENDING,
            created_at=int(now_ts),
        )
        return self.repositories.create_payment_order(order)

    def mark_order_paid(
        self,
        order_id: str,
        *,
        provider_payment_id: str,
        provider_payload: dict[str, object],
        paid_at: int,
    ) -> PaymentOrder:
        return self.repositories.mark_payment_order_paid(
            order_id,
            provider_payment_id=provider_payment_id,
            provider_payload_json=json.dumps(provider_payload, ensure_ascii=False, sort_keys=True),
            paid_at=paid_at,
        )

    def fulfill_paid_order(self, order_id: str, *, now_ts: int) -> Entitlement:
        return self.repositories.fulfill_paid_order_transactionally(order_id, now_ts=now_ts)

    def mark_order_refunded(self, order_id: str, *, refunded_at: int) -> PaymentOrder:
        return self.repositories.mark_payment_order_refunded(order_id, refunded_at=refunded_at)

    def mark_order_cancelled(self, order_id: str, *, cancelled_at: int) -> PaymentOrder:
        return self.repositories.mark_payment_order_cancelled(order_id, cancelled_at=cancelled_at)

    def mark_order_failed(self, order_id: str, *, error_code: str) -> PaymentOrder:
        return self.repositories.mark_payment_order_failed(order_id, error_code=error_code)

    def has_lifetime_capacity(self) -> bool:
        return self._lifetime_entitlement_count() < 100

    def user_payment_actions(self, order_id: str) -> tuple[str, ...]:
        order = self.repositories.load_payment_order(order_id)
        if order is None:
            return ()
        if order.status in {PaymentStatus.REFUNDED, PaymentStatus.CANCELLED}:
            return ()
        return ()

    def grant_manual_access(
        self,
        *,
        operator_ref: UserRef,
        target_ref: UserRef,
        tier: Tier | str,
        now_ts: int,
        duration_days: int | None,
        reason: str,
        messages_per_day: int | None = None,
        explicit_images_per_day: int | None = None,
        product_id: ProductId | str | None = None,
    ) -> Entitlement:
        resolved_tier = Tier(tier)
        resolved_product_id = ProductId(product_id) if product_id is not None else None
        if resolved_product_id == ProductId.LIFETIME_PREMIUM_100 and not self.has_lifetime_capacity():
            raise ValueError("lifetime_cap_reached")
        metadata: dict[str, object] = {}
        if messages_per_day is not None:
            metadata["messages_per_day"] = messages_per_day
        if explicit_images_per_day is not None:
            metadata["explicit_images_per_day"] = explicit_images_per_day
        grant_id = uuid.uuid4().hex
        plan_id = resolved_product_id.value if resolved_product_id is not None else f"manual_{resolved_tier.value}"
        expires_at = None if duration_days is None else int(now_ts) + int(duration_days) * 86_400
        entitlement = self.repositories.upsert_entitlement(
            entitlement_id=f"manual-{grant_id}",
            user_ref=target_ref,
            plan_id=plan_id,
            tier=resolved_tier,
            starts_at=now_ts,
            expires_at=expires_at,
            source=f"manual:{operator_ref.value}:{grant_id}",
            created_at=now_ts,
            metadata=metadata,
        )
        self.append_admin_audit_event(
            operator_ref=operator_ref,
            action="grant_access",
            target_ref=target_ref,
            result="success",
            reason=reason,
            created_at=now_ts,
        )
        return entitlement

    def revoke_manual_access(self, *, operator_ref: UserRef, target_ref: UserRef, now_ts: int, reason: str) -> int:
        revoked = self.repositories.revoke_entitlements(
            target_ref,
            revoked_by=operator_ref.value,
            revoked_at=now_ts,
            reason=reason,
        )
        self.append_admin_audit_event(
            operator_ref=operator_ref,
            action="revoke_access",
            target_ref=target_ref,
            result="success" if revoked else "noop",
            reason=reason,
            created_at=now_ts,
        )
        return revoked

    def fulfill_order_repair(self, *, operator_ref: UserRef, order_id: str, now_ts: int, reason: str) -> Entitlement:
        entitlement = self.fulfill_paid_order(order_id, now_ts=now_ts)
        self.append_admin_audit_event(
            operator_ref=operator_ref,
            action="fulfill_order",
            target_order_id=order_id,
            result="success",
            reason=reason,
            created_at=now_ts,
        )
        return entitlement

    def list_paid_unfulfilled_orders(self) -> list[PaymentOrder]:
        return self.repositories.list_paid_unfulfilled_orders()

    def list_admin_user_summaries(
        self,
        *,
        now_ts: int,
        q: str | None = None,
        tier: str | None = None,
        sort: str | None = None,
        desc: bool = False,
        page: int = 1,
        page_size: int = 10,
    ) -> list[AdminUserSummary]:
        identities = self.repositories.list_admin_user_identities(q=q)
        summaries: list[AdminUserSummary] = []
        estimator = LlmCostEstimator.default()
        for identity in identities:
            user_ref = UserRef(str(identity["telegram_user_id"]))
            snapshot = self.get_access_snapshot(user_ref, now_ts=now_ts)
            if tier and snapshot.effective_tier.value != tier:
                continue
            prompt_tokens, completion_tokens = self.repositories.load_llm_token_totals(user_ref)
            estimate = estimator.estimate(
                "x-ai/grok-4.1-fast",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
            summaries.append(
                AdminUserSummary(
                    telegram_user_id=int(identity["telegram_user_id"]),
                    name=str(identity.get("name") or ""),
                    username=str(identity.get("username") or ""),
                    tier=snapshot.effective_tier.value,
                    expires_at=snapshot.tier_expires_at,
                    payment_status=self.repositories.load_latest_payment_status(user_ref),
                    messages_used=snapshot.usage.messages_used,
                    explicit_images_used=snapshot.usage.explicit_images_used,
                    estimated_cost_usd=estimate.usd,
                    explicit_consent=snapshot.explicit_consent,
                    last_active_at=identity.get("last_active_at"),
                    actions=("status", "usage", "grant", "revoke"),
                )
            )

        sort_key = (sort or "last_active").strip().lower()
        key_map = {
            "tier": lambda item: item.tier,
            "expires": lambda item: item.expires_at or 0,
            "messages": lambda item: item.messages_used,
            "images": lambda item: item.explicit_images_used,
            "cost": lambda item: item.estimated_cost_usd,
            "last_active": lambda item: item.last_active_at or 0,
        }
        summaries.sort(key=key_map.get(sort_key, key_map["last_active"]), reverse=desc)
        start = max(page - 1, 0) * page_size
        return summaries[start : start + page_size]

    def append_admin_audit_event(
        self,
        *,
        operator_ref: UserRef,
        action: str,
        result: str,
        reason: str,
        created_at: int,
        target_ref: UserRef | None = None,
        target_order_id: str | None = None,
    ) -> None:
        self.repositories.append_admin_audit_event(
            audit_id=uuid.uuid4().hex,
            operator_user_id=operator_ref.value,
            target_user_id=None if target_ref is None else int(target_ref.value),
            target_order_id=target_order_id,
            action=action,
            result=result,
            reason=reason,
            created_at=created_at,
        )

    def _limits_for(self, tier: Tier, metadata: dict[str, object]) -> UsageLimits:
        base = self.policy.limits_for(tier)
        messages = self._metadata_int(metadata, "messages_per_day", base.messages_per_day)
        images = self._metadata_int(metadata, "explicit_images_per_day", base.explicit_images_per_day)
        return UsageLimits(messages_per_day=messages, explicit_images_per_day=images)

    @staticmethod
    def _metadata_int(metadata: dict[str, object], key: str, default: int) -> int:
        raw = metadata.get(key)
        if raw is None:
            return default
        if isinstance(raw, (int, float, str)):
            return int(raw)
        return default

    @staticmethod
    def _daily_window(now_ts: int) -> tuple[int, int]:
        window_start = int(now_ts) - (int(now_ts) % 86_400)
        return window_start, window_start + 86_400

    @staticmethod
    def _is_premium_persona(persona: str) -> bool:
        return persona.endswith("_premium") or persona == "premium"

    @staticmethod
    def _is_explicit_persona(persona: str) -> bool:
        return persona in {"whore", "unhinged"}

    def _lifetime_entitlement_count(self) -> int:
        entitlements = getattr(self.repositories, "load_manual_lifetime_entitlement_count", None)
        if entitlements is not None:
            return int(entitlements())
        return 0


@dataclass(frozen=True, slots=True)
class LlmCostEstimate:
    model: str
    prompt_tokens: int
    completion_tokens: int
    usd_decimal: Decimal

    @property
    def usd(self) -> float:
        rounded = self.usd_decimal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return float(rounded)


@dataclass(frozen=True, slots=True)
class TokenPrice:
    prompt_usd_per_million: Decimal
    completion_usd_per_million: Decimal


@dataclass(frozen=True, slots=True)
class LlmCostEstimator:
    prices: dict[str, TokenPrice]

    @classmethod
    def default(cls) -> "LlmCostEstimator":
        return cls(
            prices={
                "x-ai/grok-4.1-fast": TokenPrice(
                    prompt_usd_per_million=Decimal("0.20"),
                    completion_usd_per_million=Decimal("0.50"),
                ),
            }
        )

    def estimate(self, model: str, *, prompt_tokens: int, completion_tokens: int) -> LlmCostEstimate:
        normalized_model = model.strip().lower()
        price = self.prices.get(normalized_model, TokenPrice(Decimal("0"), Decimal("0")))
        usd_decimal = (
            (Decimal(prompt_tokens) / Decimal(1_000_000) * price.prompt_usd_per_million)
            + (Decimal(completion_tokens) / Decimal(1_000_000) * price.completion_usd_per_million)
        )
        return LlmCostEstimate(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            usd_decimal=usd_decimal,
        )
