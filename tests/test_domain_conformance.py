"""Domain conformance: complete workflows over the supported declarations.

Each case materializes a small fixture skill with a fresh identity (data
only — no core or UI edits), drops it into the skills root, and drives the
real API/session paths end to end on the scripted demo provider: session
start, governed experiment execution, result parsing through the declared
parser, iteration recording, winner selection through the declared
objective, and promotion preview/confirmation through the declared scope
shape. Unsupported extensions and parameter violations must fail before any
side effect.

The catalog is checked mechanically against the published support matrix so
every supported declaration value carries execution evidence, and a
machine-readable conformance report can be emitted to the qualification
workspace (set CONFORMANCE_REPORT_PATH).
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest
import yaml

from tests.test_non_ml_session_e2e import (
    API_TOKEN,
    _auth,
    _poll_terminal,
    _preserve_lifespan_globals,
)

_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "conformance"

_TERMINAL = {"completed", "failed", "timed_out", "stopped"}


def _materialize_skill(skills_root: Path, skill_id: str, manifest: dict) -> Path:
    """Drop one fixture skill directory (SKILL.yaml + primer + evaluator)."""
    skill_dir = skills_root / skill_id
    (skill_dir / "eval").mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8",
    )
    (skill_dir / "SKILL.md").write_text(
        (_FIXTURE_DIR / "SKILL.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (skill_dir / "eval" / "run.py").write_text(
        (_FIXTURE_DIR / "eval" / "run.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (skill_dir / "bootstrap.py").write_text(
        (_FIXTURE_DIR / "bootstrap.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return skill_dir


@pytest.fixture
def conformance_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Hermetic deployment: tmp workspace + tmp skills root + demo mode."""
    from src.config import settings
    from src.core import skill_registry as skill_registry_module

    ws_root = tmp_path / "workspace"
    venv_bin = ws_root / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    os.symlink(sys.executable, venv_bin / "python")
    monkeypatch.setattr(settings, "demo_mode", True)
    monkeypatch.setattr(settings, "workspace_root", str(ws_root))
    monkeypatch.setattr(settings, "host_configs_path", str(tmp_path / "hostconfigs"))
    monkeypatch.setattr(settings, "autoresearch_api_token", API_TOKEN)

    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    monkeypatch.setattr(
        skill_registry_module, "DEFAULT_SKILLS_ROOT", skills_root,
    )
    # The API resolves skills through the module-level singleton; retarget it
    # in place so drop-a-directory discovery runs against the hermetic root.
    registry = skill_registry_module.default_registry
    monkeypatch.setattr(registry, "_root", skills_root)
    monkeypatch.setattr(registry, "_cache", {})
    monkeypatch.setattr(registry, "_discovered", set())
    monkeypatch.setattr(registry, "_scanned", False)
    _preserve_lifespan_globals(monkeypatch)
    return {
        "ws_root": ws_root,
        "skills_root": skills_root,
        "host_configs": tmp_path / "hostconfigs",
    }


def _start(client, body: dict):
    return client.post(
        "/api/v1/research/start", headers=_auth(), json=body,
    )



# ── Case catalog ──────────────────────────────────────────────────────────
# One complete workflow per supported value of each declared axis: objective
# (goal + metric direction), parser format, parameter-binding shape, and
# promotion-scope shape. The coverage test below checks this catalog against
# the published support matrix.

CONFORMANCE_CASES: list[dict] = [
    {
        "case_id": "optimize-higher-json-single-scope",
        "skill_id": "conformance-opt-high-json",
        "goal": "optimize",
        "direction": "higher_is_better",
        "parser": "json_marker",
        "bindings": ["evaluator_flags", "fixed_flags"],
        "eval_flags": ["sequence", "metric_name", "echo", "threshold_sequence"],
        "fixed_flags": {},
        "scopes": [{"id": "development", "approval_required": False}],
        "target_kind": "file_path",
        "sequence": [10.0, 5.0, 20.0],
        "threshold_sequence": ["true", "true", "true"],
        "params": {"sequence": "10,5,20", "metric_name": "score",
                   "echo": "bound-echo", "effort": 3},
        "expected_winner_metric": 20.0,
    },
    {
        "case_id": "optimize-lower-json-single-scope",
        "skill_id": "conformance-opt-low-json",
        "goal": "optimize",
        "direction": "lower_is_better",
        "parser": "json_marker",
        "bindings": ["evaluator_flags", "fixed_flags"],
        "eval_flags": ["sequence", "metric_name", "threshold_sequence"],
        "fixed_flags": {},
        "scopes": [{"id": "development", "approval_required": False}],
        "target_kind": "file_path",
        "sequence": [10.0, 5.0, 20.0],
        "threshold_sequence": ["true", "true", "true"],
        "params": {"sequence": "10,5,20", "metric_name": "latency_ms"},
        "expected_winner_metric": 5.0,
    },
    {
        "case_id": "satisfice-higher-kv-single-scope",
        "skill_id": "conformance-sat-high-kv",
        "goal": "satisfice",
        "direction": "higher_is_better",
        "parser": "delimited_kv",
        "bindings": ["fixed_flags"],
        "eval_flags": [],
        "fixed_flags": {
            "--sequence": "3,4,9",
            "--threshold-sequence": "false,false,true",
            "--metric-name": "score",
        },
        "scopes": [{"id": "development", "approval_required": False}],
        "target_kind": "file_path",
        "sequence": [3.0, 4.0, 9.0],
        "threshold_sequence": ["false", "false", "true"],
        "params": {"effort": 2},
        "expected_winner_metric": 9.0,
    },
    {
        "case_id": "satisfice-lower-kv-single-scope",
        "skill_id": "conformance-sat-low-kv",
        "goal": "satisfice",
        "direction": "lower_is_better",
        "parser": "delimited_kv",
        "bindings": ["evaluator_flags", "fixed_flags"],
        "eval_flags": ["sequence", "metric_name"],
        "fixed_flags": {"--threshold-sequence": "false,true,true"},
        "scopes": [{"id": "development", "approval_required": False}],
        "target_kind": "file_path",
        "sequence": [10.0, 5.0, 20.0],
        "threshold_sequence": ["false", "true", "true"],
        "params": {"sequence": "10,5,20", "metric_name": "latency_ms",
                   "effort": 1},
        "expected_winner_metric": 5.0,
    },
    {
        "case_id": "optimize-higher-json-chained-scope",
        "skill_id": "conformance-opt-high-chained",
        "goal": "optimize",
        "direction": "higher_is_better",
        "parser": "json_marker",
        "bindings": ["evaluator_flags", "fixed_flags", "bootstrap_inputs",
                     "candidate_files", "output_metadata"],
        "eval_flags": ["sequence", "metric_name", "threshold_sequence",
                       "input_file"],
        "fixed_flags": {},
        "scopes": [
            {"id": "development", "approval_required": False},
            {"id": "production", "approval_required": True,
             "prior_scopes": ["development"]},
        ],
        "target_kind": "registry_api",
        "sequence": [10.0, 5.0, 20.0],
        "threshold_sequence": ["true", "true", "true"],
        "params": {"sequence": "10,5,20", "metric_name": "score",
                   "input_file": "sample_input.txt", "effort": 5},
        "expected_winner_metric": 20.0,
    },
]


def _case_manifest(case: dict) -> dict:
    """One fixture-skill manifest declaring exactly the case's axes."""
    bindings = case["bindings"]
    flag_names = {
        "sequence": "--sequence",
        "metric_name": "--metric-name",
        "threshold_sequence": "--threshold-sequence",
        "echo": "--echo",
        "input_file": "--input",
    }
    evaluator_flags = {
        name: flag_names[name] for name in case.get("eval_flags", [])
    }
    evaluator_flags["candidate_file"] = "--target"
    bootstrap_inputs: dict = {}
    candidate_files = {"candidate_file": "candidate.yaml"}
    output_metadata: dict = {}
    if "bootstrap_inputs" in bindings:
        bootstrap_inputs = {"input_file": "input_file"}
        output_metadata = {"input_file": "bound_input"}
    fixed_flags = {"--marker": "ITERATION_RESULT:"}
    fixed_flags["--emit-format"] = (
        "json" if case["parser"] == "json_marker" else "kv"
    )
    fixed_flags.update(case.get("fixed_flags", {}))
    parameter_bindings = {
        "bootstrap_inputs": bootstrap_inputs,
        "candidate_files": candidate_files,
        "evaluator_flags": dict(evaluator_flags),
        "fixed_flags": fixed_flags,
        "output_metadata": output_metadata,
    }
    parser_block = {
        "format": case["parser"],
        "iteration_marker": "ITERATION_RESULT:",
        "require_signed_metrics": False,
        "required_fields": ["status", "primary_metric", "metric_name"],
        "field_types": {
            "primary_metric": "number",
            "threshold_met": "boolean",
        },
        "failure_statuses": ["eval_error"],
        "fallback": {
            "read_results_file": "result.kv",
            "marker_dir_template": (
                "{workspace_root}/runs/{skill_id}/{subject_id}/{variant}/"
            ),
        },
    }
    if case["target_kind"] == "registry_api":
        primary = {
            "kind": "registry_api",
            "registry": "conformance-registry",
            "register_endpoint": "http://registry.local/api/v1/prompts",
        }
    else:
        primary = {
            "kind": "file_path",
            "path_template": (
                f"configs/{case['skill_id']}/{{subject_id}}_{{variant}}.yaml"
            ),
        }
    metric_schema = {
        "primary": {
            "field": "primary_metric",
            "label": "Conformance Metric",
            "direction": case["direction"],
            "format": ".4f",
        },
        "chart_series": [],
        "iteration_table_columns": [
            {"field": "primary_metric", "label": "Metric"},
        ],
        "goal": case["goal"],
    }
    if case["goal"] == "satisfice":
        metric_schema["satisfice_threshold_field"] = "threshold_met"
    return {
        "schema_version": "research_skill.v1",
        "id": case["skill_id"],
        "version": "0.1.0",
        "category": "exploratory",
        "display_name": f"Conformance Probe ({case['case_id']})",
        "description": (
            "Fixture skill driving one declared configuration through the "
            "complete research workflow for domain conformance."
        ),
        "llm": {
            "provider": "anthropic",
            "primary_model": "claude-sonnet-4-20250514",
            "max_output_tokens": 8192,
            "system_prompt": "SKILL.md",
        },
        "workspace": {
            "session_path_template": "runs/{skill_id}/{subject_id}/{variant}",
        },
        "subjects": {"static": [
            {"id": "conformance-subject", "label": "Conformance subject"},
        ]},
        "variants": {"static": ["default"]},
        "param_schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "sequence": {"type": "string", "default": "10,5,20"},
                "metric_name": {"type": "string", "default": "score",
                                "enum": ["score", "latency_ms"]},
                "input_file": {"type": "string",
                               "default": "sample_input.txt"},
                "candidate_file": {"type": "string",
                                   "default": "candidate.yaml"},
                "threshold_sequence": {"type": "string", "default": "true"},
                "effort": {"type": "integer", "minimum": 1, "maximum": 5,
                           "default": 3},
                "echo": {"type": "string", "default": ""},
            },
            "required": [],
        },
        "parameter_bindings": parameter_bindings,
        "metric_schema": metric_schema,
        "decision_vocabulary": {
            "base": ["keep", "discard", "improve", "unknown"],
            "extensions": [],
            "success_values": ["keep"],
        },
        "phase_plan": [
            {"id": "main", "min_iterations": 1, "max_iterations": 5},
        ],
        "phase_advancement": {"mode": "declarative"},
        "command_policy": {
            "config_flag": "--target",
            "allowed_python": [".venv/bin/python", "./.venv/bin/python"],
            "allowed_scripts": ["eval/run.py", "bootstrap.py"],
            "allowed_executables": [],
            "copyable_files": ["candidate.yaml", "sample_input.txt"],
            "readable_files": ["candidate.yaml", "sample_input.txt"],
            "forbidden_tokens": ["|", "||", "&&", ";", "&"],
            "forbidden_substrings": ["`", "$", ">", "<", "\\n", "\\r"],
            "secret_markers": [".env", "/proc/", "authorization", "bearer",
                               "password", "secret", "token"],
        },
        "output_parser": parser_block,
        "promotion_target": {"primary": primary,
                             "scopes": [dict(s) for s in case["scopes"]]},
        "trial_identity": {
            "hash_fields": ["skill_id", "subject_id", "variant"],
            "resolve": {"mode": "declarative"},
        },
        "blocker_classification": {
            "actionable_blockers": [], "phase_evidence_keys": {},
        },
        "structured_hpo": {"enabled": False},
        "prompt": {
            "experiment_command": ".venv/bin/python eval/run.py",
            "demo_experiment_command": ".venv/bin/python eval/run.py",
            "continuation_enabled": False,
        },
        "ui": {"form_fields": [
            {"name": "sequence", "type": "string", "required": False,
             "label": "Metric sequence"},
            {"name": "effort", "type": "integer", "required": False,
             "label": "Effort", "default": 3},
        ]},
    }



# ── Complete workflows over the declared axes ─────────────────────────────


@pytest.mark.parametrize("case", CONFORMANCE_CASES, ids=lambda c: c["case_id"])
def test_complete_workflow_for_declared_axes(
    conformance_env, monkeypatch, case,
):
    """Start → governed eval → parsed observations → selection → preview."""
    from fastapi.testclient import TestClient

    from src.main import app as real_app

    _materialize_skill(
        conformance_env["skills_root"], case["skill_id"], _case_manifest(case),
    )
    with TestClient(real_app) as client:
        params = {
            "threshold_sequence": ",".join(case["threshold_sequence"]),
            **case["params"],
        }
        started = _start(client, {
            "skill_id": case["skill_id"],
            "max_iterations": 3,
            "skill_params": params,
        })
        assert started.status_code == 201, started.text
        research_id = started.json()["id"]

        session = _poll_terminal(client, research_id, timeout_s=120.0)
        assert session.get("status") == "completed", (
            f"workflow {case['case_id']} reached "
            f"{session.get('status')!r}: {session.get('error_message')}"
        )

        iterations = client.get(
            f"/api/v1/research/{research_id}/iterations", headers=_auth(),
        ).json()
        assert len(iterations) == 3, (
            f"iterations={iterations}; session={json.dumps(session, default=str)[:900]}"
        )
        observed = [row["primary_metric"] for row in iterations]
        assert observed == case["sequence"], (
            f"declared sequence must be observed verbatim through the "
            f"{case['parser']} parser: {observed}; rows: "
            f"{json.dumps(iterations, default=str)[:1200]}"
        )
        # Identical domain semantics across parsers: every normalized row
        # carries the canonical identity fields regardless of block format.
        for row in iterations:
            assert row.get("skill_id") == case["skill_id"]
            assert row.get("iteration") is not None

        if case["goal"] == "satisfice":
            # Satisfice semantics: the declared threshold decides (accepted
            # once observed), never an argmax winner comparison.
            decisions = [row.get("decision") for row in iterations]
            expected_decisions = [
                "keep" if met else "discard"
                for met in (s == "true" for s in case["threshold_sequence"])
            ]
            assert decisions == expected_decisions, decisions

        # Objective-aware selection: the recorded winner follows direction.
        refreshed = client.get(
            f"/api/v1/research/{research_id}", headers=_auth(),
        ).json()
        assert refreshed.get("best_metric") == case["expected_winner_metric"], (
            f"winner must follow {case['direction']}: "
            f"best_metric={refreshed.get('best_metric')}"
        )

        results = client.get(
            f"/api/v1/research/{research_id}/results", headers=_auth(),
        ).json()
        assert results.get("research_id") == research_id
        assert results.get("iterations")

        preview = client.post(
            f"/api/v1/research/{research_id}/promote/preview",
            headers=_auth(),
            json={"scope": "development"},
        )
        assert preview.status_code == 200, preview.text
        body = preview.json()
        assert body.get("target_kind") == case["target_kind"]
        assert body.get("research_id") == research_id

        if len(case["scopes"]) > 1:
            # Chained scope shape: the production policy needs no fabricated
            # ML evidence — only the declared prior scope and operator
            # approval (and it keeps needing approval after the prior lands).
            ml_reasons = {
                "missing_paper_validation", "missing_production_gate_bundle",
                "missing_model_card", "missing_feature_readiness",
                "inference_reload_failed", "missing_canary_duration",
                "missing_live_risk_limits", "missing_monitoring_alerts",
                "missing_rl_oos_provenance", "missing_rl_economic_replay",
            }
            before = client.post(
                f"/api/v1/research/{research_id}/promote/preview",
                headers=_auth(),
                json={"scope": "production"},
            )
            assert before.status_code == 200, before.text
            scoped = before.json().get("scoped_promotion_metadata") or {}
            blockers = set(scoped.get("blockers") or [])
            assert not (blockers & ml_reasons), blockers
            assert "missing_development_promotion" in blockers
            assert "missing_production_approval" in blockers

            confirmed = None
            if case["target_kind"] == "registry_api":
                import httpx

                from tests.test_webhook_promotion import _patch_mock_transport

                _patch_mock_transport(
                    monkeypatch,
                    lambda request: httpx.Response(
                        200, json={"status": "registered"},
                    ),
                )
            confirmed = client.post(
                f"/api/v1/research/{research_id}/promote/confirm",
                headers=_auth(),
                json={"scope": "development"},
            )
            assert confirmed.status_code in (200, 201), confirmed.text

            after = client.post(
                f"/api/v1/research/{research_id}/promote/preview",
                headers=_auth(),
                json={"scope": "production"},
            )
            assert after.status_code == 200, after.text
            scoped = after.json().get("scoped_promotion_metadata") or {}
            blockers = set(scoped.get("blockers") or [])
            assert not (blockers & ml_reasons), blockers
            assert "missing_development_promotion" not in blockers
            assert "missing_production_approval" in blockers



# ── Rejections before side effects ────────────────────────────────────────
# Unsupported extension declarations (schema-valid but unimplemented) and
# parameter violations must fail the start request before any workspace,
# row, or command side effect exists.

UNSUPPORTED_EXTENSIONS: list[tuple[str, dict]] = [
    ("trial_identity_plugin", {
        "trial_identity": {"hash_fields": ["skill_id"],
                           "resolve": {"mode": "plugin"}},
    }),
    ("phase_advancement_plugin", {
        "phase_advancement": {"mode": "plugin"},
    }),
    ("promotion_target_artifact_store", {
        "promotion_target": {
            "primary": {"kind": "artifact_store",
                        "bucket": "s3://unimplemented"},
            "scopes": [{"id": "development"}],
        },
    }),
    ("output_parser_unknown_format", {
        "output_parser": {"format": "bespoke_magic",
                          "iteration_marker": "ITERATION_RESULT:"},
    }),
]


@pytest.mark.parametrize(
    "label, override",
    UNSUPPORTED_EXTENSIONS,
    ids=[label for label, _ in UNSUPPORTED_EXTENSIONS],
)
def test_unsupported_extensions_fail_before_side_effects(
    conformance_env, label, override,
):
    case = dict(CONFORMANCE_CASES[0])
    case["skill_id"] = f"conformance-unsupported-{label}"
    manifest = _case_manifest(case)
    manifest.update(override)
    _materialize_skill(conformance_env["skills_root"], case["skill_id"], manifest)

    from fastapi.testclient import TestClient

    from src.main import app as real_app

    with TestClient(real_app) as client:
        runs_root = conformance_env["ws_root"] / "runs"
        before = (
            sorted(p.name for p in runs_root.iterdir())
            if runs_root.exists() else []
        )
        started = _start(client, {
            "skill_id": case["skill_id"],
            "max_iterations": 1,
            "skill_params": {},
        })
        assert started.status_code >= 400, started.text
        detail = started.json().get("detail", {})
        message = json.dumps(detail)
        assert "error" in message or "invalid" in message.lower(), message
        # No side effects: no session workspace appeared and no session id
        # was issued.
        after = (
            sorted(p.name for p in runs_root.iterdir())
            if runs_root.exists() else []
        )
        assert after == before, f"side effect: {after} != {before}"
        assert "id" not in (started.json() or {})


PARAMETER_VIOLATIONS: list[tuple[str, dict]] = [
    ("bounds_upper", {"effort": 99}),
    ("bounds_lower", {"effort": 0}),
    ("enum", {"metric_name": "bogus_metric"}),
    ("unknown_key", {"not_a_declared_param": 1}),
    ("type", {"effort": "high"}),
]


@pytest.mark.parametrize(
    "label, bad_params",
    PARAMETER_VIOLATIONS,
    ids=[label for label, _ in PARAMETER_VIOLATIONS],
)
def test_parameter_violations_fail_before_side_effects(
    conformance_env, label, bad_params,
):
    case = dict(CONFORMANCE_CASES[0])
    case["skill_id"] = f"conformance-params-{label}"
    _materialize_skill(
        conformance_env["skills_root"], case["skill_id"], _case_manifest(case),
    )

    from fastapi.testclient import TestClient

    from src.main import app as real_app

    with TestClient(real_app) as client:
        runs_root = conformance_env["ws_root"] / "runs"
        before = (
            sorted(p.name for p in runs_root.iterdir())
            if runs_root.exists() else []
        )
        started = _start(client, {
            "skill_id": case["skill_id"],
            "max_iterations": 1,
            "skill_params": bad_params,
        })
        assert started.status_code == 422, started.text
        detail = started.json().get("detail", {})
        assert detail.get("error") == "skill_params_invalid", detail
        after = (
            sorted(p.name for p in runs_root.iterdir())
            if runs_root.exists() else []
        )
        assert after == before, f"side effect: {after} != {before}"


# ── Sequential and parallel observation paths ─────────────────────────────
# The same fixture skill runs one session with two candidate commands on the
# sequential path (concurrency 1) and one on the parallel-trial path
# (concurrency 2). Both paths must record observations with identical domain
# semantics, and every observation must carry its own trial's data.






class _OnePerTurnScriptedProvider:
    """Issues one candidate command per turn (the sequential execution path)."""

    name = "scripted-sequential"

    def __init__(self, commands: list[str]) -> None:
        self._commands = commands
        self._index = 0

    async def messages_create(
        self, *, model, system, messages, tools, max_tokens,
        temperature=None, stop_sequences=None,
    ):
        from src.core.llm_provider import (
            ProviderResponse,
            StopReason,
            TextBlock,
            ToolUseBlock,
            Usage,
        )

        usage = Usage(input_tokens=10, output_tokens=10)
        if self._index < len(self._commands):
            command = self._commands[self._index]
            self._index += 1
            return ProviderResponse(
                content=[
                    ToolUseBlock(
                        id=f"call_trial_{self._index}",
                        name="bash",
                        input={"command": command, "timeout_s": 120},
                    )
                ],
                stop_reason=StopReason.TOOL_USE,
                usage=usage,
                raw_model="scripted",
            )
        return ProviderResponse(
            content=[TextBlock(text="TERMINATE_REQUEST: trials complete")],
            stop_reason=StopReason.END_TURN,
            usage=usage,
            raw_model="scripted",
        )

    async def complete(self, *, model, prompt, max_tokens, system=None) -> str:
        return "{\"summary\": \"observation session complete\"}"

    def estimate_cost(self, model, usage) -> float:
        return 0.0

    def capabilities(self):
        from src.core.llm_provider import ProviderCapabilities

        return ProviderCapabilities(
            native_tool_use=True, streaming=False, system_prompt=True,
            max_context_tokens=200_000,
        )

    def classify_error(self, exc):
        from src.core.llm_provider import ErrorClass

        return ErrorClass(transient=False, status_code=None, retry_after_s=None)


async def _run_observation_session(
    monkeypatch, tmp_path, *, concurrency: int, research_id: str,
):
    from unittest.mock import AsyncMock, patch

    from src.config import settings
    from src.core import orchestrator as orchestrator_module
    from src.core import skill_registry as skill_registry_module
    from src.core.orchestrator import AgentOrchestrator, ResearchConfig
    from src.core.results_store import ResultsStore
    from tests.test_parallel_trials import _ScriptedProvider

    ws_root = tmp_path / "workspace"
    venv_bin = ws_root / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    os.symlink(sys.executable, venv_bin / "python")
    monkeypatch.setattr(settings, "workspace_root", str(ws_root))
    monkeypatch.setattr(
        settings, "host_configs_path", str(tmp_path / "hostconfigs"),
    )
    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    monkeypatch.setattr(
        skill_registry_module, "DEFAULT_SKILLS_ROOT", skills_root,
    )
    registry = skill_registry_module.default_registry
    monkeypatch.setattr(registry, "_root", skills_root)
    monkeypatch.setattr(registry, "_cache", {})
    monkeypatch.setattr(registry, "_discovered", set())
    monkeypatch.setattr(registry, "_scanned", False)

    case = dict(CONFORMANCE_CASES[0])
    case["skill_id"] = "conformance-observation"
    manifest = _case_manifest(case)
    manifest["execution"] = {"concurrency": concurrency}
    # The observation paths vary per trial by candidate, not by bound flags.
    manifest["output_parser"]["format"] = "delimited_kv"
    manifest["parameter_bindings"] = {
        "bootstrap_inputs": {},
        "candidate_files": {"candidate_file": "candidates_a.yaml"},
        "evaluator_flags": {},
        "fixed_flags": {
            "--marker": "ITERATION_RESULT:",
            "--emit-format": "kv",
        },
        "output_metadata": {},
    }
    manifest["command_policy"]["copyable_files"] += [
        "candidates_a.yaml", "candidates_b.yaml",
    ]
    manifest["command_policy"]["readable_files"] += [
        "candidates_a.yaml", "candidates_b.yaml",
    ]
    _materialize_skill(skills_root, case["skill_id"], manifest)

    provider = (
        _ScriptedProvider if concurrency > 1 else _OnePerTurnScriptedProvider
    )([
        ".venv/bin/python eval/run.py --target candidates_a.yaml",
        ".venv/bin/python eval/run.py --target candidates_b.yaml",
    ])
    monkeypatch.setattr(
        orchestrator_module, "build_provider", lambda name, **kw: provider,
    )

    session_ws = (
        ws_root / "runs" / case["skill_id"] / "conformance-subject" / "default"
    )
    session_ws.mkdir(parents=True)
    (session_ws / "candidates_a.yaml").write_text(
        "metric: 41\n", encoding="utf-8",
    )
    (session_ws / "candidates_b.yaml").write_text(
        "metric: 7\n", encoding="utf-8",
    )

    store = ResultsStore(str(tmp_path / "observations.sqlite"))
    await store.initialize()
    await store.create_session(
        session_id=research_id,
        instrument="conformance-subject",
        timeframe="default",
        model_type=case["skill_id"],
        skill_id=case["skill_id"],
        tag="observation",
        quick_mode=False,
        max_iterations=5,
        max_budget_usd=5.0,
        focus_hint=None,
        workspace_path=str(session_ws),
    )
    config = ResearchConfig(
        id=research_id,
        instrument="conformance-subject",
        timeframe="default",
        model_type=case["skill_id"],
        skill_id=case["skill_id"],
        tag="observation",
        max_iterations=5,
        max_budget_usd=5.0,
        timeout_s=300,
        workspace_path=str(session_ws),
    )
    orchestrator = AgentOrchestrator(store)
    with patch.object(
        orchestrator, "_load_claude_md_async", new=AsyncMock(return_value=""),
    ):
        await orchestrator.run(config)
    return store, session_ws


@pytest.mark.asyncio
async def test_sequential_and_parallel_observations_share_domain_semantics(
    monkeypatch, tmp_path,
):
    """Both observation paths record identical normalized shapes and
    isolated per-trial data."""
    seq_store, seq_ws = await _run_observation_session(
        monkeypatch, tmp_path / "seq", concurrency=1, research_id="res_seq",
    )
    par_store, par_ws = await _run_observation_session(
        monkeypatch, tmp_path / "par", concurrency=2, research_id="res_par",
    )
    seq_rows = await seq_store.get_iterations("res_seq")
    par_rows = await par_store.get_iterations("res_par")
    assert len(seq_rows) == 2, seq_rows
    assert len(par_rows) == 2, par_rows

    def by_trial(rows):
        out = {}
        for row in rows:
            out[row.get("config_snapshot")] = row
        return out

    seq_by_trial = by_trial(seq_rows)
    par_by_trial = by_trial(par_rows)
    # Isolated data: each observation carries its own trial's candidate and
    # the metric that candidate declares.
    assert seq_by_trial["metric: 41\n"]["primary_metric"] == 41.0
    assert seq_by_trial["metric: 7\n"]["primary_metric"] == 7.0
    assert par_by_trial["metric: 41\n"]["primary_metric"] == 41.0
    assert par_by_trial["metric: 7\n"]["primary_metric"] == 7.0

    # Identical domain semantics: the same normalized row shape and the same
    # observation-identity schema on both paths.
    assert set(seq_by_trial["metric: 41\n"]) == set(par_by_trial["metric: 41\n"])
    for row in seq_rows + par_rows:
        identity = json.loads(row["trial_identity_json"])
        assert identity["schema_version"] == (
            "autoresearch_observation_identity.v2"
        )
        assert identity["subject_id"] == "conformance-subject"
        assert identity["variant"] == "default"

    # Parallel trials run in isolated dirs; the sequential path never
    # allocates a trial directory.
    par_trial_root = par_ws / "trials"
    if par_trial_root.exists():
        trial_dirs = sorted(p for p in par_trial_root.iterdir() if p.is_dir())
        assert len(trial_dirs) == 2, trial_dirs
        staged = sorted(
            p.name for d in trial_dirs for p in d.glob("candidates_*.yaml")
        )
        assert staged == ["candidates_a.yaml", "candidates_b.yaml"]
    assert not (seq_ws / "trials").exists()




# ── Conformance report ────────────────────────────────────────────────────
# Every supported declaration value maps to execution evidence: either a
# complete workflow case in this suite or the named conformance test that
# exercises the surface. The report is emitted to the qualification
# workspace when CONFORMANCE_REPORT_PATH is set.

from src.core.support_matrix import ACCEPTED_ADVISORY, SUPPORT_MATRIX  # noqa: E402


def _case_ids(**axis_values) -> list[str]:
    out = []
    for case in CONFORMANCE_CASES:
        if all(case.get(axis) == value for axis, value in axis_values.items()):
            out.append(case["case_id"])
    return out


def _binding_cases(slot: str) -> list[str]:
    return [
        case["case_id"] for case in CONFORMANCE_CASES
        if slot in case["bindings"]
    ]


CONFORMANCE_EVIDENCE: dict = {
    "metric_schema.goal": {
        "optimize": {"cases": _case_ids(goal="optimize")},
        "satisfice": {"cases": _case_ids(goal="satisfice")},
    },
    "metric_schema.primary.direction": {
        "higher_is_better": {"cases": _case_ids(direction="higher_is_better")},
        "lower_is_better": {"cases": _case_ids(direction="lower_is_better")},
    },
    "output_parser.format": {
        "json_marker": {"cases": _case_ids(parser="json_marker")},
        "delimited_kv": {"cases": _case_ids(parser="delimited_kv")},
    },
    "parameter_bindings": {
        "evaluator_flags": {"cases": _binding_cases("evaluator_flags")},
        "fixed_flags": {"cases": _binding_cases("fixed_flags")},
        "bootstrap_inputs": {"cases": _binding_cases("bootstrap_inputs")},
        "candidate_files": {"cases": _binding_cases("candidate_files")},
        "output_metadata": {"cases": _binding_cases("output_metadata")},
    },
    "promotion_target.scope_shape": {
        "single-scope": {
            "cases": [
                c["case_id"] for c in CONFORMANCE_CASES
                if len(c["scopes"]) == 1
            ],
        },
        "chained-with-approval": {
            "cases": [
                c["case_id"] for c in CONFORMANCE_CASES
                if len(c["scopes"]) > 1
            ],
        },
    },
    "promotion_target.kind": {
        "file_path": {"cases": _case_ids(target_kind="file_path")},
        "registry_api": {"cases": _case_ids(target_kind="registry_api")},
        "webhook": {
            "test": "tests/test_webhook_promotion.py",
            "note": "delivery, idempotent retries, and rollback e2e",
        },
    },
    "preflight.kind": {
        "http_health": {"test": "tests/test_preflight_support_matrix.py"},
        "tcp": {"test": "tests/test_preflight_support_matrix.py"},
        "local_file": {"test": "tests/test_preflight_support_matrix.py"},
    },
    "command_policy.allowed_executables": {
        "SUPPORTED_EXECUTABLE_BINDINGS": {
            "test": "tests/test_command_policy.py",
            "note": "governed-runner contract for every supported binding",
        },
    },
    "trial_identity.resolve.mode": {
        "declarative": {
            "cases": [
                "test_sequential_and_parallel_observations_share_"
                "domain_semantics",
            ],
            "test": "tests/test_observation_identity.py",
        },
    },
    "phase_advancement.mode": {
        "declarative": {
            "cases": _case_ids(),
            "test": "tests/test_goal_phase_semantics.py",
        },
    },
    "observation_paths": {
        "sequential": {
            "cases": [
                "test_sequential_and_parallel_observations_share_"
                "domain_semantics",
            ],
        },
        "parallel": {
            "cases": [
                "test_sequential_and_parallel_observations_share_"
                "domain_semantics",
            ],
        },
    },
}

#: Matrix feature -> the report axis carrying its execution evidence.
_MATRIX_AXIS = {
    "output_parser.format": "output_parser.format",
    "command_policy.allowed_executables": "command_policy.allowed_executables",
    "trial_identity.resolve.mode": "trial_identity.resolve.mode",
    "phase_advancement.mode": "phase_advancement.mode",
    "metric_schema.goal": "metric_schema.goal",
    "promotion_target.kind": "promotion_target.kind",
    "preflight.kind": "preflight.kind",
}


def _conformance_report() -> dict:
    return {
        "schema_version": "domain_conformance_report.v1",
        "cases": [
            {
                "case_id": case["case_id"],
                "skill_id": case["skill_id"],
                "goal": case["goal"],
                "direction": case["direction"],
                "parser": case["parser"],
                "bindings": case["bindings"],
                "scope_shape": (
                    "chained-with-approval"
                    if len(case["scopes"]) > 1 else "single-scope"
                ),
                "target_kind": case["target_kind"],
            }
            for case in CONFORMANCE_CASES
        ],
        "coverage": CONFORMANCE_EVIDENCE,
        "rejections_before_side_effects": {
            "unsupported_extensions": [
                label for label, _ in UNSUPPORTED_EXTENSIONS
            ],
            "parameter_violations": [
                label for label, _ in PARAMETER_VIOLATIONS
            ],
        },
        "support_matrix": SUPPORT_MATRIX,
        "accepted_advisory": ACCEPTED_ADVISORY,
    }


def test_conformance_report_covers_support_matrix():
    """Every supported declaration value carries execution evidence."""
    report = _conformance_report()
    for feature, row in SUPPORT_MATRIX.items():
        axis = _MATRIX_AXIS[feature]
        supported = row["supported"]
        values = [supported] if isinstance(supported, str) else list(supported)
        for value in values:
            evidence = (report["coverage"].get(axis) or {}).get(value)
            assert evidence, (
                f"{feature}={value!r} has no execution evidence "
                f"in axis {axis!r}"
            )
            assert evidence.get("cases") or evidence.get("test"), evidence


def test_no_skill_specific_branch_for_the_fixture_skills():
    """A conforming new skill needs no core or UI code changes."""
    root = Path(__file__).resolve().parents[1]
    fixture_ids = [case["skill_id"] for case in CONFORMANCE_CASES]
    fixture_ids += [f"conformance-unsupported-{label}"
                    for label, _ in UNSUPPORTED_EXTENSIONS]
    fixture_ids += [f"conformance-params-{label}"
                    for label, _ in PARAMETER_VIOLATIONS]
    fixture_ids.append("conformance-observation")
    for surface in ("src", "ui/src"):
        base = root / surface
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix not in {".py", ".ts", ".tsx"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for skill_id in fixture_ids:
                assert skill_id not in text, (
                    f"{path} names fixture skill {skill_id!r}"
                )


def test_conformance_report_is_emitted_on_request():
    target = os.environ.get("CONFORMANCE_REPORT_PATH")
    if not target:
        pytest.skip("CONFORMANCE_REPORT_PATH unset")
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_conformance_report(), indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    assert path.is_file()


