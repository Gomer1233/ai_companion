from __future__ import annotations

import argparse
import time
import uuid
from pathlib import Path

from src.app.settings import Settings
from src.db.factory import create_repositories
from src.db.repositories import legacy_user_ref


def revoke_explicit_consent(
    *,
    target_user_id: int,
    operator_id: str,
    reason: str,
    now_ts: int,
    project_root: Path | None = None,
) -> str:
    settings = Settings.from_env(project_root=project_root or Path(__file__).parent.parent)
    repositories = create_repositories(settings, include_relationship_state=True)
    user_ref = legacy_user_ref(target_user_id)
    consent = repositories.revoke_explicit_consent(
        user_ref,
        revoked_at=now_ts,
        source=f"operator:{operator_id}:revoke",
    )
    result = "no_active_consent" if consent is None or consent.revoked_at != now_ts else "revoked"
    repositories.append_admin_audit_event(
        audit_id=uuid.uuid4().hex,
        operator_user_id=operator_id,
        target_user_id=int(user_ref.value),
        action="explicit_consent_revoke",
        result=result,
        reason=reason,
        created_at=now_ts,
        metadata={"source": "revoke_explicit_consent.py"},
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Revoke Lina explicit 18+ consent for one Telegram user id.")
    parser.add_argument("telegram_user_id", type=int)
    parser.add_argument("--operator-id", required=True)
    parser.add_argument("--reason", default="support_request")
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args(argv)
    if not args.confirm:
        parser.error("add --confirm to revoke explicit consent")

    result = revoke_explicit_consent(
        target_user_id=args.telegram_user_id,
        operator_id=args.operator_id,
        reason=args.reason,
        now_ts=int(time.time()),
    )
    print(f"{result}: user={args.telegram_user_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
