from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")

from src.core.research_manifest import (
    CURRENT_SCHEMA_VERSION,
    ResearchSessionManifest,
    build_research_manifest,
    manifest_pretty_json,
)


def _build_manifest(**overrides):
    return build_research_manifest(
        research_id="res_manifest",
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        tag="m8",
        quick_mode=False,
        max_iterations=5,
        max_budget_usd=2.5,
        timeout_s=3600,
        focus_hint="calibration",
        overrides=overrides or None,
    )


def test_build_research_manifest_has_required_runtime_sections():
    manifest = _build_manifest(
        data_window={"start": "2026-03-01", "end": "2026-03-31"},
    )
    payload = json.loads(manifest_pretty_json(manifest))

    assert payload["schema_version"] == "research_session_manifest.v3"
    assert payload["manifest_hash"]
    assert payload["research_id"] == "res_manifest"
    assert payload["data_window"]["instrument"] == "DOGE_USDT"
    assert payload["data_window"]["start"] == "2026-03-01"
    assert "mlflow_tracking" in payload["service_urls"]
    assert "mlflow_external" in payload["service_urls"]
    assert payload["preflight"]["schema_version"] == "autoresearch_service_preflight.v1"
    assert payload["preflight"]["status"] == "not_run"
    assert payload["runtime"]["runs_dir"].endswith("/runs/autotuner")
    assert payload["runtime"]["db_path"].endswith("/db/experiments.db")


# ---------------------------------------------------------------------------
# ARC-012 Wave 1 (P7-002/003/004): manifest v3 — skill identity authoritative,
# skill-driven sections, profile-based validation.
# ---------------------------------------------------------------------------

_BUNDLED_SKILL_IDS = ["prompt-engineering", "code-refactor", "db-config-tuning"]

#: Strings a skill-driven manifest must never contain — each one is an ML
#: artifact this skill does not produce (P7-003 acceptance). The
#: ``mlflow_experiment`` *key* may appear (with ``null``); the value is
#: asserted separately.
_FABRICATED_ML_STRINGS = (
    "direction-tuning",
    "experiment_matrix_v1",
    "runs/autotuner",
)


@pytest.mark.parametrize("skill_id", _BUNDLED_SKILL_IDS)
def test_v3_manifest_builds_for_bundled_skills_without_ml_fabrication(skill_id):
    """P7-002/P7-003 AC: every bundled (non-ML) skill builds a v3 manifest
    with model_type="", a populated skill section, and no invented ML
    provenance."""
    manifest = build_research_manifest(
        research_id="res_v3",
        instrument="subject",
        timeframe="variant",
        model_type="",
        skill_id=skill_id,
        tag="t1",
        quick_mode=False,
        max_iterations=3,
        max_budget_usd=1.0,
        timeout_s=60,
        focus_hint=None,
    )
    assert manifest.schema_version == "research_session_manifest.v3"
    assert manifest.skill_id == skill_id
    assert manifest.model_type == ""
    assert manifest.subject_id == "subject"
    assert manifest.variant == "variant"
    # Skill-sourced section present and honest.
    assert manifest.skill is not None
    assert manifest.skill["id"] == skill_id
    assert manifest.skill["phases"], "phase ids must come from SKILL.yaml"
    assert manifest.skill["promotion_target"]["kind"]
    # ML-only sections are absent (None), not fabricated.
    for section in ("data_window", "roster", "tsfm", "adaptive_features",
                    "split_ids", "cost_model", "gate_bundle"):
        assert getattr(manifest, section) is None, section
    assert manifest.mlflow_experiment is None
    # No ML artifact strings anywhere in the serialized manifest.
    blob = manifest_pretty_json(manifest)
    for fabricated in _FABRICATED_ML_STRINGS:
        assert fabricated not in blob, fabricated


def test_v3_manifest_model_type_alias_accepted_for_legacy_trio():
    """P7-002 AC: ``build_research_manifest(model_type=...)`` with a legacy
    alias still builds (and a non-alias value is normalized per D1 rather
    than crashing the pattern)."""
    manifest = _build_manifest()
    assert manifest.model_type == "direction"
    assert manifest.skill_id == "ml-direction"


@pytest.mark.parametrize(
    "model_type", ["direction", "volatility", "rl", ""],
)
def test_v3_model_type_closed_vocabulary(model_type):
    payload = _build_manifest().model_dump(mode="json")
    payload["model_type"] = model_type
    loaded = ResearchSessionManifest.model_validate(payload)
    assert loaded.model_type == model_type


def test_v3_model_type_rejects_free_text():
    """D1: the legacy field is a closed vocabulary — a skill id or typo must
    not accrete in it."""
    payload = _build_manifest().model_dump(mode="json")
    payload["model_type"] = "prompt-engineering"
    with pytest.raises(Exception, match="direction|volatility|rl"):
        ResearchSessionManifest.model_validate(payload)


def test_v3_unknown_skill_rejected_without_fabrication():
    """A skill id the registry cannot resolve raises instead of fabricating
    ML sections (the pre-P7-003 behaviour)."""
    with pytest.raises(ValueError, match="not registered"):
        build_research_manifest(
            research_id="res_unknown",
            instrument="subject",
            timeframe="variant",
            model_type="not-a-real-skill",
            tag="t1",
            quick_mode=False,
            max_iterations=3,
            max_budget_usd=1.0,
            timeout_s=60,
            focus_hint=None,
        )


def test_ml_profile_still_requires_ml_sections():
    """P7-004 regression: a legacy-ML manifest missing ``roster`` fails."""
    manifest = _build_manifest()
    payload = manifest.model_dump(mode="json")
    payload["roster"] = None
    with pytest.raises(Exception, match="manifest missing required section"):
        ResearchSessionManifest.model_validate(payload)


def test_skill_profile_does_not_require_ml_sections():
    """P7-004: a skill-driven manifest validates without the ML-only
    sections — but still demands the universal four."""
    manifest = build_research_manifest(
        research_id="res_v3b",
        instrument="subject",
        timeframe="variant",
        skill_id="prompt-engineering",
        tag="t1",
        quick_mode=False,
        max_iterations=3,
        max_budget_usd=1.0,
        timeout_s=60,
        focus_hint=None,
    )
    payload = manifest.model_dump(mode="json")
    loaded = ResearchSessionManifest.model_validate(payload)
    assert loaded.skill is not None

    # Each universal section is individually required: emptying any one of
    # them must fail the profile validation.
    for section in ("budget", "promotion_policy", "preflight", "runtime"):
        payload_missing = json.loads(json.dumps(payload))
        payload_missing[section] = {}
        with pytest.raises(Exception, match="manifest missing required section"):
            ResearchSessionManifest.model_validate(payload_missing)


def test_build_research_manifest_emits_per_session_nonce():
    """ARC-011 P4-002, revised by review C3 (2026-08-15): the per-session
    anti-forgery nonce is generated OUT-OF-BAND by the SessionManager and
    never enters the manifest artifact — the artifact is written into the
    agent-readable session workspace, and the W11 adversary is the agent
    itself. The schema keeps the ``session_nonce`` slot (always null in new
    artifacts) so the v2 shape is unchanged; legacy manifests embedding a
    value still load."""
    manifest = _build_manifest()
    assert manifest.session_nonce is None, (
        "the nonce must NOT be embedded in the manifest artifact (C3) — "
        "it is generated out-of-band by SessionManager._build_manifest_payload"
    )
    payload = json.loads(manifest_pretty_json(manifest))
    assert payload["session_nonce"] is None


def test_session_manager_nonce_is_out_of_band_and_fresh():
    """C3: ``SessionManager._build_manifest_payload`` returns a fresh 64-hex
    nonce alongside the (nonce-free) manifest, so the orchestrator still
    receives per-session nonce material without it ever touching the
    agent-readable artifact."""
    from src.core.orchestrator import ResearchConfig
    from src.core.session_manager import SessionManager

    mgr = SessionManager.__new__(SessionManager)
    config = ResearchConfig(
        id="res_c3", instrument="DOGE_USDT", timeframe="15m",
        model_type="direction", workspace_path="/tmp/c3",
    )
    # _build_manifest_payload is a sync helper: it only reads the config and
    # calls the manifest builder — no store or orchestrator interaction.
    _, _, nonce_a = mgr._build_manifest_payload(config)  # noqa: SLF001
    _, _, nonce_b = mgr._build_manifest_payload(config)  # noqa: SLF001

    for nonce in (nonce_a, nonce_b):
        assert isinstance(nonce, str) and len(nonce) == 64
        bytes.fromhex(nonce)  # valid hex — 32 bytes
    assert nonce_a != nonce_b, "nonce must be freshly generated per session"


def test_manifest_identity_overrides_must_match_request():
    with pytest.raises(ValueError, match="instrument must match"):
        _build_manifest(instrument="BTC_USDT")


# ---------------------------------------------------------------------------
# ARC-011 P3-019: manifest schema_version v1 → v2 + forward-compat read.
# ---------------------------------------------------------------------------


def test_new_manifest_emits_v3():
    """Newly built manifests carry the current schema version (P7-002)."""
    manifest = _build_manifest()
    assert manifest.schema_version == CURRENT_SCHEMA_VERSION
    assert manifest.schema_version == "research_session_manifest.v3"


@pytest.mark.parametrize(
    "model_type, expected_skill_id",
    [
        ("direction", "ml-direction"),
        ("volatility", "ml-volatility"),
        ("rl", "ml-rl"),
    ],
)
def test_manifest_carries_canonical_dual_shape_fields(model_type, expected_skill_id):
    """The v2 manifest artifact is self-describing: canonical fields are
    populated alongside the legacy trio for all three model types."""
    manifest = build_research_manifest(
        research_id="res_dual",
        instrument="BTC_USDT",
        timeframe="1h",
        model_type=model_type,
        tag="t1",
        quick_mode=True,
        max_iterations=2,
        max_budget_usd=1.0,
        timeout_s=60,
        focus_hint=None,
    )
    assert manifest.skill_id == expected_skill_id
    assert manifest.subject_id == "BTC_USDT"
    assert manifest.variant == "1h"
    # Legacy trio stays populated (dual shape, not replacement).
    assert manifest.model_type == model_type
    assert manifest.instrument == "BTC_USDT"
    assert manifest.timeframe == "1h"


def test_v1_manifest_loads_and_normalizes_to_current():
    """Forward-compat: a v1 manifest persisted before P3-019 loads under the
    current model and is re-stamped with canonical fields back-filled."""
    # Serialize a current manifest, then regress its schema_version to v1 to
    # simulate a row written before the bump.
    current = _build_manifest()
    v1_payload = current.model_dump(mode="json")
    v1_payload["schema_version"] = "research_session_manifest.v1"
    # Strip the canonical fields — a real v1 artifact never carried them.
    for field in ("skill_id", "subject_id", "variant", "skill"):
        v1_payload.pop(field, None)

    loaded = ResearchSessionManifest.model_validate(v1_payload)

    # Forward-compat: version normalized to the current version on read.
    assert loaded.schema_version == CURRENT_SCHEMA_VERSION
    # Canonical fields back-filled from the legacy trio (validator path).
    assert loaded.skill_id == "ml-direction"
    assert loaded.subject_id == "DOGE_USDT"
    assert loaded.variant == "15m"
    # Legacy trio preserved.
    assert loaded.model_type == "direction"
    assert loaded.instrument == "DOGE_USDT"


def test_v2_manifest_loads_and_normalizes_to_v3():
    """P7-002: persisted v2 artifacts (written before the bump) load
    unchanged and re-stamp as v3."""
    v2_payload = _build_manifest().model_dump(mode="json")
    v2_payload["schema_version"] = "research_session_manifest.v2"
    loaded = ResearchSessionManifest.model_validate(v2_payload)
    assert loaded.schema_version == "research_session_manifest.v3"
    assert loaded.model_type == "direction"
    assert loaded.skill_id == "ml-direction"


def test_unknown_schema_version_rejected_with_clear_error():
    """An unrecognized schema_version prefix is rejected (R3 back-compat —
    fail loudly rather than silently degrading)."""
    payload = _build_manifest().model_dump(mode="json")
    payload["schema_version"] = "research_session_manifest.v999"
    with pytest.raises(Exception, match="unsupported manifest schema_version"):
        ResearchSessionManifest.model_validate(payload)


def test_manifest_round_trip_preserves_canonical_fields():
    """model_dump → re-validate preserves the canonical surface (no field
    dropped on the round-trip through the v2 model)."""
    original = _build_manifest()
    dumped = original.model_dump(mode="json")
    round_tripped = ResearchSessionManifest.model_validate(dumped)

    assert round_tripped.schema_version == original.schema_version
    assert round_tripped.skill_id == original.skill_id
    assert round_tripped.subject_id == original.subject_id
    assert round_tripped.variant == original.variant
    # The canonical_json hash is stable across the round-trip (with_hash).
    assert round_tripped.with_hash().manifest_hash == original.manifest_hash
