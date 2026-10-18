"""Immutable research-session manifests for autoresearch runs."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.config import settings
from src.core.legacy_alias import (
    is_known_model_type,
    model_type_to_skill_id,
    skill_id_to_model_type,
)
from src.core.service_preflight import build_not_run_preflight, sanitize_service_url
from src.core.skill_paths import session_workspace_path

#: Current manifest artifact schema version (ARC-012 P7-002). v3 makes the
#: canonical ``skill_id`` authoritative and required; the legacy
#: ``model_type`` becomes an optional, *closed-vocabulary* alias
#: (``direction``/``volatility``/``rl`` or empty — D1: frozen history,
#: writable never). v2 added the canonical dual-shape fields; v1 predates
#: them. Both remain readable and are normalized to v3 on load
#: (forward-compat).
CURRENT_SCHEMA_VERSION = "research_session_manifest.v3"
_KNOWN_SCHEMA_VERSIONS = {
    "research_session_manifest.v1",
    "research_session_manifest.v2",
    CURRENT_SCHEMA_VERSION,
}

#: Sections every manifest must carry regardless of skill category — the
#: universal research-session contract (budget, policy, preflight, runtime).
_SKILL_PROFILE_SECTIONS = (
    "budget",
    "promotion_policy",
    "preflight",
    "runtime",
)

#: Additional sections only a legacy-ML (``model_type`` trio) manifest must
#: carry. A generative/optimization/… skill has no ``roster``/``tsfm`` —
#: demanding them would force fabricated provenance (ARC-012 P7-004).
_ML_PROFILE_SECTIONS = _SKILL_PROFILE_SECTIONS + (
    "data_window",
    "baseline_config",
    "roster",
    "tsfm",
    "adaptive_features",
    "split_ids",
    "cost_model",
    "gate_bundle",
    "service_urls",
)

#: Legacy-ML sections that a skill-driven (v3) manifest leaves ``None``.
#: Kept as model fields so v1/v2 artifacts round-trip unchanged.
_ML_ONLY_SECTION_FIELDS = (
    "data_window",
    "baseline_config",
    "roster",
    "tsfm",
    "adaptive_features",
    "split_ids",
    "cost_model",
    "gate_bundle",
)


class ResearchSessionManifest(BaseModel):
    """Complete immutable manifest for one autonomous research session."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = CURRENT_SCHEMA_VERSION
    research_id: str
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    instrument: str
    timeframe: str
    #: D1 (ARC-012 §2): closed legacy vocabulary — a known legacy short name
    #: for ML skills, or ``""`` for every skill without one. Never a skill id,
    #: never free text; nothing runtime branches on it.
    model_type: str = Field(default="", pattern=r"^(direction|volatility|rl)$|^$")
    objective: str
    model_family: str
    # P7-003/P7-004: ML-only sections are Optional so a skill-driven (v3)
    # manifest can honestly omit them instead of fabricating ML provenance.
    # Legacy v1/v2 manifests always carry them; the profile validator still
    # enforces their presence for the legacy-ML profile.
    data_window: Optional[Dict[str, Any]] = None
    baseline_config: Optional[Dict[str, Any]] = None
    roster: Optional[Dict[str, Any]] = None
    tsfm: Optional[Dict[str, Any]] = None
    adaptive_features: Optional[Dict[str, Any]] = None
    split_ids: Optional[Dict[str, Any]] = None
    cost_model: Optional[Dict[str, Any]] = None
    gate_bundle: Optional[Dict[str, Any]] = None
    budget: Dict[str, Any]
    max_iterations: int = Field(ge=1)
    timeout_s: int = Field(ge=0)
    mlflow_experiment: Optional[str] = None
    promotion_policy: Dict[str, Any]
    service_urls: Dict[str, str] = Field(default_factory=dict)
    preflight: Dict[str, Any]
    runtime: Dict[str, Any]
    hpo: Dict[str, Any] = Field(default_factory=dict)
    focus_hint: Optional[str] = None
    manifest_hash: Optional[str] = None
    # ARC-011 P4-002, revised by review C3 (2026-08-15): per-session
    # anti-forgery nonce slot (W11). The nonce itself is generated
    # out-of-band by ``SessionManager._build_manifest_payload`` and NEVER
    # enters the artifact (the artifact is written into the agent-readable
    # session workspace — see the C3 finding). New manifests carry ``null``
    # here; the field is kept so the v2 schema shape is unchanged and legacy
    # manifests that embedded a value still load.
    session_nonce: Optional[str] = None
    # ARC-011 P3-019 (manifest v2): the canonical dual-shape fields. They mirror
    # the API's dual-shape session responses (§7.7) so the persisted artifact is
    # self-describing without a read-time projection. ``model_type`` →
    # ``skill_id`` via the legacy_alias registry; ``instrument`` → ``subject_id``;
    # ``timeframe`` → ``variant`` (the ResearchConfig derivation rules, P2-017).
    # Optional + derived in ``_derive_canonical_fields`` so v1 manifests (which
    # never carried these) load and back-fill cleanly.
    skill_id: Optional[str] = None
    subject_id: Optional[str] = None
    variant: Optional[str] = None
    # ARC-012 P7-003 (manifest v3): the skill-sourced section — everything the
    # session manifest claims about *this* skill comes from its SKILL.yaml
    # (phase ids, primary metric, promotion-target kind, workspace template),
    # never invented by the builder. Absent on legacy-ML manifests, which keep
    # their byte-identical v2 shape.
    skill: Optional[Dict[str, Any]] = None
    # Resolved run spec: the canonical immutable inputs (resolved parameters
    # and defaults, objective/policy, content digests, runtime identity,
    # effective configuration, secret references). Optional so legacy
    # artifacts — which never recorded one — load unchanged and are
    # *reported* as missing provenance rather than backfilled.
    run_spec: Optional[Dict[str, Any]] = None

    @field_validator("schema_version", mode="before")
    @classmethod
    def _accept_known_schema_versions(cls, value: Any) -> Any:
        """Forward-compat read: accept v1/v2 manifests, normalize to v3.

        Persisted v1/v2 manifests (written before P7-002) carry their own
        ``schema_version``. They are loaded unchanged and re-stamped as v3 on
        the round-trip so a migrated artifact carries the canonical surface.
        Unknown prefixes raise a field-located error rather than silently
        degrading (R3 back-compat).
        """
        if value is None:
            return CURRENT_SCHEMA_VERSION
        if isinstance(value, str) and value in _KNOWN_SCHEMA_VERSIONS:
            return CURRENT_SCHEMA_VERSION
        raise ValueError(
            f"unsupported manifest schema_version {value!r}; expected one of "
            f"{sorted(_KNOWN_SCHEMA_VERSIONS)}"
        )

    @field_validator("instrument", "timeframe", "objective", "model_family")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("field must not be blank")
        return value.strip()

    @model_validator(mode="after")
    def _require_manifest_sections(self) -> "ResearchSessionManifest":
        # P7-004: section requirements are profile-based. A v3 manifest that
        # carries the skill-sourced ``skill`` section validates against the
        # universal profile (any non-ML category); a legacy-ML manifest (no
        # skill section, ``model_type`` trio) must still satisfy the full ML
        # set — including ``roster``/``tsfm`` (regression-asserted).
        required = (
            _SKILL_PROFILE_SECTIONS if self.skill is not None
            else _ML_PROFILE_SECTIONS
        )
        missing = [name for name in required if not getattr(self, name)]
        if missing:
            raise ValueError(f"manifest missing required section(s): {missing}")
        # P3-019: back-fill canonical dual-shape fields from the legacy trio so a
        # v1 manifest (which never carried skill_id/subject_id/variant) round-
        # trips through read → v3 with the canonical surface populated. The
        # derivation rules mirror ResearchConfig (P2-017): model_type → skill_id
        # via legacy_alias; instrument → subject_id; timeframe → variant.
        if not self.skill_id:
            object.__setattr__(
                self, "skill_id", model_type_to_skill_id(self.model_type)
            )
        if not self.subject_id:
            object.__setattr__(self, "subject_id", self.instrument)
        if not self.variant:
            object.__setattr__(self, "variant", self.timeframe)
        # P7-002: the canonical skill identity is required — a manifest that
        # resolves to no skill at all names nothing and cannot run.
        if not (self.skill_id or "").strip():
            raise ValueError(
                "manifest requires a non-blank skill_id (every session must "
                "name an installed skill; legacy sessions must carry a known "
                "model_type alias)"
            )
        return self

    def canonical_json(self, *, include_hash: bool = True) -> str:
        payload = self.model_dump(mode="json")
        if not include_hash:
            payload.pop("manifest_hash", None)
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def with_hash(self) -> "ResearchSessionManifest":
        payload = self.model_copy(update={"manifest_hash": None})
        digest = hashlib.sha256(
            payload.canonical_json(include_hash=False).encode("utf-8")
        ).hexdigest()
        return payload.model_copy(update={"manifest_hash": digest})


from src.core.run_spec import build_run_spec, skill_package_dir


def _schema_dict(schema: Any) -> Optional[Dict[str, Any]]:
    if schema is None:
        return None
    if hasattr(schema, "model_dump"):
        return schema.model_dump()
    if isinstance(schema, Mapping):
        return dict(schema)
    return None


def _skill_package_dir(skill_id: str) -> Optional[str]:
    return skill_package_dir(skill_id)


def _canonical_digest(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        payload = value.model_dump()
    elif isinstance(value, Mapping):
        payload = dict(value)
    else:
        return None
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def build_research_manifest(
    *,
    research_id: str,
    instrument: str,
    timeframe: str,
    model_type: str = "",
    tag: str,
    quick_mode: bool,
    max_iterations: int,
    max_budget_usd: float,
    timeout_s: int,
    focus_hint: Optional[str],
    overrides: Optional[Dict[str, Any]] = None,
    # ARC-012 P7-005: the canonical skill identity. When given, it is
    # authoritative and the legacy ``model_type`` alias is derived here —
    # the single place that knows the translation.
    skill_id: Optional[str] = None,
    skill_params: Optional[Dict[str, Any]] = None,
) -> ResearchSessionManifest:
    """Build and validate a complete manifest from request/server state."""

    model_type, skill_id = _resolve_identity(model_type=model_type, skill_id=skill_id)

    if is_known_model_type(model_type) and _lookup_skill_manifest(skill_id) is None:
        # Legacy ML trio with no installed skill manifest: keep the incumbent
        # ML sections byte-identical (parity fixtures depend on them).
        defaults = _ml_manifest_defaults(
            research_id=research_id,
            instrument=instrument,
            timeframe=timeframe,
            model_type=model_type,
            skill_id=skill_id or model_type_to_skill_id(model_type),
            tag=tag,
            quick_mode=quick_mode,
            max_iterations=max_iterations,
            max_budget_usd=max_budget_usd,
            timeout_s=timeout_s,
            focus_hint=focus_hint,
        )
    else:
        skill_manifest = _lookup_skill_manifest(skill_id)
        if skill_manifest is None:
            raise ValueError(
                f"skill_id {skill_id!r} is not registered; a manifest must be "
                "sourced from an installed skill (add skills/<id>/ and reload) "
                "or carry a legacy model_type alias"
            )
        defaults = _skill_manifest_defaults(
            research_id=research_id,
            instrument=instrument,
            timeframe=timeframe,
            skill_id=skill_manifest.id,
            tag=tag,
            quick_mode=quick_mode,
            max_iterations=max_iterations,
            max_budget_usd=max_budget_usd,
            timeout_s=timeout_s,
            focus_hint=focus_hint,
            skill_manifest=skill_manifest,
            skill_params=skill_params,
        )

    payload = _deep_merge(defaults, overrides or {})
    if payload.get("research_id") != research_id:
        raise ValueError("manifest research_id must match server session id")
    if payload.get("instrument") != instrument:
        raise ValueError("manifest instrument must match request instrument")
    if payload.get("timeframe") != timeframe:
        raise ValueError("manifest timeframe must match request timeframe")
    if payload.get("model_type") != model_type:
        raise ValueError("manifest model_type must match request model_type")
    return ResearchSessionManifest(**payload).with_hash()


def _resolve_identity(
    *, model_type: str, skill_id: Optional[str]
) -> tuple[str, str]:
    """Resolve (legacy ``model_type``, canonical ``skill_id``).

    ``skill_id`` wins when both are given (P7-005); the legacy alias — if the
    skill has one — is derived here. A ``model_type`` that is not a known
    legacy alias is treated as a canonical skill id (the P3-013 identity
    fallback) and yields ``model_type=""`` per D1.
    """
    if not skill_id:
        skill_id = model_type_to_skill_id(model_type or "")
    if not skill_id:
        raise ValueError(
            "manifest identity requires an installed skill_id (or a legacy "
            f"model_type alias); got model_type={model_type!r}, "
            f"skill_id={skill_id!r}"
        )
    legacy = skill_id_to_model_type(skill_id)
    return (legacy if is_known_model_type(legacy) else "", skill_id)


def _lookup_skill_manifest(skill_id: Optional[str]) -> Any:
    """Resolve a skill id against the registry; ``None`` when unresolvable."""
    if not skill_id:
        return None
    try:
        from src.core.skill_registry import default_registry

        return default_registry.get(skill_id)
    except Exception:
        return None


def _ml_manifest_defaults(
    *,
    research_id: str,
    instrument: str,
    timeframe: str,
    model_type: str,
    skill_id: str,
    tag: str,
    quick_mode: bool,
    max_iterations: int,
    max_budget_usd: float,
    timeout_s: int,
    focus_hint: Optional[str],
) -> Dict[str, Any]:
    """The incumbent legacy-ML section set — byte-identical to the v2 builder
    (parity fixtures depend on it; P7-003 keeps this branch untouched)."""
    instrument_under = instrument.replace("-", "_")
    return {
        "research_id": research_id,
        "instrument": instrument,
        "timeframe": timeframe,
        "model_type": model_type,
        # P3-019: canonical dual-shape fields, populated alongside the legacy
        # trio so the persisted manifest artifact is self-describing. The model
        # validator back-fills these if absent (v1 round-trip path).
        "skill_id": skill_id,
        "subject_id": instrument,
        "variant": timeframe,
        "objective": _default_objective(model_type),
        "model_family": _default_model_family(model_type),
        "data_window": {
            "source": "experiment_matrix_v1",
            "matrix_path": "reports/direction-tuning/experiment_matrix_v1.yaml",
            "instrument": instrument,
            "timeframe": timeframe,
            "quick_mode": quick_mode,
        },
        "baseline_config": {
            "tag": tag,
            "workspace_config": (
                f"runs/autotuner/{instrument_under}_{timeframe}/"
                f"{model_type}/train.yaml"
            ),
        },
        "roster": {
            "source": "config_snapshot",
            "model_type": model_type,
        },
        "tsfm": {
            "enabled": False,
            "source": None,
            "weights": None,
            "license": None,
        },
        "adaptive_features": {
            "enabled": False,
            "version": None,
        },
        "split_ids": {
            "source": "experiment_matrix_v1",
            "value": None,
        },
        "cost_model": {
            "source": "experiment_matrix_v1",
            "fee_slippage_spread": "matrix_defined",
        },
        "gate_bundle": {
            "id": "development_direction_prediction_v1",
            "version": 1,
            "path": "reports/direction-tuning/promotion/development_gate_bundle_v1.yaml",
        },
        "budget": {
            "max_budget_usd": max_budget_usd,
            "quick_mode": quick_mode,
        },
        "max_iterations": max_iterations,
        "timeout_s": timeout_s,
        "mlflow_experiment": f"autoresearch/{instrument_under}/{timeframe}/{model_type}",
        "promotion_policy": {
            "scope": "development",
            "live_production_promotion_allowed": False,
            "auc_only_promotion_allowed": False,
        },
        "service_urls": {
            "mlflow_tracking": sanitize_service_url(settings.mlflow_tracking_uri),
            "mlflow_external": sanitize_service_url(settings.mlflow_external_url),
        },
        "preflight": build_not_run_preflight(model_type=model_type),
        "runtime": {
            "environment": settings.environment,
            "workspace_root": settings.workspace_root,
            "runs_dir": settings.runs_dir,
            "db_path": settings.db_path,
            "host_configs_path": settings.host_configs_path,
            "anthropic_model": settings.anthropic_model,
        },
        "hpo": {
            "enabled": False,
            "trials": None,
            "timesteps": None,
        },
        "focus_hint": focus_hint,
        # ARC-011 review C3 (2026-08-15): the per-session anti-forgery nonce
        # is generated OUT-OF-BAND (SessionManager._build_manifest_payload)
        # and deliberately NOT placed in the manifest. The manifest artifact
        # is written into the agent-readable session workspace; embedding the
        # nonce there handed the W11 adversary (the agent) the very secret the
        # contract defends against. ``session_nonce`` stays in the schema
        # (always null in new artifacts) so the v2 shape is unchanged.
    }


def _skill_manifest_defaults(
    *,
    research_id: str,
    instrument: str,
    timeframe: str,
    skill_id: str,
    tag: str,
    quick_mode: bool,
    max_iterations: int,
    max_budget_usd: float,
    timeout_s: int,
    focus_hint: Optional[str],
    skill_manifest: Any,
    skill_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Skill-driven sections (ARC-012 P7-003): everything is sourced from the
    skill's SKILL.yaml — no invented ML artifacts. A manifest must never
    claim artefacts the skill does not produce."""
    workspace_rel = session_workspace_path(
        skill_manifest,
        skill_id=skill_id,
        subject_id=instrument,
        variant=timeframe,
    )
    promotion_scopes = [
        scope.id
        for scope in (getattr(skill_manifest.promotion_target, "scopes", None) or [])
    ]
    run_spec = build_run_spec(
        skill_params=skill_params or {},
        param_schema=_schema_dict(getattr(skill_manifest, "param_schema", None)),
        skill_id=skill_id,
        skill_version=getattr(skill_manifest, "version", None),
        skill_dir=_skill_package_dir(skill_id),
        objective_policy={
            "objective": _default_objective(skill_id),
            "goal": getattr(skill_manifest.metric_schema, "goal", None),
            "direction": getattr(
                skill_manifest.metric_schema.primary, "direction", None,
            ),
            "epsilon": settings.global_stagnation_epsilon,
        },
        policy={
            "command_policy_sha256": _canonical_digest(
                getattr(skill_manifest, "command_policy", None)
            ),
            "parameter_bindings_sha256": _canonical_digest(
                getattr(skill_manifest, "parameter_bindings", None)
            ),
        },
        effective_config={
            "environment": settings.environment,
            "anthropic_model": settings.anthropic_model,
            "quick_mode": quick_mode,
            "max_iterations": max_iterations,
            "max_budget_usd": max_budget_usd,
            "timeout_s": timeout_s,
        },
    )
    return {
        "research_id": research_id,
        "instrument": instrument,
        "timeframe": timeframe,
        "model_type": "",  # D1: no legacy alias for skill-driven sessions
        "skill_id": skill_id,
        "subject_id": instrument,
        "variant": timeframe,
        "objective": _default_objective(skill_id),
        "model_family": _default_model_family(skill_id),
        # ``baseline_config`` carries only what is real: the request tag. The
        # ML branch's ``workspace_config`` train.yaml pointer is intentionally
        # absent — this skill produces no train.yaml.
        "baseline_config": {"tag": tag},
        "budget": {
            "max_budget_usd": max_budget_usd,
            "quick_mode": quick_mode,
        },
        "max_iterations": max_iterations,
        "timeout_s": timeout_s,
        "promotion_policy": {
            "scope": "development",
            "live_production_promotion_allowed": False,
            "auc_only_promotion_allowed": False,
            "scopes": promotion_scopes,
        },
        "preflight": build_not_run_preflight(model_type=skill_id),
        "runtime": {
            "environment": settings.environment,
            "workspace_root": settings.workspace_root,
            "db_path": settings.db_path,
            "host_configs_path": settings.host_configs_path,
            "anthropic_model": settings.anthropic_model,
            # The session workspace follows the skill's declared template
            # (P7-005); ``runs_dir`` (an ML-layout setting) is deliberately
            # not claimed here.
            "session_workspace": (
                f"{settings.workspace_root}/{workspace_rel}"
                if workspace_rel
                else None
            ),
        },
        "hpo": {
            "enabled": False,
            "trials": None,
            "timesteps": None,
        },
        "focus_hint": focus_hint,
        # The resolved run spec: canonical immutable inputs with content
        # digests and secret references (never credential values).
        "run_spec": run_spec,
        # P7-003: the skill-sourced section — the manifest's claims about the
        # skill, read straight from its descriptor.
        "skill": {
            "id": skill_manifest.id,
            "version": getattr(skill_manifest, "version", None),
            "category": getattr(skill_manifest, "category", None),
            "session_path_template": getattr(
                getattr(skill_manifest, "workspace", None),
                "session_path_template",
                None,
            ),
            "phases": [
                phase.id for phase in (skill_manifest.phase_plan or [])
            ],
            "metric": {
                "field": skill_manifest.metric_schema.primary.field,
                "direction": getattr(
                    skill_manifest.metric_schema.primary, "direction", None
                ),
            },
            "promotion_target": {
                "kind": skill_manifest.promotion_target.primary.kind,
                "scopes": promotion_scopes,
            },
        },
    }


def manifest_pretty_json(manifest: ResearchSessionManifest) -> str:
    return json.dumps(
        manifest.model_dump(mode="json"),
        indent=2,
        sort_keys=True,
    ) + "\n"


def _default_objective(model_type: str) -> str:
    # Domain-neutral fallback: legacy ML skill ids keep their historical copy
    # for pre-migration session rendering; any other skill id gets a generic
    # objective naming the skill directly.
    return {
        "direction": "improve calibrated direction_proba for development promotion",
        "volatility": "improve calibrated volatility_proba for development promotion",
        "rl": "improve out-of-sample robustness using honest predictive inputs",
    }.get(model_type, f"improve {model_type} skill for development promotion")


def _default_model_family(model_type: str) -> str:
    # Historical family labels retained for pre-migration session rendering;
    # unknown skill ids fall back to the skill id itself.
    return {
        "direction": "stacked_tabular_direction",
        "volatility": "stacked_tabular_volatility",
        "rl": "policy_optimization_agent",
    }.get(model_type, model_type)


def _deep_merge(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in overrides.items():
        if (
            isinstance(value, dict)
            and isinstance(merged.get(key), dict)
        ):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_persisted_manifest(
    text: str,
) -> Tuple[Optional["ResearchSessionManifest"], Dict[str, Any]]:
    """Read a persisted artifact with its provenance report — never invent.

    Unknown fields carried by the artifact are reported by name and excluded
    from the model; missing immutable provenance (run spec, digests, runtime
    identity) is reported as missing. Nothing is back-filled with current
    registry or settings facts — the artifact's own recorded values are the
    only source.
    """
    from src.core.run_spec import provenance_report

    empty_report: Dict[str, Any] = {
        "unknown_fields": [],
        "missing_provenance": [],
        "spec_digest_verified": None,
        "reported_not_backfilled": True,
    }
    try:
        raw = json.loads(text)
    except (TypeError, ValueError) as exc:
        report = dict(empty_report)
        report["error"] = f"manifest artifact is not valid JSON: {exc}"
        return None, report
    if not isinstance(raw, dict):
        report = dict(empty_report)
        report["error"] = "manifest artifact is not a JSON object"
        return None, report
    report = provenance_report(raw)
    known = set(ResearchSessionManifest.model_fields)
    payload = {key: value for key, value in raw.items() if key in known}
    try:
        manifest = ResearchSessionManifest(**payload)
    except Exception as exc:  # noqa: BLE001 - surfaced in the report
        report["error"] = f"manifest does not validate: {exc}"
        return None, report
    return manifest, report
