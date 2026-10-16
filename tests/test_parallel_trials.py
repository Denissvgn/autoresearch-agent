"""P2 parallel-trial dispatch tests (the ``execution.concurrency`` flip-on).

Drives a real ``AgentOrchestrator.run()`` session with a synthetic skill whose
manifest declares ``execution.concurrency: 2`` and a scripted provider that
emits **two** sanctioned experiment commands in a single turn. Proves:

* both commands run concurrently (overlapping wall-clock, not back-to-back);
* each runs inside its own staged trial directory and leaves its artifacts
  there (the session workspace is untouched by trial outputs);
* each trial records its own iteration (per-trial recording), with
  ``trial_dir``/``trial_seq`` provenance on the row;
* the default ``concurrency: 1`` control keeps the sequential
  first-marker-wins behavior and never allocates a trial directory.

The synthetic skill is authored by loading the real ``prompt-engineering``
manifest and overriding the sections under test, so schema validity is
guaranteed by the same loader the service uses.
"""
from __future__ import annotations

import asyncio
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pytest
import yaml

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")

from src.core.llm_provider import (  # noqa: E402
    ErrorClass,
    ProviderCapabilities,
    ProviderResponse,
    StopReason,
    TextBlock,
    ToolUseBlock,
    Usage,
)
from src.core.orchestrator import AgentOrchestrator, ResearchConfig  # noqa: E402
from src.core.results_store import ResultsStore  # noqa: E402
from src.core.skill_registry import SkillRegistry  # noqa: E402
from src.core.trial_workspace import TRIALS_DIRNAME  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
PE_SKILL_YAML = REPO / "skills" / "prompt-engineering" / "SKILL.yaml"

_SLEEP_S = 1.0
SKILL_ID = "par-trial"
_MARKER_NAME = "result.kv"

_EVAL_SCRIPT = '''\
"""Synthetic slow eval: sleeps, writes sentinels + a marker KV file."""
import argparse
import pathlib
import time

parser = argparse.ArgumentParser()
parser.add_argument("--config", required=True)
parser.add_argument("--sleep", type=float, default={sleep})
args = parser.parse_args()

time.sleep(args.sleep)

cfg = pathlib.Path(args.config)
stem = cfg.stem
# Per-variant metric so the two trials are distinguishable in the DB.
metric = 0.50 if stem.endswith("a") else 0.75
pathlib.Path("sentinel_" + stem + ".txt").write_text("ran", encoding="utf-8")

kv = (
    "---\\n"
    "status: completed\\n"
    "primary_metric: " + str(metric) + "\\n"
    "metric_name: demo_metric\\n"
    "training_gates_passed: true\\n"
    "---\\n"
)
# The marker file lands next to the config: inside the trial directory for
# staged trials (relative config), in the session workspace otherwise —
# exactly the resolution order output_parser.fallback + trial candidates
# implement server-side.
(cfg.parent / "{marker}").write_text(kv, encoding="utf-8")
print(kv)
'''.replace("{sleep}", str(_SLEEP_S)).replace("{marker}", _MARKER_NAME)


def _write_synthetic_skill(skills_root: Path, *, concurrency: int | None) -> Path:
    """Author a schema-valid skill by overriding the real manifest."""
    base = yaml.safe_load(PE_SKILL_YAML.read_text(encoding="utf-8"))
    base["id"] = SKILL_ID
    base["display_name"] = "Parallel Trial Test Skill"
    base["description"] = "Synthetic two-command trial surface for tests."
    if concurrency is not None:
        base["execution"] = {"concurrency": concurrency}
    else:
        base.pop("execution", None)
    base["llm"] = {**base["llm"], "provider": "anthropic"}
    base.pop("plugins", None)
    base.pop("insights", None)
    base["command_policy"] = {
        **base["command_policy"],
        "allowed_python": [".venv/bin/python"],
        "allowed_scripts": ["eval/slow.py"],
        "allowed_executables": ["cp", "cat"],
        "copyable_files": ["candidates_a.yaml", "candidates_b.yaml"],
        "readable_files": ["candidates_a.yaml", "candidates_b.yaml"],
        # The synthetic trials use the ML ``--config`` vocabulary; drop the
        # base skill's ``--prompt`` flag (ARC-012 P7-011 config_flag) so the
        # pre-run snapshot keys on the right argument.
        "config_flag": "--config",
    }
    base["output_parser"] = {
        "format": "delimited_kv",
        "block_delimiter": "---",
        "iteration_marker": "ITERATION_RESULT:",
        "required_fields": ["status", "primary_metric", "metric_name"],
        "failure_statuses": ["crash", "timeout", "failed", "error"],
        "fallback": {
            "read_results_file": _MARKER_NAME,
            "marker_dir_template": (
                "{workspace_root}/runs/autotuner/"
                "{subject_id}_{variant}/{skill_id}"
            ),
        },
    }
    base["promotion_target"] = {
        "primary": {
            "kind": "file_path",
            "path_template": "configs/{subject_id}_{variant}.yaml",
            "atomic_write": True,
        },
        "scopes": [{"id": "development", "approval_required": False}],
    }
    base["trial_identity"] = {
        "hash_fields": ["skill_id", "subject_id", "variant", "command"],
        "resolve": {"mode": "declarative"},
    }
    base["prompt"] = {
        "experiment_command": ".venv/bin/python eval/slow.py --config candidates_a.yaml",
        "continuation_enabled": False,
    }

    skill_dir = skills_root / SKILL_ID
    (skill_dir / "eval").mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.yaml").write_text(yaml.safe_dump(base), encoding="utf-8")
    (skill_dir / "SKILL.md").write_text(
        "# Parallel trial test skill\n\nEdit candidates_a.yaml, run the eval.\n",
        encoding="utf-8",
    )
    (skill_dir / "eval" / "slow.py").write_text(_EVAL_SCRIPT, encoding="utf-8")
    return skill_dir


class _ScriptedProvider:
    """Issues two sanctioned eval commands in one turn, then terminates."""

    name = "scripted"

    def __init__(self, commands: list[str]) -> None:
        self._commands = commands
        self._issued = False

    async def messages_create(
        self, *, model, system, messages, tools, max_tokens,
        temperature=None, stop_sequences=None,
    ) -> ProviderResponse:
        if not self._issued:
            self._issued = True
            return ProviderResponse(
                content=[
                    ToolUseBlock(
                        id=f"call_trial_{i}",
                        name="bash",
                        input={"command": cmd, "timeout_s": 120},
                    )
                    for i, cmd in enumerate(self._commands, start=1)
                ],
                stop_reason=StopReason.TOOL_USE,
                usage=Usage(input_tokens=10, output_tokens=10),
                raw_model="scripted",
            )
        return ProviderResponse(
            content=[TextBlock(text="TERMINATE_REQUEST: trials complete")],
            stop_reason=StopReason.END_TURN,
            usage=Usage(input_tokens=10, output_tokens=10),
            raw_model="scripted",
        )

    async def complete(self, *, model, prompt, max_tokens, system=None) -> str:
        return "{\"summary\": \"parallel trial session complete\"}"

    def estimate_cost(self, model, usage) -> float:
        return 0.0

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            native_tool_use=True, streaming=False, system_prompt=True,
            max_context_tokens=200_000,
        )

    def classify_error(self, exc: Exception) -> ErrorClass:
        return ErrorClass(transient=False, status_code=None, retry_after_s=None)


async def _run_session(
    monkeypatch, tmp_path, *, concurrency: int | None,
    absolute_config: bool = False,
) -> tuple[ResultsStore, str, Path, Path]:
    """Drive one real run() session; returns (store, id, session ws, root).

    ``absolute_config`` selects the command style: parallel trials address
    configs by bare name (the trial cwd's staged copy — the isolation
    semantics under test); the sequential control uses the absolute session
    path, the way production sequential commands do.
    """
    from src.config import settings
    from src.core import orchestrator as orchestrator_module
    from src.core import skill_registry as skill_registry_module

    # ── Hermetic workspace root (+ venv python for governed commands) ──────
    ws_root = tmp_path / "workspace"
    venv_bin = ws_root / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    os.symlink(sys.executable, venv_bin / "python")
    monkeypatch.setattr(settings, "workspace_root", str(ws_root))
    # Promotion auto-run at session end must not touch /host/configs.
    monkeypatch.setattr(settings, "host_configs_path", str(tmp_path / "hostconfigs"))

    # ── Synthetic skill in a hermetic registry ────────────────────────────
    skills_root = tmp_path / "skills"
    _write_synthetic_skill(skills_root, concurrency=concurrency)
    registry = SkillRegistry(root=skills_root)
    registry.discover()
    monkeypatch.setattr(skill_registry_module, "default_registry", registry)
    # The runtime resolves the packaged dir (primer, script_paths) from
    # DEFAULT_SKILLS_ROOT — point it at the hermetic root too, else the
    # sanctioned ``eval/slow.py`` is not rewritten to its packaged path.
    monkeypatch.setattr(
        skill_registry_module, "DEFAULT_SKILLS_ROOT", skills_root,
    )

    # ── Session workspace with the two candidate configs ──────────────────
    session_ws = ws_root / "runs" / "autotuner" / "default_production" / SKILL_ID
    session_ws.mkdir(parents=True)
    (session_ws / "candidates_a.yaml").write_text("knob: 1\n", encoding="utf-8")
    (session_ws / "candidates_b.yaml").write_text("knob: 2\n", encoding="utf-8")

    # ── Provider: two sanctioned commands in one turn, then TERMINATE ─────
    def _config_arg(name: str) -> str:
        return str(session_ws / name) if absolute_config else name

    provider = _ScriptedProvider([
        f".venv/bin/python eval/slow.py --config {_config_arg('candidates_a.yaml')}",
        f".venv/bin/python eval/slow.py --config {_config_arg('candidates_b.yaml')}",
    ])
    monkeypatch.setattr(
        orchestrator_module, "build_provider", lambda name, **kw: provider,
    )

    store = ResultsStore(str(tmp_path / "parallel.sqlite"))
    await store.initialize()
    research_id = "res_parallel_0001"
    await store.create_session(
        session_id=research_id,
        instrument="default",
        timeframe="production",
        model_type=SKILL_ID,
        tag="p2-parallel",
        quick_mode=False,
        max_iterations=10,
        max_budget_usd=5.0,
        focus_hint=None,
        workspace_path=str(session_ws),
    )
    config = ResearchConfig(
        id=research_id,
        instrument="default",
        timeframe="production",
        model_type=SKILL_ID,
        skill_id=SKILL_ID,
        tag="p2-parallel",
        max_iterations=10,
        max_budget_usd=5.0,
        timeout_s=300,
        workspace_path=str(session_ws),
    )

    orchestrator = AgentOrchestrator(store)
    from unittest.mock import AsyncMock, patch

    with patch.object(
        orchestrator, "_load_claude_md_async", new=AsyncMock(return_value=""),
    ):
        await orchestrator.run(config)
    return store, research_id, session_ws, ws_root


@pytest.mark.asyncio
async def test_parallel_trials_overlap_and_record_each(monkeypatch, tmp_path):
    """concurrency=2: both trials run in isolated dirs, concurrently, and each
    records its own iteration with provenance."""
    store, research_id, session_ws, _ws_root = await _run_session(
        monkeypatch, tmp_path, concurrency=2,
    )

    # ── Two isolated trial directories, each with its own sentinel ────────
    trial_root = session_ws / TRIALS_DIRNAME
    trial_dirs = sorted(p for p in trial_root.iterdir() if p.is_dir())
    assert [p.name for p in trial_dirs] == [
        "turn-000-seq-01", "turn-000-seq-02",
    ]
    sentinels = sorted(
        f.name for d in trial_dirs for f in d.glob("sentinel_*.txt")
    )
    assert sentinels == ["sentinel_candidates_a.txt", "sentinel_candidates_b.txt"]
    # The staged configs travelled with the trials...
    assert (trial_dirs[0] / "candidates_a.yaml").is_file()
    assert (trial_dirs[1] / "candidates_b.yaml").is_file()
    # ...while the session workspace stayed clean of trial outputs.
    assert not list(session_ws.glob("sentinel_*.txt"))

    # ── Concurrency: the two 1s trials' execution windows overlapped ──────
    # (from the runtime_commands wall-clock records — immune to session
    # start/end overhead that a whole-run elapsed threshold would fold in)
    con = sqlite3.connect(str(tmp_path / "parallel.sqlite"))
    try:
        windows = [
            (datetime.fromisoformat(s), datetime.fromisoformat(e))
            for s, e in con.execute(
                "SELECT started_at, completed_at FROM runtime_commands "
                "ORDER BY id"
            )
        ]
    finally:
        con.close()
    assert len(windows) == 2, windows
    (s1, e1), (s2, e2) = windows
    assert s2 < e1, (
        f"trials did not overlap (second started {s2} after first ended {e1}"
        " — sequential execution?)"
    )
    span = (max(e1, e2) - min(s1, s2)).total_seconds()
    assert span < (_SLEEP_S * 2) - 0.2, (
        f"combined trial span {span:.2f}s ≈ back-to-back for two "
        f"{_SLEEP_S}s experiments"
    )

    # ── Each trial recorded its own iteration (per-trial recording) ───────
    iterations = await store.get_iterations(research_id)
    assert len(iterations) == 2, [i["iteration"] for i in iterations]
    assert sorted(i["primary_metric"] for i in iterations) == [0.5, 0.75]
    # Config snapshots came from the staged trial copies.
    assert sorted(
        (i.get("config_snapshot") or "") for i in iterations
    ) == ["knob: 1\n", "knob: 2\n"]
    # Provenance: each row points at the trial dir it ran in.
    seen: set[str] = set()
    for row in iterations:
        blob = f"{row.get('attempt_snapshot_json') or ''}{row.get('metrics_json') or ''}"
        assert TRIALS_DIRNAME in blob and "trial_seq" in blob, blob[:400]
        for d in trial_dirs:
            if str(d) in blob:
                seen.add(d.name)
    assert seen == {"turn-000-seq-01", "turn-000-seq-02"}


@pytest.mark.asyncio
async def test_sequential_default_never_allocates_trials(monkeypatch, tmp_path):
    """concurrency=1 (default): no trial dirs; first-marker-wins preserved."""
    store, research_id, session_ws, ws_root = await _run_session(
        monkeypatch, tmp_path, concurrency=None, absolute_config=True,
    )
    assert not (session_ws / TRIALS_DIRNAME).exists()
    # The attempt output root is the session workspace: relative outputs
    # land there, never in the shared workspace root (the pre-B06 behavior
    # leaked both trials' writes into the shared root).
    sentinels = sorted(p.name for p in session_ws.glob("sentinel_*.txt"))
    assert sentinels == ["sentinel_candidates_a.txt", "sentinel_candidates_b.txt"]
    assert not list(ws_root.glob("sentinel_*.txt"))
    # ...but the sequential turn flag lets only the FIRST recording stand.
    iterations = await store.get_iterations(research_id)
    assert len(iterations) == 1, [i["iteration"] for i in iterations]
    assert TRIALS_DIRNAME not in (iterations[0].get("metrics_json") or "")