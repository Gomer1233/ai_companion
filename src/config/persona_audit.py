from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class PersonaAuditRecord:
    persona: str
    verdict: str
    owner: str
    risk_class: str
    default_tier: str
    kill_switch_key: str
    category: str
    catalog_id: str
    title: str
    catalog_order: int
    notes: str


@dataclass(frozen=True, slots=True)
class AlphaCatalogItem:
    id: str
    mode: str
    title: str
    category: str
    default_tier: str
    risk_class: str


PERSONA_AUDIT_RECORDS: tuple[PersonaAuditRecord, ...] = (
    PersonaAuditRecord(
        persona="basic",
        verdict="launch-approved",
        owner="product",
        risk_class="low",
        default_tier="free",
        kill_switch_key="LINA_PERSONA_BASIC_ENABLED",
        category="assistant",
        catalog_id="basic",
        title="AI Assistant",
        catalog_order=10,
        notes="Core utility mode with repeatable general-purpose value.",
    ),
    PersonaAuditRecord(
        persona="brainstorm",
        verdict="launch-approved",
        owner="product",
        risk_class="low",
        default_tier="free",
        kill_switch_key="LINA_PERSONA_BRAINSTORM_ENABLED",
        category="assistant",
        catalog_id="brainstorm",
        title="Brainstorm",
        catalog_order=20,
        notes="Repeatable idea critique and planning workflow.",
    ),
    PersonaAuditRecord(
        persona="psychologist",
        verdict="launch-approved",
        owner="product",
        risk_class="sensitive",
        default_tier="free",
        kill_switch_key="LINA_PERSONA_PSYCHOLOGIST_ENABLED",
        category="wellbeing",
        catalog_id="psychologist",
        title="Psychologist",
        catalog_order=30,
        notes="Useful support mode; must keep non-clinical positioning.",
    ),
    PersonaAuditRecord(
        persona="coach_premium",
        verdict="launch-approved",
        owner="product",
        risk_class="low",
        default_tier="premium",
        kill_switch_key="LINA_PERSONA_COACH_ENABLED",
        category="practice",
        catalog_id="coach",
        title="Coach",
        catalog_order=40,
        notes="Premium coach is the alpha coach surface; basic coach is superseded.",
    ),
    PersonaAuditRecord(
        persona="oldschool_rep",
        verdict="launch-approved",
        owner="product",
        risk_class="low",
        default_tier="free",
        kill_switch_key="LINA_PERSONA_OLDSCHOOL_REP_ENABLED",
        category="practice",
        catalog_id="oldschool_rep",
        title="Rap Lyrics",
        catalog_order=50,
        notes="Creative practice mode with dedicated submode UX.",
    ),
    PersonaAuditRecord(
        persona="chef",
        verdict="launch-approved",
        owner="product",
        risk_class="low",
        default_tier="free",
        kill_switch_key="LINA_PERSONA_CHEF_ENABLED",
        category="life",
        catalog_id="chef",
        title="Chef",
        catalog_order=60,
        notes="Repeatable household and restaurant-style cooking use cases.",
    ),
    PersonaAuditRecord(
        persona="financial",
        verdict="launch-approved",
        owner="product",
        risk_class="regulated",
        default_tier="free",
        kill_switch_key="LINA_PERSONA_FINANCIAL_ENABLED",
        category="life",
        catalog_id="financial",
        title="Financial Consultant",
        catalog_order=70,
        notes="Useful life-planning mode; must keep risk disclaimers in prompt.",
    ),
    PersonaAuditRecord(
        persona="doctor",
        verdict="launch-approved",
        owner="product",
        risk_class="regulated",
        default_tier="free",
        kill_switch_key="LINA_PERSONA_DOCTOR_ENABLED",
        category="life",
        catalog_id="doctor",
        title="Doctor",
        catalog_order=80,
        notes="Useful triage mode; must not diagnose or replace a clinician.",
    ),
    PersonaAuditRecord(
        persona="pet_behaviorist",
        verdict="launch-approved",
        owner="product",
        risk_class="regulated",
        default_tier="free",
        kill_switch_key="LINA_PERSONA_PET_BEHAVIORIST_ENABLED",
        category="life",
        catalog_id="pet_behaviorist",
        title="Pet Behaviorist",
        catalog_order=90,
        notes="Repeatable pet-care and behavior planning mode.",
    ),
    PersonaAuditRecord(
        persona="oldtimer",
        verdict="launch-approved",
        owner="product",
        risk_class="low",
        default_tier="free",
        kill_switch_key="LINA_PERSONA_OLDTIMER_ENABLED",
        category="entertainment",
        catalog_id="oldtimer",
        title="Oldtimer",
        catalog_order=100,
        notes="Kept as a characterful entertainment mode.",
    ),
    PersonaAuditRecord(
        persona="whore",
        verdict="launch-approved-gated",
        owner="product",
        risk_class="explicit",
        default_tier="premium",
        kill_switch_key="LINA_PERSONA_WHORE_ENABLED",
        category="explicit",
        catalog_id="whore",
        title="Flirt 18+",
        catalog_order=110,
        notes="Explicit mode gated by tier, consent, policy, and kill switch.",
    ),
    PersonaAuditRecord(
        persona="unhinged",
        verdict="launch-approved-gated",
        owner="product",
        risk_class="explicit",
        default_tier="premium",
        kill_switch_key="LINA_PERSONA_UNHINGED_ENABLED",
        category="explicit",
        catalog_id="unhinged",
        title="Unhinged 18+",
        catalog_order=120,
        notes="Explicit adjacent entertainment mode; gated for alpha.",
    ),
    PersonaAuditRecord(
        persona="coach",
        verdict="superseded",
        owner="product",
        risk_class="low",
        default_tier="free",
        kill_switch_key="LINA_PERSONA_COACH_LEGACY_ENABLED",
        category="practice",
        catalog_id="coach_legacy",
        title="Coach Legacy",
        catalog_order=900,
        notes="Superseded by coach_premium, which is exposed as Coach.",
    ),
    PersonaAuditRecord(
        persona="alco",
        verdict="deferred",
        owner="product",
        risk_class="medium",
        default_tier="free",
        kill_switch_key="LINA_PERSONA_ALCO_ENABLED",
        category="entertainment",
        catalog_id="alco",
        title="Drinking Companion",
        catalog_order=910,
        notes="Gimmick entertainment mode; not useful enough for alpha catalog.",
    ),
    PersonaAuditRecord(
        persona="communist",
        verdict="deferred",
        owner="product",
        risk_class="medium",
        default_tier="free",
        kill_switch_key="LINA_PERSONA_COMMUNIST_ENABLED",
        category="entertainment",
        catalog_id="communist",
        title="Soviet Communist",
        catalog_order=920,
        notes="Roleplay mode deferred until catalog has an experimental section.",
    ),
    PersonaAuditRecord(
        persona="conspiro",
        verdict="deferred",
        owner="product",
        risk_class="medium",
        default_tier="free",
        kill_switch_key="LINA_PERSONA_CONSPIRO_ENABLED",
        category="entertainment",
        catalog_id="conspiro",
        title="Conspiracy Theorist",
        catalog_order=930,
        notes="Potential misinformation risk; hidden for alpha.",
    ),
)


_VISIBLE_VERDICTS = {"launch-approved", "launch-approved-gated"}
_FALSE_VALUES = {"0", "false", "off", "no", "disabled"}


def build_alpha_launch_catalog(env: Mapping[str, str] | None = None) -> tuple[AlphaCatalogItem, ...]:
    source = os.environ if env is None else env
    records = [
        record
        for record in PERSONA_AUDIT_RECORDS
        if record.verdict in _VISIBLE_VERDICTS and _persona_enabled(record, source)
    ]
    return tuple(
        AlphaCatalogItem(
            id=record.catalog_id,
            mode=record.persona,
            title=record.title,
            category=record.category,
            default_tier=record.default_tier,
            risk_class=record.risk_class,
        )
        for record in sorted(records, key=lambda item: item.catalog_order)
    )


def _persona_enabled(record: PersonaAuditRecord, env: Mapping[str, str]) -> bool:
    raw = env.get(record.kill_switch_key)
    if raw is None:
        return True
    return raw.strip().lower() not in _FALSE_VALUES
