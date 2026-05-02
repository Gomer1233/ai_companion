from __future__ import annotations

from src.core.access_policy import AccessPolicyService, ExplicitCapability, LaunchManifestRecord


ALPHA_LAUNCH_MODEL_MANIFEST: tuple[LaunchManifestRecord, ...] = (
    LaunchManifestRecord(
        persona="whore",
        provider="openrouter",
        model="x-ai/grok-4.1-fast",
        capabilities=(ExplicitCapability.TEXT,),
        enabled=True,
    ),
    LaunchManifestRecord(
        persona="whore",
        provider="modelslab",
        model="MODELSLAB_MODEL_ID",
        capabilities=(ExplicitCapability.IMAGE,),
        enabled=True,
    ),
)


def validate_alpha_launch_manifest(
    records: tuple[LaunchManifestRecord, ...] = ALPHA_LAUNCH_MODEL_MANIFEST,
    service: AccessPolicyService | None = None,
) -> None:
    policy = service or AccessPolicyService.alpha_default()
    for record in records:
        record.validate(policy)
