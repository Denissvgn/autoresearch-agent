"""Tests for DPU-040 adaptive-level feature flag/version plumbing."""

import pytest

from feature_engineering.contracts import build_feature_schema_hash_payload
from feature_engineering.core.config import (
    ADAPTIVE_LEVEL_FEATURE_VERSION,
    FeatureConfig,
    SPECTRAL_FEATURE_EVIDENCE_REPORT,
    SPECTRAL_FEATURE_VERSION,
)
from feature_engineering.builders.feature_selection import (
    select_adaptive_level_features,
    select_direction_features,
    select_spectral_features,
    select_volatility_features,
)
from feature_engineering.spec.hasher import compute_feature_spec_hash


def test_adaptive_level_flag_defaults_off_and_preserves_selection():
    columns = [
        "return_1",
        "close_sma_10_ratio",
        "close_fib_bucket_24",
        "dist_to_support_24",
    ]

    cfg = FeatureConfig()
    selected = select_direction_features(columns, feature_config=cfg)

    assert cfg.adaptive_levels_enabled is False
    assert cfg.adaptive_levels_version == ADAPTIVE_LEVEL_FEATURE_VERSION
    assert selected == ["close_sma_10_ratio", "return_1"]


def test_adaptive_level_flag_on_selects_versioned_level_columns():
    columns = [
        "return_1",
        "close_fib_bucket_24",
        "dist_to_support_24",
        "dist_to_resistance_96",
        "sma_local_to_long_ratio_24",
        "range_local_to_long_ratio_24",
        "ohlc_bucket_spread_24",
        "close_bucket_delta_24",
    ]
    cfg = FeatureConfig(adaptive_levels_enabled=True)

    selected = select_direction_features(columns, feature_config=cfg)
    adaptive_selected = select_adaptive_level_features(columns)
    volatility_selected = select_volatility_features(columns, feature_config=cfg)

    assert adaptive_selected == [
        "close_bucket_delta_24",
        "close_fib_bucket_24",
        "dist_to_resistance_96",
        "dist_to_support_24",
        "ohlc_bucket_spread_24",
        "range_local_to_long_ratio_24",
        "sma_local_to_long_ratio_24",
    ]
    assert set(adaptive_selected).issubset(selected)
    assert set(adaptive_selected).issubset(volatility_selected)


def test_unknown_adaptive_level_version_fails_when_enabled():
    cfg = FeatureConfig(
        adaptive_levels_enabled=True,
        adaptive_levels_version="adaptive_levels.v2",
    )

    with pytest.raises(ValueError, match="Unsupported adaptive_levels_version"):
        select_direction_features(["close_fib_bucket_24"], feature_config=cfg)


def test_feature_schema_hash_payload_captures_enabled_version_and_selected_names():
    cfg = FeatureConfig(adaptive_levels_enabled=True)
    payload = build_feature_schema_hash_payload(
        ["return_1", "close_fib_bucket_24"],
        {"return_1": "float64", "close_fib_bucket_24": "int64"},
        feature_config=cfg,
        selected_feature_names=["close_fib_bucket_24", "return_1"],
    )

    assert payload["feature_flags"]["adaptive_levels"] == {
        "enabled": True,
        "version": ADAPTIVE_LEVEL_FEATURE_VERSION,
        "selected_feature_names": ["close_fib_bucket_24", "return_1"],
    }


def test_feature_spec_hash_ignores_disabled_flag_but_captures_enabled_context():
    base_spec = {
        "feature_names": ["return_1", "close_fib_bucket_24"],
        "feature_dtypes": {"return_1": "float64", "close_fib_bucket_24": "int64"},
        "library_version": "2.0.0",
        "feature_spec_version": "1.0",
    }
    disabled_spec = {
        **base_spec,
        "feature_flags": {
            "adaptive_levels": {
                "enabled": False,
                "version": ADAPTIVE_LEVEL_FEATURE_VERSION,
                "selected_feature_names": ["close_fib_bucket_24", "return_1"],
            }
        },
    }
    enabled_spec = {
        **base_spec,
        "feature_flags": {
            "adaptive_levels": {
                "enabled": True,
                "version": ADAPTIVE_LEVEL_FEATURE_VERSION,
                "selected_feature_names": ["close_fib_bucket_24", "return_1"],
            }
        },
    }
    enabled_spec_reordered = {
        **enabled_spec,
        "feature_flags": {
            "adaptive_levels": {
                "enabled": True,
                "version": ADAPTIVE_LEVEL_FEATURE_VERSION,
                "selected_feature_names": ["return_1", "close_fib_bucket_24"],
            }
        },
    }

    base_hash = compute_feature_spec_hash(base_spec)

    assert compute_feature_spec_hash(disabled_spec) == base_hash
    assert compute_feature_spec_hash(enabled_spec) != base_hash
    assert compute_feature_spec_hash(enabled_spec_reordered) != compute_feature_spec_hash(enabled_spec)


def test_spectral_feature_gate_defaults_off_and_preserves_selection():
    columns = ["return_1", "spectral_energy_16", "fft_phase_8", "sempo_prompt_0"]
    cfg = FeatureConfig()

    selected = select_direction_features(columns, feature_config=cfg)

    assert cfg.spectral_features_enabled is False
    assert cfg.spectral_features_version == SPECTRAL_FEATURE_VERSION
    assert selected == ["return_1"]
    assert select_spectral_features(columns) == [
        "fft_phase_8",
        "sempo_prompt_0",
        "spectral_energy_16",
    ]


def test_spectral_feature_gate_requires_dpu050_evidence_report():
    cfg = FeatureConfig(
        spectral_features_enabled=True,
        spectral_evidence_report_path=None,
    )

    with pytest.raises(ValueError, match="DPU-050 evidence"):
        select_direction_features(["spectral_energy_16"], feature_config=cfg)


def test_spectral_feature_gate_selects_columns_when_versioned_and_evidenced():
    cfg = FeatureConfig(
        spectral_features_enabled=True,
        spectral_evidence_report_path=SPECTRAL_FEATURE_EVIDENCE_REPORT,
    )
    columns = ["return_1", "spectral_energy_16", "fft_phase_8"]

    selected = select_direction_features(columns, feature_config=cfg)
    volatility_selected = select_volatility_features(columns, feature_config=cfg)
    payload = build_feature_schema_hash_payload(
        selected,
        {name: "float64" for name in selected},
        feature_config=cfg,
    )

    assert selected == ["fft_phase_8", "return_1", "spectral_energy_16"]
    assert "spectral_energy_16" in volatility_selected
    assert payload["feature_flags"]["spectral_features"] == {
        "enabled": True,
        "version": SPECTRAL_FEATURE_VERSION,
        "evidence_report_path": SPECTRAL_FEATURE_EVIDENCE_REPORT,
        "selected_feature_names": selected,
    }
