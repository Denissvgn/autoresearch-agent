"""ResearchConfig generalization tests (ARC-011 P2-020).

Pins the P2-017 behavior: ``ResearchConfig`` accepts both the legacy shape
(``instrument``/``timeframe``/``model_type`` flat fields) and the canonical shape
(``subject_id``/``variant``/``skill_id``), the canonical fields derive from
legacy when unset, the flat ML fields mirror into ``skill_params``, and the
``skill_id`` derivation is deferred to ``materialize_skill_runtime`` (not
``__post_init__``) so legacy sessions keep the transitional runtime.

Also covers P2-019 (``legacy_alias`` ``model_type ↔ skill_id`` round-trips).
"""

from __future__ import annotations

import pytest

from src.core.legacy_alias import (
    is_known_model_type,
    model_type_to_skill_id,
    skill_id_to_model_type,
)
from src.core.orchestrator import ResearchConfig


# ===========================================================================
# P2-019 — legacy alias registry
# ===========================================================================


@pytest.mark.parametrize(
    "model_type, skill_id",
    [
        ("direction", "ml-direction"),
        ("volatility", "ml-volatility"),
        ("rl", "ml-rl"),
    ],
)
def test_model_type_to_skill_id(model_type: str, skill_id: str):
    assert model_type_to_skill_id(model_type) == skill_id


@pytest.mark.parametrize(
    "model_type, skill_id",
    [
        ("direction", "ml-direction"),
        ("volatility", "ml-volatility"),
        ("rl", "ml-rl"),
    ],
)
def test_skill_id_to_model_type(model_type: str, skill_id: str):
    assert skill_id_to_model_type(skill_id) == model_type


def test_alias_round_trip_is_identity():
    for mt in ("direction", "volatility", "rl"):
        assert skill_id_to_model_type(model_type_to_skill_id(mt)) == mt


def test_unknown_model_type_is_its_own_skill_id():
    """Non-legacy values are already canonical skill ids — identity fallback."""
    assert model_type_to_skill_id("prompt-engineering") == "prompt-engineering"
    assert model_type_to_skill_id("") == ""


def test_unknown_skill_id_is_its_own_model_type():
    """Non-legacy skill ids alias to themselves — dual-shape for every skill."""
    assert skill_id_to_model_type("prompt-engineering") == "prompt-engineering"
    assert skill_id_to_model_type("") == ""


def test_is_known_model_type():
    assert is_known_model_type("direction")
    assert is_known_model_type("volatility")
    assert is_known_model_type("rl")
    assert not is_known_model_type("pipeline")
    assert not is_known_model_type("")


# ===========================================================================
# P2-017 — ResearchConfig generalization
# ===========================================================================


def test_legacy_shape_construction_works():
    """Legacy fields (instrument/timeframe/model_type) are still the primary
    construction shape — no caller needs to change."""
    cfg = ResearchConfig(
        id="s1", instrument="BTCUSD", timeframe="5m", model_type="direction"
    )
    assert cfg.instrument == "BTCUSD"
    assert cfg.timeframe == "5m"
    assert cfg.model_type == "direction"


def test_canonical_fields_derive_from_legacy():
    """subject_id/variant derive from instrument/timeframe when not set."""
    cfg = ResearchConfig(
        id="s1", instrument="BTCUSD", timeframe="5m", model_type="direction"
    )
    assert cfg.subject_id == "BTCUSD"
    assert cfg.variant == "5m"


def test_canonical_fields_win_when_explicitly_set():
    """When subject_id/variant are passed explicitly, they are authoritative."""
    cfg = ResearchConfig(
        id="s1", instrument="BTCUSD", timeframe="5m", model_type="direction",
        subject_id="ETHUSD", variant="15m",
    )
    assert cfg.subject_id == "ETHUSD"
    assert cfg.variant == "15m"
    # Legacy fields are unchanged (they're independent storage today).
    assert cfg.instrument == "BTCUSD"


def test_skill_id_stays_empty_by_default():
    """skill_id is NOT derived in __post_init__ — it stays "" so legacy
    sessions keep the transitional runtime (the derivation happens in
    materialize_skill_runtime). This is the P2-017 back-compat guarantee."""
    cfg = ResearchConfig(
        id="s1", instrument="BTCUSD", timeframe="5m", model_type="direction"
    )
    assert cfg.skill_id == ""


def test_skill_id_when_explicitly_set():
    cfg = ResearchConfig(
        id="s1", instrument="BTCUSD", timeframe="5m", model_type="direction",
        skill_id="ml-direction",
    )
    assert cfg.skill_id == "ml-direction"


def test_skill_params_initializes_to_dict():
    """skill_params is always a dict after construction (never None). The
    non-falsy flat-field defaults (hpo_trials=20, hpo_timesteps=50000) mirror
    into it; falsy defaults (enable_hpo=False, trading_mode=None) do not."""
    cfg = ResearchConfig(
        id="s1", instrument="BTCUSD", timeframe="5m", model_type="direction"
    )
    assert isinstance(cfg.skill_params, dict)
    # Non-falsy defaults mirror in.
    assert cfg.skill_params.get("hpo_trials") == 20
    assert cfg.skill_params.get("hpo_timesteps") == 50000
    # Falsy defaults do not.
    assert "enable_hpo" not in cfg.skill_params
    assert "trading_mode" not in cfg.skill_params


def test_flat_ml_fields_mirror_into_skill_params():
    """The flat ML fields (enable_hpo/hpo_*/trading_mode/...) mirror into
    skill_params so manifest-driven runtimes read them from one dict (P2-018).
    Fields that are falsy (None/False) are not mirrored."""
    cfg = ResearchConfig(
        id="s1", instrument="BTCUSD", timeframe="5m", model_type="rl",
        enable_hpo=True, hpo_trials=15, hpo_timesteps=25000,
        trading_mode="margin", agent_strategy="AGGR", initial_balance=10000.0,
    )
    assert cfg.skill_params["enable_hpo"] is True
    assert cfg.skill_params["hpo_trials"] == 15
    assert cfg.skill_params["hpo_timesteps"] == 25000
    assert cfg.skill_params["trading_mode"] == "margin"
    assert cfg.skill_params["agent_strategy"] == "AGGR"
    assert cfg.skill_params["initial_balance"] == 10000.0


def test_falsy_flat_fields_not_mirrored():
    """enable_hpo=False / trading_mode=None are NOT mirrored (they're defaults)."""
    cfg = ResearchConfig(
        id="s1", instrument="BTCUSD", timeframe="5m", model_type="direction"
    )
    assert "enable_hpo" not in cfg.skill_params
    assert "trading_mode" not in cfg.skill_params


def test_skill_params_passed_explicitly_are_preserved():
    """A caller can pass skill_params directly; it's not overwritten."""
    cfg = ResearchConfig(
        id="s1", instrument="BTCUSD", timeframe="5m", model_type="direction",
        skill_params={"custom_param": 42},
    )
    assert cfg.skill_params["custom_param"] == 42


def test_skill_version_field_exists():
    """P1-023 (D3): skill_version field is present (default "")."""
    cfg = ResearchConfig(
        id="s1", instrument="BTCUSD", timeframe="5m", model_type="direction"
    )
    assert cfg.skill_version == ""
