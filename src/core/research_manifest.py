"""Immutable research-session manifests for autoresearch runs."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.config import settings
from src.core.legacy_alias import model_type_to_skill_id
from src.core.service_preflight import build_not_run_preflight, sanitize_service_url

#: Current manifest artifact schema version (ARC-011 P3-019). v2 adds the
#: canonical ``skill_id``/``subject_id``/``variant`` derived fields alongside
#: the legacy ``model_type``/``instrument``/``timeframe`` so the persisted
#: manifest artifact carries the same dual shape as the API responses (§7.7).
#: v1 manifests are accepted on read and normalized to v2 (forward-compat).
CURRENT_SCHEMA_VERSION = "research_session_manifest.v2"
_KNOWN_SCHEMA_VERSIONS = {"research_session_manifest.v1", CURRENT_SCHEMA_VERSION}


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
    model_type: str = Field(pattern="^(direction|volatility|rl)$")
    objective: str
    model_family: str
    data_window: Dict[str, Any]
    baseline_config: Dict[str, Any]
    roster: Dict[str, Any]
    tsfm: Dict[str, Any]
    adaptive_features: Dict[str, Any]
    split_ids: Dict[str, Any]
    cost_model: Dict[str, Any]
    gate_bundle: Dict[str, Any]
    budget: Dict[str, Any]
    max_iterations: int = Field(ge=1)
    timeout_s: int = Field(ge=0)
    mlflow_experiment: str
    promotion_policy: Dict[str, Any]
    service_urls: Dict[str, str]
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

    @field_validator("schema_version", mode="before")
    @classmethod
    def _accept_known_schema_versions(cls, value: Any) -> Any:
        """Forward-compat read: accept v1 manifests, normalize to v2.

        Persisted v1 manifests (written before P3-019) carry
        ``schema_version = "research_session_manifest.v1"``. They are loaded
        unchanged and re-stamped as v2 on the round-trip so a migrated artifact
        carries the canonical fields. Unknown prefixes raise a field-located
        error rather than silently degrading (R3 back-compat).
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
        required = (
            "data_window",
            "baseline_config",
            "roster",
            "tsfm",
            "adaptive_features",
            "split_ids",
            "cost_model",
            "gate_bundle",
            "budget",
            "promotion_policy",
            "service_urls",
            "preflight",
            "runtime",
        )
        missing = [name for name in required if not getattr(self, name)]
        if missing:
            raise ValueError(f"manifest missing required section(s): {missing}")
        # P3-019: back-fill canonical dual-shape fields from the legacy trio so a
        # v1 manifest (which never carried skill_id/subject_id/variant) round-
        # trips through read → v2 with the canonical surface populated. The
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


def build_research_manifest(
    *,
    research_id: str,
    instrument: str,
    timeframe: str,
    model_type: str,
    tag: str,
    quick_mode: bool,
    max_iterations: int,
    max_budget_usd: float,
    timeout_s: int,
    focus_hint: Optional[str],
    overrides: Optional[Dict[str, Any]] = None,
) -> ResearchSessionManifest:
    """Build and validate a complete manifest from request/server state."""

    instrument_under = instrument.replace("-", "_")
    defaults = {
        "research_id": research_id,
        "instrument": instrument,
        "timeframe": timeframe,
        "model_type": model_type,
        # P3-019: canonical dual-shape fields, populated alongside the legacy
        # trio so the persisted manifest artifact is self-describing. The model
        # validator back-fills these if absent (v1 round-trip path).
        "skill_id": model_type_to_skill_id(model_type),
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


def manifest_pretty_json(manifest: ResearchSessionManifest) -> str:
    return json.dumps(
        manifest.model_dump(mode="json"),
        indent=2,
        sort_keys=True,
    ) + "\n"


def _default_objective(model_type: str) -> str:
    return {
        "direction": "improve calibrated direction_proba for development promotion",
        "volatility": "improve calibrated volatility_proba for development promotion",
        "rl": "improve PPO OOS trading robustness using honest predictive inputs",
    }.get(model_type, f"improve {model_type} model")


def _default_model_family(model_type: str) -> str:
    return {
        "direction": "stacked_tabular_direction",
        "volatility": "stacked_tabular_volatility",
        "rl": "ppo_trading_agent",
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
