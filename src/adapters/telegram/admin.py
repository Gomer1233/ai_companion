from __future__ import annotations

from dataclasses import dataclass, field

from src.core.monetization import AdminUserSummary


@dataclass(frozen=True, slots=True)
class OperatorCommand:
    command: str
    target_user_id: int | None = None
    target_order_id: str | None = None
    tier: str | None = None
    days: int | None = None
    confirmed: bool = False
    messages_per_day: int | None = None
    explicit_images_per_day: int | None = None
    filters: dict[str, str] = field(default_factory=dict)
    sort: str | None = None
    desc: bool = False
    page: int = 1


class OperatorThrottle:
    def __init__(self, *, window_seconds: int = 60, max_actions: int = 5) -> None:
        self.window_seconds = window_seconds
        self.max_actions = max_actions
        self._events: dict[int, list[int]] = {}

    def allow(self, operator_user_id: int, *, now_ts: int) -> bool:
        events = [ts for ts in self._events.get(operator_user_id, []) if ts > now_ts - self.window_seconds]
        if len(events) >= self.max_actions:
            self._events[operator_user_id] = events
            return False
        events.append(now_ts)
        self._events[operator_user_id] = events
        return True


def parse_operator_command(text: str) -> OperatorCommand:
    parts = [part for part in text.strip().split() if part]
    if not parts:
        return OperatorCommand(command="")
    command = parts[0].lstrip("/")
    confirmed = "confirm" in parts[1:]
    if command == "grant_access":
        if len(parts) < 3:
            return OperatorCommand(command=command, confirmed=confirmed)
        target_user_id = int(parts[1])
        tier = parts[2].lower()
        days: int | None = None
        if len(parts) > 3 and parts[3] != "confirm" and "=" not in parts[3]:
            days = None if parts[3].lower() == "lifetime" else int(parts[3])
        kv = _kv(parts[1:])
        return OperatorCommand(
            command=command,
            target_user_id=target_user_id,
            tier=tier,
            days=days,
            confirmed=confirmed,
            messages_per_day=_int_or_none(kv.get("messages")),
            explicit_images_per_day=_int_or_none(kv.get("images")),
        )
    if command in {"revoke_access", "user_status", "usage_status"}:
        return OperatorCommand(
            command=command,
            target_user_id=int(parts[1]) if len(parts) > 1 else None,
            confirmed=confirmed,
        )
    if command == "fulfill_order":
        return OperatorCommand(
            command=command,
            target_order_id=parts[1] if len(parts) > 1 else None,
            confirmed=confirmed,
        )
    if command == "admin_users":
        kv = _kv(parts[1:])
        filters = {key: value for key, value in kv.items() if key in {"q", "tier"}}
        return OperatorCommand(
            command=command,
            filters=filters,
            sort=kv.get("sort"),
            desc="desc" in parts[1:],
            page=int(kv.get("page", "1")),
        )
    return OperatorCommand(command=command, confirmed=confirmed)


def render_admin_user_summaries(summaries: list[AdminUserSummary]) -> str:
    lines: list[str] = []
    for item in summaries:
        username = f"@{item.username}" if item.username else "-"
        consent = "yes" if item.explicit_consent else "no"
        actions = ",".join(item.actions)
        lines.append(
            f"{item.telegram_user_id} {item.name} {username} tier={item.tier} expires={item.expires_at} "
            f"payment={item.payment_status} messages={item.messages_used} images={item.explicit_images_used} "
            f"cost=${item.estimated_cost_usd:.2f} 18+: {consent} last={item.last_active_at} actions={actions}"
        )
    return "\n".join(lines)


def _kv(parts: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for part in parts:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        result[key.strip().lower()] = value.strip()
    return result


def _int_or_none(value: str | None) -> int | None:
    return None if value is None else int(value)
