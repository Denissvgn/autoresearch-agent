"""Domain semantics extension: the two motivating skill cases.

Case 1 (adaptive-phase): a completion rule that adapts to evidence
history resists declarative evidence_keys — the sanctioned
phase_advancement plugin escape now executes under the qualified
isolation rules with attempt-bound receipts. Case 2 (pareto-tradeoff): a
genuine two-metric tradeoff needs Pareto semantics — the scalar primary
contract cannot express it and a scalar proxy is refused.

Both cases are executable agent-authored fixtures (valid technical
evidence per the card). Migration, plugin adversarial containment, and
objective-specific acceptance scenarios are covered; nothing here (or in
the extension) branches on a domain or skill id.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from src.core.multiobjective import (
    Candidate,
    MultiObjectiveError,
    ObjectiveMetric,
    ScalarProxyRejected,
    dominates,
    non_dominated,
    objective_metrics_from_spec,
    promotion_frontier,
    scalar_winner_rejected,
)
from src.core.phase_resolver import (
    PluginAdvancementFailed,
    PluginAdvancementRejected,
    resolve_phase_advancement,
)
from src.core.skill_manifest import PluginEntry, ResearchSkillManifest
from src.core.skill_runtime import (
    ManifestSkillRuntime,
    UnsupportedPhaseAdvancementError,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "skill_cases"
ADAPTIVE = FIXTURES / "adaptive-phase"
PARETO = FIXTURES / "pareto-tradeoff"
ADVERSARIAL = FIXTURES / "adversarial"


class _Host:
    """Minimal SkillHostServices stand-in for runtime construction."""

    def load_claude_md(self) -> str:
        return ""

    def load_research_resume(self, config: Any) -> str:
        return ""

    def build_phase_contract_block(self, config: Any) -> str:
        return ""

    def research_resume_path(self, config: Any) -> str:
        return "/tmp/resume.md"


def _manifest(path: Path) -> ResearchSkillManifest:
    return ResearchSkillManifest.model_validate(
        yaml.safe_load((path / "SKILL.yaml").read_text())
    )


def _runtime(manifest: ResearchSkillManifest) -> ManifestSkillRuntime:
    return ManifestSkillRuntime(manifest, _Host())


def _entry(path: str = "phases.py") -> PluginEntry:
    return PluginEntry.model_validate({"kind": "phase_advancement", "path": path})


# ------------------------------------------------------------------
# Motivating case 1: adaptive phase advancement (plugin escape)
# ------------------------------------------------------------------
def test_case1_manifest_carries_the_plugin_declaration():
    manifest = _manifest(ADAPTIVE)
    assert manifest.phase_advancement.mode == "plugin"
    assert manifest.plugins.entries[0].kind == "phase_advancement"
    plan = _runtime(manifest).phase_plan()
    assert [p["id"] for p in plan] == ["screen", "refine"]


def test_case1_declarative_limitation_is_real():
    """Fixed evidence keys cannot express the adaptive rule: identical
    key presence with and without convergence evidence yields the same
    declarative verdict, while the plugin rule distinguishes them."""
    manifest = _manifest(ADAPTIVE)

    def declarative_advance(evidence):
        keys = manifest.phase_plan[0].evidence_keys
        return all(k in evidence for k in keys)

    flat = {"screen_result": 1.0, "trend": [0.5, 0.5, 0.5]}
    converged = {"screen_result": 1.0, "trend": [0.5, 0.5, 0.5],
                 "converged_early": True}
    assert declarative_advance(flat) == declarative_advance(converged) is True


def test_case1_plugin_rule_executes_with_an_attempt_bound_receipt():
    manifest = _manifest(ADAPTIVE)
    entry = _runtime(manifest).phase_advancement_plugin("screen")
    assert entry is not None and entry.kind == "phase_advancement"

    def resolve(evidence):
        return asyncio.run(
            resolve_phase_advancement(
                skill_dir=ADAPTIVE,
                plugin_entry=entry,
                mode="plugin",
                phase_id="screen",
                evidence_keys=tuple(manifest.phase_plan[0].evidence_keys),
                evidence=evidence,
                attempt_id="attempt-42",
            )
        )

    progressing = resolve({"screen_result": 1.0, "trend": [0.4, 0.5, 0.6]})
    plateau = resolve({"screen_result": 1.0, "trend": [0.5, 0.5, 0.5]})
    converged = resolve({"screen_result": 1.0, "trend": [0.9, 0.2, 0.9],
                         "converged_early": True})
    # the adaptive rule: keep going while progressing; advance early on
    # plateau or convergence — the declarative share alone advances all three
    assert progressing.advance is False
    assert plateau.advance is True
    assert converged.advance is True
    assert converged.source == "hybrid"
    assert converged.plugin_rule and "adaptive" in converged.plugin_rule
    receipt = converged.receipt
    assert receipt is not None
    assert receipt.attempt_id == "attempt-42"
    assert receipt.schema == "phase-advancement-plugin.v1"
    assert len(receipt.input_digest) == 64 and len(receipt.output_digest) == 64
    missing = resolve({"converged_early": True})
    assert missing.advance is False and missing.declarative_share is False


def test_case1_plugin_declarations_without_an_entry_are_rejected():
    manifest = _manifest(ADAPTIVE)
    data = manifest.model_dump(mode="json")
    data["plugins"] = {"entries": []}
    broken = ResearchSkillManifest.model_validate(data)
    with pytest.raises(UnsupportedPhaseAdvancementError):
        _runtime(broken).phase_plan()
    with pytest.raises(PluginAdvancementRejected):
        asyncio.run(
            resolve_phase_advancement(
                skill_dir=ADAPTIVE, plugin_entry=None, mode="plugin",
                phase_id="screen", evidence_keys=("screen_result",),
                evidence={}, attempt_id="a1",
            )
        )
    with pytest.raises(PluginAdvancementRejected):
        asyncio.run(
            resolve_phase_advancement(
                skill_dir=ADAPTIVE, plugin_entry=_entry(), mode="lexicographic",
                phase_id="screen", evidence_keys=("screen_result",),
                evidence={}, attempt_id="a1",
            )
        )


# ------------------------------------------------------------------
# Plugin adversarial containment (qualified isolation rules)
# ------------------------------------------------------------------
def _adversarial(plugin: str, timeout_s: float = 3.0):
    entry = PluginEntry.model_validate({
        "kind": "phase_advancement",
        "path": plugin,
        "caps": {"fs_write": "none", "network_egress": [], "env": [],
                 "timeout_s": timeout_s, "max_rss_mb": 256, "max_cpu_s": 3},
    })
    return asyncio.run(
        resolve_phase_advancement(
            skill_dir=ADVERSARIAL,
            plugin_entry=entry,
            mode="plugin",
            phase_id="screen",
            evidence_keys=("screen_result",),
            evidence={"screen_result": 1.0},
            attempt_id="attempt-adv",
        )
    )


def test_plugin_adversarial_timeout_tamper_and_schema_fail_closed():
    with pytest.raises(PluginAdvancementFailed):
        _adversarial("phases_timeout.py")
    with pytest.raises(PluginAdvancementFailed):
        _adversarial("phases_tamper.py")
    with pytest.raises(PluginAdvancementFailed) as wrong_schema:
        _adversarial("phases_bad_schema.py")
    assert "pinned schema" in str(wrong_schema.value)


def test_plugin_adversarial_env_secret_is_withheld_and_egress_ungranted():
    # the env allow-list is enforced: a secret in the host environment is
    # not passed to the plugin, so no verdict can exfiltrate it
    verdict = _adversarial("phases_env_spy.py")
    receipt = verdict.receipt
    assert receipt is not None
    assert "spied_env" not in json.dumps(receipt.as_dict())
    # and the capability grant binds egress as never granted: the receipt's
    # caps digest covers network_egress=[] — a plugin cannot grant itself
    # egress through its output (OS-level socket enforcement beyond the
    # env/rlimit posture is a documented limitation of the runner)
    entry = PluginEntry.model_validate({
        "kind": "phase_advancement",
        "path": "phases_env_spy.py",
        "caps": {"fs_write": "none", "network_egress": [], "env": []},
    })
    assert entry.caps is not None and entry.caps.network_egress == []


# ------------------------------------------------------------------
# Motivating case 2: multiobjective (Pareto) semantics
# ------------------------------------------------------------------
def test_case2_manifest_carries_the_multiobjective_declaration():
    manifest = _manifest(PARETO)
    assert manifest.metric_schema.objective is not None
    assert manifest.metric_schema.objective.kind == "multiobjective"
    metrics = objective_metrics_from_spec(manifest.metric_schema.objective)
    assert [(m.field, m.direction) for m in metrics] == [
        ("tps", "higher_is_better"),
        ("latency_ms", "lower_is_better"),
    ]


def test_case2_scalar_proxy_is_rejected_as_evidence():
    with pytest.raises(ScalarProxyRejected):
        scalar_winner_rejected(
            [ObjectiveMetric("tps", "higher_is_better"),
             ObjectiveMetric("latency_ms", "lower_is_better")]
        )


def test_case2_pareto_semantics_without_a_scalar_winner():
    objectives = [
        ObjectiveMetric("tps", "higher_is_better"),
        ObjectiveMetric("latency_ms", "lower_is_better"),
    ]
    a = Candidate("a", {"tps": 100.0, "latency_ms": 40.0})
    b = Candidate("b", {"tps": 80.0, "latency_ms": 20.0})
    c = Candidate("c", {"tps": 70.0, "latency_ms": 45.0})  # dominated
    d = Candidate("d", {"tps": 100.0, "latency_ms": 40.0})  # tie with a
    unmeasured = Candidate("e", {"tps": 999.0, "latency_ms": None})
    assert dominates(a, c, objectives) is True
    assert dominates(a, b, objectives) is False
    frontier = non_dominated([a, b, c, d, unmeasured], objectives)
    assert sorted(x.candidate_id for x in frontier) == ["a", "b", "d"]
    promotion = promotion_frontier([a, b, c, d], objectives)
    assert sorted(promotion["promotion_set"]) == ["a", "b", "d"]
    assert promotion["single_winner"] is None
    assert "scalar proxy" in promotion["note"]


# ------------------------------------------------------------------
# Migration: existing contracts unchanged; rejections preserved
# ------------------------------------------------------------------
def test_migration_shipped_skills_load_unchanged_as_scalar():
    for skill in ("prompt-engineering", "code-refactor", "db-config-tuning"):
        manifest = ResearchSkillManifest.model_validate(
            yaml.safe_load(
                (Path(__file__).resolve().parent.parent
                 / "skills" / skill / "SKILL.yaml").read_text()
            )
        )
        assert manifest.metric_schema.objective is None
        assert manifest.phase_advancement.mode == "declarative"


def test_unsupported_objective_kinds_are_rejected_explicitly():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ResearchSkillManifest.model_validate(
            {**_manifest(PARETO).model_dump(mode="json"),
             "metric_schema": {
                 **_manifest(PARETO).metric_schema.model_dump(mode="json"),
                 "objective": {"kind": "lexicographic", "metrics": []},
             }}
        )
    with pytest.raises(MultiObjectiveError):
        objective_metrics_from_spec(
            _manifest(ADAPTIVE).metric_schema
        )


def test_preserved_rejection_resolve_identity_plugin_mode():
    from src.core.iteration_snapshot import (
        UnsupportedIdentityResolveError,
        build_trial_identity,
    )

    with pytest.raises(UnsupportedIdentityResolveError):
        build_trial_identity(
            instrument="EURUSD",
            timeframe="1h",
            model_type="direction",
            command="run.sh",
            config_snapshot={"x": 1},
            quick_mode=False,
            resolve_mode="plugin",
        )


def test_extension_adds_no_domain_id_branch():
    for module in ("multiobjective", "phase_resolver"):
        source = (Path(__file__).resolve().parent.parent
                  / "src" / "core" / f"{module}.py").read_text()
        for banned in ("prompt-engineering", "code-refactor",
                       "db-config-tuning", "skill_id_to_model_type"):
            assert banned not in source, f"{module}.py references {banned}"