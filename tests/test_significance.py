"""P2 multi-seed significance tests.

Covers the pure statistics (``src/core/significance.py``), the manifest
declaration (``metric_schema.significance``), and the orchestrator's
declarative opt-in hook (``_significance_improved`` / ``_infer_decision``)
with a stubbed store — the default path (no declaration) stays
byte-identical to the legacy epsilon test.
"""

from __future__ import annotations

import json
import os
from types import SimpleNamespace
from typing import Any, Optional

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")
os.environ.setdefault("USE_VAULT", "false")

import pytest
import yaml

from src.core.significance import (
    INCONCLUSIVE,
    REGRESSION,
    SIGNIFICANT,
    best_config_hash,
    mean_std,
    samples_from_rows,
    significance_verdict,
)
from src.core.skill_loader import load_skill_manifest

# ---------------------------------------------------------------------------
# Pure statistics
# ---------------------------------------------------------------------------


class TestMeanStd:
    def test_single_value_is_deterministic(self):
        assert mean_std([0.5]) == (0.5, 0.0)

    def test_two_values(self):
        mean, std = mean_std([0.4, 0.6])
        assert mean == pytest.approx(0.5)
        assert std == pytest.approx(0.1)

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            mean_std([])


class TestVerdict:
    def test_clean_separation_is_significant(self):
        verdict = significance_verdict(
            [0.60, 0.61, 0.60], [0.50, 0.51, 0.50],
        )
        assert verdict == SIGNIFICANT

    def test_reversed_separation_is_regression(self):
        verdict = significance_verdict(
            [0.40, 0.41, 0.40], [0.50, 0.51, 0.50],
        )
        assert verdict == REGRESSION

    def test_overlapping_noise_is_inconclusive(self):
        verdict = significance_verdict(
            [0.52, 0.58, 0.55], [0.53, 0.57, 0.54],
        )
        assert verdict == INCONCLUSIVE

    def test_sparse_data_is_inconclusive_never_a_verdict(self):
        assert significance_verdict(
            [0.9], [0.5, 0.5], min_samples=2,
        ) == INCONCLUSIVE
        assert significance_verdict(
            [0.9, 0.9], [0.5], min_samples=2,
        ) == INCONCLUSIVE

    def test_deterministic_zero_sigma_compares_raw_means(self):
        # Both configs bit-stable: any mean difference is decisive.
        assert significance_verdict([0.6, 0.6], [0.5, 0.5]) == SIGNIFICANT
        assert significance_verdict([0.5, 0.5], [0.5, 0.5]) == INCONCLUSIVE

    def test_lower_is_better_direction(self):
        assert significance_verdict(
            [0.10, 0.11, 0.10], [0.50, 0.51, 0.50],
            direction="lower_is_better",
        ) == SIGNIFICANT

    def test_min_sigma_raises_the_bar(self):
        # ~1.8σ separation: significant at 1.0σ, inconclusive at 2.0σ.
        cand = [0.56, 0.66, 0.61]   # mean .61, σ ≈ .041
        ref = [0.50, 0.60, 0.55]    # mean .55, σ ≈ .041
        assert significance_verdict(cand, ref, min_sigma=1.0) == SIGNIFICANT
        assert significance_verdict(cand, ref, min_sigma=2.0) == INCONCLUSIVE


# ---------------------------------------------------------------------------
# Row helpers
# ---------------------------------------------------------------------------


def _row(
    iteration: int, metric: float, config_hash: str, decision: str = "keep",
) -> dict[str, Any]:
    return {
        "iteration": iteration,
        "primary_metric": metric,
        "decision": decision,
        "metrics_json": json.dumps({"canonical_config_hash": config_hash}),
    }


class TestRowHelpers:
    def test_samples_from_rows_groups_by_hash(self):
        rows = [
            _row(1, 0.5, "aaa"), _row(2, 0.52, "bbb"), _row(3, 0.51, "aaa"),
        ]
        assert samples_from_rows(rows, canonical_config_hash="aaa") == [0.5, 0.51]

    def test_samples_skip_malformed_rows(self):
        rows = [
            _row(1, 0.5, "aaa"),
            {"iteration": 2, "primary_metric": 0.6, "metrics_json": "{bad"},
        ]
        assert samples_from_rows(rows, canonical_config_hash="aaa") == [0.5]

    def test_best_config_hash_picks_extreme_kept_row(self):
        rows = [
            _row(1, 0.5, "aaa"), _row(2, 0.7, "bbb"), _row(3, 0.6, "ccc"),
        ]
        assert best_config_hash(rows) == "bbb"
        assert best_config_hash(rows, direction="lower_is_better") == "aaa"

    def test_best_config_hash_none_when_empty(self):
        assert best_config_hash([]) is None


# ---------------------------------------------------------------------------
# Manifest declaration
# ---------------------------------------------------------------------------


def _manifest_dict() -> dict[str, Any]:
    return {
        "schema_version": "research_skill.v1",
        "id": "sig-skill",
        "version": "1.0.0",
        "category": "optimization",
        "display_name": "Sig Skill",
        "description": "x",
        "llm": {"provider": "anthropic", "primary_model": "m"},
        "workspace": {"session_path_template": "runs/{skill_id}"},
        "variants": {"static": ["v1"]},
        "param_schema": {"type": "object"},
        "metric_schema": {
            "primary": {"field": "m", "label": "M", "direction": "higher_is_better"},
            "significance": {"min_samples": 2, "min_sigma": 1.5},
        },
        "decision_vocabulary": {"base": ["keep"]},
        "phase_plan": [{"id": "p1", "min_iterations": 1, "max_iterations": 2}],
        "command_policy": {"allowed_scripts": ["run.sh"]},
        "output_parser": {"format": "delimited_kv"},
        "preflight": [],
        "promotion_target": {"primary": {"kind": "file_path", "path_template": "/tmp/x"}},
    }


class TestManifestDeclaration:
    def test_significance_section_parses(self):
        manifest = load_skill_manifest(yaml.safe_dump(_manifest_dict()))
        sig = manifest.metric_schema.significance
        assert sig is not None
        assert sig.min_samples == 2
        assert sig.min_sigma == 1.5

    def test_absence_keeps_legacy_default(self):
        data = _manifest_dict()
        data["metric_schema"].pop("significance")
        manifest = load_skill_manifest(yaml.safe_dump(data))
        assert manifest.metric_schema.significance is None

    def test_out_of_range_rejected(self):
        from src.core.skill_manifest import ManifestValidationError

        data = _manifest_dict()
        data["metric_schema"]["significance"] = {"min_samples": 0}
        with pytest.raises(ManifestValidationError):
            load_skill_manifest(yaml.safe_dump(data))


# ---------------------------------------------------------------------------
# Orchestrator hook (stubbed store + fake skill runtime)
# ---------------------------------------------------------------------------


class _StubStore:
    def __init__(self, best_metric: Optional[float], rows: list[dict]) -> None:
        self._best = best_metric
        self._rows = rows

    async def get_session(self, research_id: str) -> Optional[dict]:
        return None if self._best is None else {"best_metric": self._best}

    async def get_iterations(self, research_id: str) -> list[dict]:
        return self._rows


def _fake_skill(declared: bool) -> SimpleNamespace:
    sig = SimpleNamespace(min_samples=2, min_sigma=1.0) if declared else None
    return SimpleNamespace(
        manifest=SimpleNamespace(
            metric_schema=SimpleNamespace(
                primary=SimpleNamespace(direction="higher_is_better"),
                significance=sig,
            ),
        ),
    )


@pytest.mark.asyncio
async def test_infer_decision_significant_beats_epsilon():
    """A noisy candidate whose mean separates by ≥min_sigma is 'improve'
    even though its single sample does not beat best + epsilon."""
    from src.core.orchestrator import AgentOrchestrator

    orch = AgentOrchestrator(_StubStore(0.55, []))  # type: ignore[arg-type]
    orch._session_skills["res_sig"] = _fake_skill(True)  # noqa: SLF001
    # Prior samples of THIS config: 0.62, 0.64 + current 0.63 → mean .63.
    store_rows = [
        _row(1, 0.62, "cand"), _row(2, 0.64, "cand"),
        _row(3, 0.54, "best"), _row(4, 0.56, "best"),
    ]
    orch._store = _StubStore(0.56, store_rows)  # noqa: SLF001
    decision = await orch._infer_decision(  # noqa: SLF001
        "res_sig", 0.63, True, config_hash="cand",
    )
    assert decision == "keep"


@pytest.mark.asyncio
async def test_infer_decision_regression_blocks_noise_chase():
    """A single lucky sample above best but whose config's samples regress
    overall is a discard — the noise-chase the gate exists to stop."""
    from src.core.orchestrator import AgentOrchestrator

    store_rows = [
        _row(1, 0.50, "cand"), _row(2, 0.49, "cand"),
        _row(3, 0.55, "best"), _row(4, 0.56, "best"),
    ]
    orch = AgentOrchestrator(_StubStore(0.56, store_rows))  # type: ignore[arg-type]
    orch._session_skills["res_sig"] = _fake_skill(True)  # noqa: SLF001
    decision = await orch._infer_decision(  # noqa: SLF001
        "res_sig", 0.57, True, config_hash="cand",
    )
    # 0.57 > best(0.56)+ε would be legacy 'keep', but mean(.52) regresses.
    assert decision == "discard"


@pytest.mark.asyncio
async def test_infer_decision_undeclared_is_byte_identical_legacy():
    from src.core.orchestrator import AgentOrchestrator

    store_rows = [_row(1, 0.5, "aaa"), _row(2, 0.6, "bbb")]
    orch = AgentOrchestrator(_StubStore(0.55, store_rows))  # type: ignore[arg-type]
    orch._session_skills["res_sig"] = _fake_skill(False)  # noqa: SLF001
    decision = await orch._infer_decision(  # noqa: SLF001
        "res_sig", 0.56, True, config_hash="aaa",
    )
    assert decision == "keep"  # legacy epsilon: 0.56 > 0.55 + tiny ε
    decision = await orch._infer_decision(  # noqa: SLF001
        "res_sig", 0.55, True, config_hash="aaa",
    )
    assert decision == "discard"  # not above epsilon → no improvement


@pytest.mark.asyncio
async def test_significance_sparse_data_falls_back_to_legacy():
    from src.core.orchestrator import AgentOrchestrator

    # Candidate has no prior replicates → inconclusive → legacy epsilon.
    store_rows = [_row(1, 0.55, "best"), _row(2, 0.56, "best")]
    orch = AgentOrchestrator(_StubStore(0.56, store_rows))  # type: ignore[arg-type]
    orch._session_skills["res_sig"] = _fake_skill(True)  # noqa: SLF001
    decision = await orch._infer_decision(  # noqa: SLF001
        "res_sig", 0.57, True, config_hash="cand",
    )
    assert decision == "keep"
