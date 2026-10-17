"""Tests for candidate identity separated from repeated observations.

Contract: the candidate digest (what was attempted) stays separate from the
observation identity (which measured observation of that candidate). Declared
identity fields are honored; evaluation-context changes isolate observations;
authorized repeats carry distinct observation slots and are charged; accidental
duplicate deliveries never run twice; exploratory point estimates are visibly
separated from qualification requiring sample counts and holdouts.
"""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from typing import Any, Dict, Optional

import pytest
from pydantic import ValidationError

try:
    import anthropic  # noqa: F401
except ModuleNotFoundError:
    _stub = types.SimpleNamespace(
        AsyncAnthropic=lambda *a, **kw: None,
        APITimeoutError=TimeoutError,
        APIConnectionError=ConnectionError,
        InternalServerError=RuntimeError,
        APIStatusError=type("APIStatusError", (Exception,), {"status_code": 500}),
    )
    sys.modules["anthropic"] = _stub

from src.core.iteration_snapshot import (
    UnsupportedIdentityResolveError,
    build_trial_identity,
    evaluation_context_hash,
    trial_identity_hash,
)
from src.core.significance import (
    INCONCLUSIVE,
    SIGNIFICANT,
    qualification_status,
    samples_from_rows,
)
from src.core.skill_manifest import SignificanceConfig


def _identity(
    *,
    hash_fields: Optional[list] = None,
    marker: Optional[Dict[str, Any]] = None,
    evaluation_context: Optional[Dict[str, Any]] = None,
    repeat_index: Optional[int] = None,
    config_snapshot: str = "a: 1\n",
) -> Dict[str, Any]:
    return build_trial_identity(
        instrument="DOGE_USDT",
        timeframe="15m",
        model_type="direction",
        command=None,
        config_snapshot=config_snapshot,
        quick_mode=False,
        marker=marker or {},
        hash_fields=hash_fields,
        evaluation_context=evaluation_context,
        repeat_index=repeat_index,
    )


# ---------------------------------------------------------------------------
# Declarative identity fields and the two identity layers
# ---------------------------------------------------------------------------


def test_declared_hash_fields_select_the_observation_identity() -> None:
    identity = _identity(
        hash_fields=["skill_id", "subject_id", "db_config_hash"],
        marker={"db_config_hash": "abc123"},
    )
    # Declared fields resolve (skill_id/subject_id aliases) and nothing else
    # leaks in; the candidate digest stays a separate, always-present layer.
    assert identity["skill_id"] == "direction"
    assert identity["subject_id"] == "DOGE_USDT"
    assert identity["db_config_hash"] == "abc123"
    assert identity["canonical_config_hash"], "candidate digest stays present"
    assert "seed" not in identity and "data_split_id" not in identity
    assert identity["schema_version"] == "autoresearch_observation_identity.v2"

    changed = _identity(
        hash_fields=["skill_id", "subject_id", "db_config_hash"],
        marker={"db_config_hash": "def456"},
    )
    assert trial_identity_hash(changed) != trial_identity_hash(identity)


def test_legacy_identity_unchanged_without_declarations() -> None:
    identity = _identity()
    assert identity["schema_version"] == "autoresearch_trial_identity.v1"
    assert set(identity) == {
        "schema_version",
        "instrument",
        "timeframe",
        "model_type",
        "canonical_config_hash",
        "seed",
        "validation_mode",
        "data_split_id",
    }
    assert _identity() == identity  # deterministic, byte-stable


def test_plugin_resolver_is_rejected_explicitly() -> None:
    with pytest.raises(UnsupportedIdentityResolveError):
        build_trial_identity(
            instrument="DOGE_USDT",
            timeframe="15m",
            model_type="direction",
            command=None,
            config_snapshot="a: 1\n",
            quick_mode=False,
            resolve_mode="plugin",
        )


def test_evaluation_context_hash_covers_evaluator_data_environment_fidelity() -> None:
    base = {
        "evaluator_id": "scorer",
        "evaluator_version": "1",
        "dataset_digests": ["d1"],
        "environment_digest": "e1",
        "fidelity": "measured",
    }
    assert evaluation_context_hash(base) == evaluation_context_hash(dict(base))
    for change in (
        {"evaluator_version": "2"},
        {"dataset_digests": ["d2"]},
        {"environment_digest": "e2"},
        {"fidelity": "simulated"},
    ):
        assert evaluation_context_hash({**base, **change}) != evaluation_context_hash(base)
    assert evaluation_context_hash({}) is None
    assert evaluation_context_hash(None) is None


def test_changed_evaluation_context_isolates_observations() -> None:
    fields = ["subject_id", "db_config_hash"]
    measured = _identity(
        hash_fields=fields,
        marker={"db_config_hash": "abc"},
        evaluation_context={"evaluator_id": "scorer", "fidelity": "measured"},
    )
    simulated = _identity(
        hash_fields=fields,
        marker={"db_config_hash": "abc"},
        evaluation_context={"evaluator_id": "scorer", "fidelity": "simulated"},
    )
    assert trial_identity_hash(measured) != trial_identity_hash(simulated)

    # Sample pools isolate by context: changed contexts never pool together.
    rows = [
        {
            "primary_metric": 0.5,
            "metrics_json": (
                '{"canonical_config_hash": "c1", "evaluation_context_hash": "ctx-a"}'
            ),
        },
        {
            "primary_metric": 0.9,
            "metrics_json": (
                '{"canonical_config_hash": "c1", "evaluation_context_hash": "ctx-b"}'
            ),
        },
    ]
    assert samples_from_rows(rows, canonical_config_hash="c1") == [0.5, 0.9]
    assert samples_from_rows(
        rows, canonical_config_hash="c1", context_hash="ctx-a"
    ) == [0.5]


# ---------------------------------------------------------------------------
# Repeat scheduling and duplicate delivery (the training guard)
# ---------------------------------------------------------------------------


def _guard_config(**overrides: Any):
    from src.core.orchestrator import ResearchConfig

    values = {
        "id": "res_repeats",
        "instrument": "DOGE_USDT",
        "timeframe": "15m",
        "model_type": "direction",
        "tag": "obs-identity",
        "quick_mode": True,
        "workspace_path": "/tmp/obs-identity",
    }
    values.update(overrides)
    return ResearchConfig(**values)


def _skill_with_policy(
    *, planned_repeats: int = 2, hash_fields: Optional[list] = None,
) -> SimpleNamespace:
    significance = SimpleNamespace(
        min_samples=2, min_sigma=1.0, planned_repeats=planned_repeats,
        holdout_required=False,
    )
    trial_identity = SimpleNamespace(
        hash_fields=hash_fields or [],
        resolve=SimpleNamespace(mode="declarative"),
    )
    manifest = SimpleNamespace(
        metric_schema=SimpleNamespace(primary=SimpleNamespace(
            direction="higher_is_better", field="primary_metric",
        ), significance=significance),
        trial_identity=trial_identity,
    )
    return SimpleNamespace(manifest=manifest)


class _DupStore:
    def __init__(self, duplicate: Optional[Dict[str, Any]]) -> None:
        self._duplicate = duplicate
        self.seen_hashes: list = []

    async def find_duplicate_trial_identity(self, **kwargs: Any):
        self.seen_hashes.append(kwargs["trial_identity_hash"])
        return self._duplicate


async def _run_guard(
    *,
    duplicate: Optional[Dict[str, Any]],
    planned_trial: Dict[str, Any],
    skill: Optional[SimpleNamespace] = None,
):
    from src.core.orchestrator import AgentOrchestrator

    orchestrator = object.__new__(AgentOrchestrator)
    orchestrator._store = _DupStore(duplicate)
    orchestrator._session_skills = {"res_repeats": skill} if skill else {}
    return await orchestrator._guard_duplicate_training_attempt(
        config=_guard_config(),
        turn=4,
        command=".venv/bin/python eval/run.py --config c.yaml",
        config_snapshot="a: 1\n",
        planned_trial=planned_trial,
    )


@pytest.mark.asyncio
async def test_authorized_repeats_get_distinct_observation_identities() -> None:
    skill = _skill_with_policy(planned_repeats=2)
    first = await _run_guard(duplicate=None, planned_trial={"repeat_index": 0}, skill=skill)
    second = await _run_guard(duplicate=None, planned_trial={"repeat_index": 1}, skill=skill)
    assert first == (None, None), "first observation is admitted"
    assert second == (None, None), "authorized repeat is admitted, not rejected"


def test_repeat_slots_stay_distinct_and_resubmission_collides() -> None:
    slot0 = _identity(repeat_index=0)
    slot1 = _identity(repeat_index=1)
    assert trial_identity_hash(slot0) != trial_identity_hash(slot1)
    assert slot0["observation_id"] != slot1["observation_id"]
    # Re-delivering a consumed slot is the same observation again.
    assert trial_identity_hash(_identity(repeat_index=0)) == trial_identity_hash(slot0)


@pytest.mark.asyncio
async def test_duplicate_delivery_does_not_run_twice() -> None:
    duplicate = {"research_id": "res_repeats", "iteration": 1}
    rejection, marker = await _run_guard(
        duplicate=duplicate, planned_trial={"repeat_index": 0},
    )
    assert rejection.meta["policy_allowed"] is False
    assert rejection.meta["policy_operation"] == "duplicate_attempt.reject"
    assert marker["status"] == "rejected_duplicate"
    assert marker["duplicate_of_iteration"] == 1


@pytest.mark.asyncio
async def test_repeats_beyond_the_declaration_are_rejected_explicitly() -> None:
    skill = _skill_with_policy(planned_repeats=2)
    rejection, marker = await _run_guard(
        duplicate=None, planned_trial={"repeat_index": 2}, skill=skill,
    )
    assert rejection.meta["policy_allowed"] is False
    assert rejection.meta["policy_operation"] == "unauthorized_repeat.reject"
    assert "planned_repeats=2" in rejection.meta["policy_reason"]
    assert marker["status"] == "rejected_duplicate"


@pytest.mark.asyncio
async def test_unsupported_identity_resolver_fails_before_work() -> None:
    skill = _skill_with_policy(
        hash_fields=["subject_id"],
    )
    skill.manifest.trial_identity.resolve = SimpleNamespace(mode="plugin")
    rejection, marker = await _run_guard(
        duplicate=None, planned_trial={}, skill=skill,
    )
    assert rejection.meta["policy_allowed"] is False
    assert rejection.meta["policy_operation"] == "identity_resolve.reject"
    assert "mode=plugin is not supported" in rejection.meta["policy_reason"]


# ---------------------------------------------------------------------------
# Significance fallback and qualification visibility
# ---------------------------------------------------------------------------


def _noisy_seeded_samples() -> tuple[list, list]:
    """Deterministic noisy multi-seed fixture (seeded LCG, no RNG dependency)."""
    def lcg(seed: int, n: int) -> list:
        out = []
        state = seed
        for _ in range(n):
            state = (1103515245 * state + 12345) % (2**31)
            out.append(state / (2**31))
        return out
    candidate = [0.60 + 0.02 * (u - 0.5) for u in lcg(7, 3)]
    reference = [0.60 + 0.02 * (u - 0.5) for u in lcg(11, 3)]
    return candidate, reference


def test_noisy_fixture_falls_back_visibly_and_never_qualifies() -> None:
    from src.core.significance import significance_verdict

    candidate, reference = _noisy_seeded_samples()
    config = SignificanceConfig(min_samples=2, min_sigma=1.0, planned_repeats=3)
    verdict = significance_verdict(
        candidate, reference, min_sigma=config.min_sigma, min_samples=config.min_samples,
    )
    assert verdict == INCONCLUSIVE, "overlapping noisy samples must be inconclusive"
    status = qualification_status(
        candidate=candidate, reference=reference, config=config, verdict=verdict,
    )
    assert status["status"] == "inconclusive"
    assert status["qualifies"] is False
    assert status["fallback_used"] is True


def test_sample_counts_and_holdouts_gate_qualification() -> None:
    config = SignificanceConfig(min_samples=3, planned_repeats=3)
    sparse = qualification_status(candidate=[0.5, 0.6], reference=[0.5, 0.6], config=config)
    assert sparse["status"] == "insufficient_samples"
    assert sparse["qualifies"] is False
    holdout_cfg = SignificanceConfig(min_samples=2, holdout_required=True)
    missing = qualification_status(
        candidate=[0.5, 0.6], reference=[0.4, 0.45], config=holdout_cfg,
        verdict=SIGNIFICANT, holdout_evidence=False,
    )
    assert missing["status"] == "missing_holdout"
    ok = qualification_status(
        candidate=[0.5, 0.6], reference=[0.4, 0.45], config=holdout_cfg,
        verdict=SIGNIFICANT, holdout_evidence=True,
    )
    assert ok["status"] == "qualified"
    undeclared = qualification_status(candidate=[0.5], config=None)
    assert undeclared["status"] == "not_declared" and undeclared["qualifies"] is True


def test_manifest_declares_the_repeat_policy() -> None:
    config = SignificanceConfig(min_samples=2, planned_repeats=3, holdout_required=True)
    assert config.planned_repeats == 3
    assert config.holdout_required is True
    assert SignificanceConfig().planned_repeats == 1
    with pytest.raises(ValidationError):
        SignificanceConfig(planned_repeats=0)


@pytest.mark.asyncio
async def test_inconclusive_significance_cannot_silently_qualify_production(
    monkeypatch,
) -> None:
    from src.core.config_promoter import ConfigPromoter

    class Store:
        async def get_session(self, research_id: str):
            return {"id": research_id, "skill_id": "noisy-skill"}

        async def get_iterations(self, research_id: str):
            candidate, reference = _noisy_seeded_samples()
            rows = [
                {
                    "iteration": index,
                    "primary_metric": value,
                    "metrics_json": '{"canonical_config_hash": "cand"}',
                }
                for index, value in enumerate(candidate, start=1)
            ]
            rows.append({
                "iteration": 90,
                "primary_metric": reference[0],
                "metrics_json": '{"canonical_config_hash": "ref"}',
            })
            rows.append({
                "iteration": 91,
                "primary_metric": reference[1],
                "metrics_json": '{"canonical_config_hash": "ref"}',
            })
            rows.append({
                "iteration": 92,
                "primary_metric": reference[2],
                "metrics_json": '{"canonical_config_hash": "ref"}',
            })
            return rows

    monkeypatch.setattr(
        "src.core.skill_registry.default_registry",
        SimpleNamespace(get=lambda skill_id: _skill_with_policy(planned_repeats=3)),
    )
    promoter = ConfigPromoter(Store())
    best = {
        "iteration": 3,
        "canonical_config_hash": "cand",
        "primary_metric": 0.6,
        "metrics_json": "{}",
    }
    from src.core.objective_comparator import ObjectiveComparator

    comparator = ObjectiveComparator(direction="maximize")
    production = await promoter._build_replication_qualification(
        research_id="res_repeats", best_iteration=best, comparator=comparator,
        scope="production",
    )
    assert production["passed"] is False, "inconclusive must not silently qualify"
    assert production["blockers"]
    assert production["qualification"]["fallback_used"] is True
    development = await promoter._build_replication_qualification(
        research_id="res_repeats", best_iteration=best, comparator=comparator,
        scope="development",
    )
    assert development["passed"] is True, "exploration is never blocked"
    assert development["qualification"]["qualifies"] is False  # but visible


@pytest.mark.asyncio
async def test_context_digest_states_the_significance_fallback(monkeypatch) -> None:
    from src.core.iteration_context import build_iteration_context_digest

    candidate, reference = _noisy_seeded_samples()
    rows = [
        {"iteration": i, "primary_metric": v, "decision": "keep",
         "metric_name": "score", "canonical_config_hash": "cand",
         "metrics_json": '{"canonical_config_hash": "cand"}'}
        for i, v in enumerate(candidate, start=1)
    ] + [
        {"iteration": 90 + i, "primary_metric": v, "decision": "keep",
         "metric_name": "score",
         "metrics_json": '{"canonical_config_hash": "ref"}'}
        for i, v in enumerate(reference, start=1)
    ]
    monkeypatch.setattr(
        "src.core.skill_registry.default_registry",
        SimpleNamespace(get=lambda skill_id: _skill_with_policy(planned_repeats=3)),
    )
    digest = build_iteration_context_digest(
        session={"id": "res_repeats", "skill_id": "noisy-skill", "model_type": ""},
        iterations=rows,
    )
    assert "Significance: verdict=inconclusive" in digest
    assert "point-test fallback (exploratory only)" in digest
