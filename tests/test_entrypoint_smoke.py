from __future__ import annotations

import sqlite3
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.core.monetization import PaymentStatus
from tests.support import FakeMessage


def index_exists(db_path: str, index_name: str) -> bool:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?",
            (index_name,),
        )
        return cur.fetchone() is not None
    finally:
        conn.close()


def table_exists(db_path: str, table_name: str) -> bool:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        return cur.fetchone() is not None
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_main_startup_runs(module_loader):
    module = module_loader("src.main")
    module.dp.start_polling = AsyncMock()
    module.run_http_server = AsyncMock()
    module.openrouter_client.aclose = AsyncMock()

    await module.main()

    module.dp.start_polling.assert_awaited_once_with(module.bot)
    module.run_http_server.assert_awaited_once()
    module.openrouter_client.aclose.assert_awaited_once()


@pytest.mark.parametrize(
    ("provider", "extra_env"),
    [
        ("openrouter", {}),
        ("openai", {"OPENAI_API_KEY": "oa-test-key"}),
        ("modelslab", {"MODELSLAB_API_KEY": "ms-test-key"}),
        ("together", {"TOG_API_KEY": "tog-test-key"}),
    ],
)
def test_supported_image_provider_configs_import(module_loader, provider, extra_env):
    module = module_loader("src.main", env={"IMAGE_BACKEND_PROVIDER": provider, **extra_env})

    assert module.IMAGE_BACKEND_PROVIDER == provider


@pytest.mark.asyncio
async def test_explicit_image_flow_rejects_openai_provider(module_loader):
    module = module_loader(
        "src.main",
        env={"IMAGE_BACKEND_PROVIDER": "openai", "OPENAI_API_KEY": "oa-test-key"},
    )

    with pytest.raises(RuntimeError, match="provider_not_allowed"):
        await module.generate_image_backend("prompt", mode="whore")


def test_legacy_openai_image_provider_import_still_works(module_loader):
    module = module_loader(
        "src.main",
        env={"IMAGE_BACKEND_PROVIDER": "openai", "OPENAI_API_KEY": "oa-test-key"},
    )

    assert module.IMAGE_BACKEND_PROVIDER == "openai"


@pytest.mark.asyncio
async def test_explicit_prompt_translation_rejects_openai_engine_before_network(module_loader):
    module = module_loader(
        "src.main",
        env={
            "PROMPT_TRANSLATION_ENABLED": "1",
            "PROMPT_TRANSLATION_ENGINE": "openai",
            "TRANSLATION_MODEL": "gpt-4o-mini",
        },
    )

    with pytest.raises(RuntimeError, match="Explicit translation blocked"):
        await module.maybe_translate_prompt("modelslab", "привет", mode="whore")


@pytest.mark.asyncio
async def test_explicit_prompt_translation_uses_openrouter_engine(module_loader, monkeypatch):
    module = module_loader(
        "src.main",
        env={
            "PROMPT_TRANSLATION_ENABLED": "1",
            "PROMPT_TRANSLATION_ENGINE": "openrouter",
            "TRANSLATION_MODEL": "x-ai/grok-4.1-fast",
        },
    )
    translator = AsyncMock(return_value="hello")
    monkeypatch.setattr(module, "call_openrouter", translator)

    translated = await module.maybe_translate_prompt("modelslab", "привет", mode="whore")

    assert translated == "hello"
    translator.assert_awaited_once()


@pytest.mark.asyncio
async def test_explicit_text_flow_rejects_blocked_policy_before_openrouter(
    module_loader,
    mark_mode_picked,
    monkeypatch,
):
    module = module_loader("src.main")
    module.init_db()
    mark_mode_picked(module, 1, mode="whore")
    user_ref = module.legacy_user_ref(1)
    module.DB_REPOSITORIES.upsert_entitlement(
        entitlement_id="explicit-policy-premium",
        user_ref=user_ref,
        plan_id="premium_30d",
        tier="premium",
        starts_at=1,
        expires_at=int(module.time.time()) + 200_000,
        source="manual:test",
        created_at=1,
    )
    module.DB_REPOSITORIES.set_explicit_consent(user_ref, accepted_at=1, source="telegram")
    monkeypatch.setattr(module, "keep_typing", AsyncMock())
    llm = AsyncMock(return_value=("blocked bypass", "stop", {"total_tokens": 1}))
    monkeypatch.setattr(module, "call_openrouter_with_meta", llm)

    class BlockingPolicy:
        def authorize_explicit(self, request):
            return SimpleNamespace(allowed=False, reasons=("provider_not_allowed",))

    monkeypatch.setattr(module, "ACCESS_POLICY", BlockingPolicy())

    with pytest.raises(RuntimeError, match="Explicit text request blocked"):
        await module.on_text(FakeMessage("hello"))

    llm.assert_not_awaited()


def test_chef_submode_keyboard_uses_readable_labels(module_loader):
    module = module_loader("src.main")

    keyboard = module.build_chef_submode_keyboard()
    labels = [row[0].text for row in keyboard.inline_keyboard]

    assert labels == [
        "🏠 Быстро по-домашнему",
        "🍽️ Как в ресторане",
        "🧠 Вспомнить контекст",
    ]


def test_unsupported_image_provider_fails_fast(module_loader):
    with pytest.raises(RuntimeError, match="Unsupported IMAGE_BACKEND_PROVIDER"):
        module_loader("src.main", env={"IMAGE_BACKEND_PROVIDER": "replicate"})


def test_init_db_is_idempotent_and_creates_llm_index(module_loader):
    module = module_loader("src.main")

    module.init_db()
    module.init_db()

    assert index_exists(module.DB_PATH, "idx_user_events_llm")


def test_init_db_creates_conversation_schema(module_loader):
    module = module_loader("src.main")

    module.init_db()

    assert table_exists(module.DB_PATH, "conversations")


def test_init_db_creates_sessions_schema(module_loader):
    module = module_loader("src.main")

    module.init_db()

    assert table_exists(module.DB_PATH, "sessions")


def test_main_import_uses_postgres_repository_when_configured(module_loader):
    module = module_loader(
        "src.main",
        env={
            "DB_BACKEND": "postgres",
            "DATABASE_URL": "postgresql://lina_app:secret@db.example/lina",
        },
    )

    from src.db.postgres import PostgresRepositories

    assert isinstance(module.DB_REPOSITORIES, PostgresRepositories)
    assert module.DB_REPOSITORIES.database_url == "postgresql://lina_app:secret@db.example/lina"


def test_main_exposes_stars_payment_helpers_without_tbank_buttons(module_loader):
    module = module_loader("src.main")

    keyboard = module.build_stars_buy_keyboard(lifetime_available=False)
    texts = [button.text for row in keyboard.inline_keyboard for button in row]

    assert texts == ["Premium 30d - 500 XTR", "Premium 1y - 2000 XTR"]
    assert hasattr(module, "fulfill_successful_stars_payment")


def test_tariff_status_renderer_hides_token_cost(module_loader):
    module = module_loader("src.main")
    snapshot = SimpleNamespace(
        effective_tier=SimpleNamespace(value="premium"),
        tier_expires_at=180_000,
        limits=SimpleNamespace(messages_per_day=300, explicit_images_per_day=20),
        usage=SimpleNamespace(messages_used=42, explicit_images_used=2),
        explicit_consent=True,
    )

    text = module.render_tariff_status(snapshot)

    assert "Остаток по тарифу" in text
    assert "Тариф: premium" in text
    assert "Сообщения сегодня: 42 / 300" in text
    assert "Картинки сегодня: 2 / 20" in text
    assert "18+: подтверждено" in text
    assert "token" not in text.lower()
    assert "cost" not in text.lower()


def test_operator_admin_parser_requires_allowlist_confirm_and_supports_admin_users(module_loader):
    module = module_loader("src.main", env={"OPERATOR_TELEGRAM_IDS": "9001,9002"})

    assert module.OPERATOR_TELEGRAM_IDS == frozenset({9001, 9002})
    assert module.is_operator(9001)
    assert not module.is_operator(42)

    from src.adapters.telegram.admin import parse_operator_command

    missing_confirm = parse_operator_command("/grant_access 61001 premium 30")
    grant = parse_operator_command("/grant_access 61001 trial 5 messages=12 images=1 confirm")
    listing = parse_operator_command("/admin_users q=lina tier=premium sort=cost desc page=2")

    assert not missing_confirm.confirmed
    assert grant.command == "grant_access"
    assert grant.target_user_id == 61001
    assert grant.tier == "trial"
    assert grant.days == 5
    assert grant.messages_per_day == 12
    assert grant.explicit_images_per_day == 1
    assert listing.command == "admin_users"
    assert listing.filters["q"] == "lina"
    assert listing.sort == "cost"
    assert listing.desc is True
    assert listing.page == 2


def test_operator_throttle_limits_sensitive_actions():
    from src.adapters.telegram.admin import OperatorThrottle

    throttle = OperatorThrottle(window_seconds=60, max_actions=5)

    assert [throttle.allow(9001, now_ts=1000) for _ in range(5)] == [True, True, True, True, True]
    assert throttle.allow(9001, now_ts=1000) is False
    assert throttle.allow(9001, now_ts=1061) is True


def test_admin_summary_renderer_includes_expected_fields():
    from src.adapters.telegram.admin import AdminUserSummary, render_admin_user_summaries

    text = render_admin_user_summaries(
        [
            AdminUserSummary(
                telegram_user_id=61001,
                name="Lina",
                username="lina",
                tier="premium",
                expires_at=180_000,
                payment_status="fulfilled",
                messages_used=42,
                explicit_images_used=2,
                estimated_cost_usd=0.7,
                explicit_consent=True,
                last_active_at=170_000,
                actions=("status", "revoke"),
            )
        ]
    )

    assert "61001" in text
    assert "lina" in text
    assert "premium" in text
    assert "fulfilled" in text
    assert "42" in text
    assert "2" in text
    assert "$0.70" in text
    assert "18+: yes" in text


@pytest.mark.asyncio
async def test_stars_buy_callback_sends_invoice_and_precheckout_validates(module_loader, monkeypatch):
    from tests.support import FakeCallbackQuery

    module = module_loader("src.main")
    module.init_db()
    sent: dict[str, object] = {}

    async def fake_send_invoice(**kwargs):
        sent.update(kwargs)

    monkeypatch.setattr(module.bot, "send_invoice", fake_send_invoice)
    callback = FakeCallbackQuery("buy_stars:premium_30d", user_id=61030)

    await module.cb_buy_stars(callback)

    assert sent["chat_id"] == callback.message.chat.id
    assert sent["currency"] == "XTR"
    assert sent["provider_token"] == ""
    payload = str(sent["payload"])
    assert "telegram_stars" in payload

    class FakePreCheckout:
        def __init__(self, invoice_payload: str) -> None:
            self.invoice_payload = invoice_payload
            self.answers: list[dict[str, object]] = []

        async def answer(self, **kwargs):
            self.answers.append(kwargs)

    pre_checkout = FakePreCheckout(payload)
    await module.on_pre_checkout_query(pre_checkout)

    assert pre_checkout.answers == [{"ok": True}]


@pytest.mark.asyncio
async def test_successful_stars_payment_handler_fulfills_order(module_loader, monkeypatch):
    from tests.support import FakeMessage

    module = module_loader("src.main")
    module.init_db()
    service = module._monetization_service()
    order = service.create_payment_order(
        module.legacy_user_ref(61031),
        module.PaymentProvider.TELEGRAM_STARS,
        module.ProductId.PREMIUM_30D,
        now_ts=100,
    )
    invoice = module.build_stars_invoice(order)
    monkeypatch.setattr(module.time, "time", lambda: 200)

    message = FakeMessage(user_id=61031)
    message.successful_payment = SimpleNamespace(
        invoice_payload=invoice.payload,
        telegram_payment_charge_id="stars-charge-handler",
    )

    await module.on_successful_payment(message)

    loaded = module.DB_REPOSITORIES.load_payment_order(order.order_id)
    assert loaded.status == PaymentStatus.FULFILLED
    assert loaded.entitlement_id
    assert "активирован" in message.answers[-1]["text"]


@pytest.mark.asyncio
async def test_operator_command_handlers_grant_list_and_revoke(module_loader, monkeypatch):
    from tests.support import FakeMessage

    module = module_loader("src.main", env={"OPERATOR_TELEGRAM_IDS": "9001"})
    module.init_db()
    monkeypatch.setattr(module.time, "time", lambda: 86_500)
    grant = FakeMessage("/grant_access 61032 trial 5 messages=12 images=1 confirm", user_id=9001)

    await module.cmd_grant_access(grant)

    assert "grant_ok" in grant.answers[-1]["text"]
    snapshot = module._monetization_service().get_access_snapshot(module.legacy_user_ref(61032), now_ts=86_600)
    assert snapshot.effective_tier == module.Tier.TRIAL
    assert snapshot.limits.messages_per_day == 12

    listing = FakeMessage("/admin_users tier=trial sort=messages desc page=1", user_id=9001)
    await module.cmd_admin_users(listing)

    assert "61032" in listing.answers[-1]["text"]
    assert "trial" in listing.answers[-1]["text"]

    revoke = FakeMessage("/revoke_access 61032 confirm", user_id=9001)
    await module.cmd_revoke_access(revoke)

    assert "revoke_ok" in revoke.answers[-1]["text"]
    after = module._monetization_service().get_access_snapshot(module.legacy_user_ref(61032), now_ts=86_700)
    assert after.effective_tier == module.Tier.FREE


@pytest.mark.asyncio
async def test_operator_command_rejects_non_operator(module_loader):
    from tests.support import FakeMessage

    module = module_loader("src.main", env={"OPERATOR_TELEGRAM_IDS": "9001"})
    module.init_db()
    message = FakeMessage("/grant_access 61033 trial 5 confirm", user_id=42)

    await module.cmd_grant_access(message)

    assert "оператору" in message.answers[-1]["text"]


def test_runtime_monetization_helpers_gate_personas_and_record_usage(module_loader):
    module = module_loader("src.main")
    module.init_db()
    user_id = 61020

    premium = module.authorize_runtime_persona(user_id, "coach_premium", now_ts=120_000)
    explicit = module.authorize_runtime_persona(user_id, "whore", now_ts=120_000)

    assert not premium.allowed
    assert premium.reasons == ("premium_required",)
    assert not explicit.allowed
    assert explicit.reasons == ("explicit_tier_required",)

    module.record_runtime_message_usage(user_id, now_ts=120_000)
    snapshot = module.get_runtime_access_snapshot(user_id, now_ts=120_000)

    assert snapshot.usage.messages_used == 1


def test_runtime_explicit_image_gate_blocks_after_limit(module_loader):
    module = module_loader("src.main")
    module.init_db()
    user_id = 61021
    user_ref = module.legacy_user_ref(user_id)
    module.DB_REPOSITORIES.upsert_entitlement(
        entitlement_id="runtime-premium",
        user_ref=user_ref,
        plan_id="premium_30d",
        tier="premium",
        starts_at=1,
        expires_at=200_000,
        source="manual:test",
        created_at=1,
    )
    module.DB_REPOSITORIES.set_explicit_consent(user_ref, accepted_at=1, source="telegram")

    for _ in range(20):
        module.record_runtime_explicit_image_usage(user_id, now_ts=130_000)

    decision = module.authorize_runtime_explicit_image(user_id, now_ts=130_000)

    assert not decision.allowed
    assert decision.reasons == ("explicit_image_limit_reached",)
