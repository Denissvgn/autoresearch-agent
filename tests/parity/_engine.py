"""ARC-011 X-002 parity engine.

Shared by ``tests/parity/test_parity.py`` (verify) and
``tests/parity/capture.py`` (record) so the two paths invoke the target
functions with identical logic. The engine:

  1. materializes a per-case workspace (token substitution + file creation),
  2. dispatches to the real source function named by the fixture's
     ``function`` field,
  3. converts the result to a plain dict, and
  4. normalizes volatile fields (paths → tokens, hashes/timestamps redacted)
     so golden ``expected`` blocks are stable across machines and runs.
"""
from __future__ import annotations

import asyncio
import dataclasses
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# --- env defaults so importing src.config / ResultsStore works headless -------
os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")

SERVICE_ROOT = Path(__file__).resolve().parents[2]  # services/autoresearch-agent
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

# --- tokens -------------------------------------------------------------------
WORKSPACE_TOKEN = "<workspace>"
HOST_CONFIGS_TOKEN = "<host_configs>"

# Keys whose values are redacted before comparison (volatile / non-deterministic).
_REDACT_KEY_RE = re.compile(r"(sha256|_sha\d*$|_at$|^at$|timestamp|run_id$)", re.IGNORECASE)


# =============================================================================
# Discovery / load
# =============================================================================

def discover_cases(base: Path) -> list[tuple[str, Path]]:
    """Return ``[(case_id, path), ...]`` for every ``*.json`` under ``base``.

    Skips non-directory entries (e.g. README.md) at the top level.
    """
    cases: list[tuple[str, Path]] = []
    for cat_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        for fp in sorted(cat_dir.glob("*.json")):
            cases.append((f"{cat_dir.name}/{fp.stem}", fp))
    return cases


def load_case(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


# =============================================================================
# Token substitution + normalization
# =============================================================================

def _substitute(obj: Any, mapping: dict[str, str]) -> Any:
    """Replace token strings with real paths (input direction)."""
    if isinstance(obj, str):
        for token, real in mapping.items():
            if token in obj:
                obj = obj.replace(token, real)
        return obj
    if isinstance(obj, list):
        return [_substitute(x, mapping) for x in obj]
    if isinstance(obj, dict):
        return {k: _substitute(v, mapping) for k, v in obj.items()}
    return obj


def _detokenize(obj: Any, mapping: dict[str, str]) -> Any:
    """Replace real paths with tokens (output direction, for stable expected)."""
    if isinstance(obj, str):
        for real in sorted(mapping.values(), key=len, reverse=True):
            token = next(t for t, r in mapping.items() if r == real)
            if real and real in obj:
                obj = obj.replace(real, token)
        return obj
    if isinstance(obj, list):
        return [_detokenize(x, mapping) for x in obj]
    if isinstance(obj, dict):
        return {k: _detokenize(v, mapping) for k, v in obj.items()}
    return obj


def _redact(obj: Any) -> Any:
    """Redact values of volatile keys (hashes, timestamps, run ids)."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if v and isinstance(v, str) and _REDACT_KEY_RE.search(k):
                out[k] = "<redacted>"
            else:
                out[k] = _redact(v)
        return out
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    return obj


def normalize(obj: Any, mapping: dict[str, str]) -> Any:
    """Full output normalization: detokenize then redact."""
    return _redact(_detokenize(obj, mapping))


def materialize_files(workspace: Path, create_files: dict[str, str] | None) -> None:
    if not create_files:
        return
    for rel, content in create_files.items():
        target = workspace / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


# =============================================================================
# Function dispatch
# =============================================================================

def invoke(case: dict[str, Any], workspace: Path, host_configs: Path, tmp_path: Path) -> Any:
    """Materialize inputs, call the target function, return its raw (dict) result.

    ``workspace`` / ``host_configs`` are real per-case tmp dirs the caller
    supplies; the fixture's ``<workspace>`` / ``<host_configs>`` tokens are
    substituted with them before the call.
    """
    fn = case["function"]
    mapping = {
        WORKSPACE_TOKEN: str(workspace),
        HOST_CONFIGS_TOKEN: str(host_configs),
    }
    materialize_files(workspace, (case.get("input_setup") or {}).get("create_files"))

    if fn == "parse_prepare_output":
        from src.core.experiment_parser import parse_prepare_output
        stdout = _substitute(case["input"]["stdout"], mapping)
        return parse_prepare_output(stdout).to_dict()

    if fn == "parse_iteration_marker":
        from src.core.experiment_parser import parse_iteration_marker
        text = _substitute(case["input"]["text"], mapping)
        return parse_iteration_marker(text)

    if fn == "evaluate_command_policy":
        from src.core.command_policy import evaluate_command_policy
        inp = case["input"]
        cmd = _substitute(inp["command"], mapping)
        wr = _substitute(inp.get("workspace_root", WORKSPACE_TOKEN), mapping)
        sw = inp.get("session_workspace")
        if sw is not None:
            sw = _substitute(sw, mapping)
        decision = evaluate_command_policy(cmd, workspace_root=wr, session_workspace=sw)
        return dataclasses.asdict(decision)

    if fn == "build_phase_state":
        from src.core.research_phase_plan import build_phase_state
        inp = _substitute(case["input"], mapping)
        return build_phase_state(**inp)

    if fn == "construct_research_config":
        from src.core.orchestrator import ResearchConfig
        req = case["input"]["request"]
        valid = {f.name for f in dataclasses.fields(ResearchConfig)}
        kwargs = {k: v for k, v in req.items() if k in valid}
        return dataclasses.asdict(ResearchConfig(**kwargs))

    if fn == "config_promoter.preview":
        return asyncio.run(_invoke_preview(case, workspace, host_configs, tmp_path))

    raise ValueError(f"unknown function tag: {fn!r}")


# --- promotion preview (async; needs a seeded ResultsStore) -------------------

async def _build_store(fixture_name: str, db_path: Path):
    """Replicate tests/conftest.py replay_iterations seeding, standalone."""
    from src.core.results_store import ResultsStore

    fixture_path = SERVICE_ROOT / "tests" / "fixtures" / f"{fixture_name}.json"
    raw = json.loads(fixture_path.read_text())
    session_cfg = raw["session"]
    session_id = session_cfg["id"]

    store = ResultsStore(str(db_path))
    await store.initialize()
    await store.create_session(
        session_id=session_id,
        instrument=session_cfg["instrument"],
        timeframe=session_cfg["timeframe"],
        model_type=session_cfg["model_type"],
        tag=session_cfg["tag"],
        quick_mode=False,
        max_iterations=session_cfg["max_iterations"],
        max_budget_usd=session_cfg["max_budget_usd"],
        focus_hint=None,
        workspace_path="/ws/replay",
    )
    for it in raw["iterations"]:
        await store.add_iteration(
            research_id=session_id,
            iteration=it["iteration"],
            primary_metric=it.get("primary_metric"),
            metric_name=it.get("metric_name", "auc"),
            all_gates_passed=bool(it.get("all_gates_passed", False)),
            decision=it.get("decision", "keep"),
            description=it.get("description", ""),
            config_snapshot=it.get("config_snapshot"),
            metrics_json=json.dumps(it.get("metrics", {})),
            training_time_s=it.get("training_time_s"),
            mlflow_run_id=it.get("mlflow_run_id"),
            search_phase=it.get("search_phase"),
        )
    return store


async def _invoke_preview(case: dict, workspace: Path, host_configs: Path, tmp_path: Path):
    from src import config as config_mod
    from src.core.config_promoter import ConfigPromoter

    fixture_name = case.get("replay_fixture") or "res_a1ba6cbd520f_minimal"
    store = await _build_store(fixture_name, tmp_path / "promo_store.sqlite")

    orig_wr = config_mod.settings.workspace_root
    orig_hcp = config_mod.settings.host_configs_path
    config_mod.settings.workspace_root = str(workspace)
    config_mod.settings.host_configs_path = str(host_configs)
    try:
        inp = case["input"]
        promoter = ConfigPromoter(store)
        return await promoter.preview(
            inp["research_id"],
            scope=inp.get("scope", "development"),
            approval=inp.get("approval"),
        )
    finally:
        config_mod.settings.workspace_root = orig_wr
        config_mod.settings.host_configs_path = orig_hcp
        await store.close()
