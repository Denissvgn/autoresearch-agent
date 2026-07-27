"""ML skill bootstrap tests (ARC-011 P5-002 / P5-003 / P5-004).

The three ML skills' ``bootstrap.py`` files are thin shims that delegate to
``scripts/autotuner/setup.py``. Live invocation requires the full repo + mlflow
+ minio (out of scope for unit tests); these tests pin:

* the bootstrap files are syntactically valid Python (``ast.parse``);
* each declares the right ``--models`` flag for its domain (ml-direction→direction,
  ml-volatility→volatility, ml-rl→rl);
* the dry-mode contract works end-to-end through ``PluginRunner`` (no
  ``setup.py`` invocation — the dry path short-circuits);
* the missing-params failure path (no subject_id/variant → exit 2 + error JSON);
* the layout resolver picks up ``bootstrap.py`` + ``knowledge/`` for each skill.

The live parity gate (setup.py produces identical files to the pre-Phase-5 path)
is the X-002 parity suite, run at P5-007 switchover.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from src.core.plugin_runner import PluginRunner
from src.core.skill_loader import load_layout
from src.core.skill_manifest import PluginCaps
from src.core.skill_registry import DEFAULT_SKILLS_ROOT

SKILLS_ROOT = DEFAULT_SKILLS_ROOT


@pytest.mark.parametrize(
    "skill_id, expected_models_flag",
    [
        ("ml-direction", "direction"),
        ("ml-volatility", "volatility"),
        ("ml-rl", "rl"),
    ],
)
def test_bootstrap_is_valid_python(skill_id: str, expected_models_flag: str):
    """Each bootstrap parses cleanly (P5-026 will reuse this for generator output)."""
    path = SKILLS_ROOT / skill_id / "bootstrap.py"
    tree = ast.parse(path.read_text())
    # Sanity: the file defines a main() and references the right --models flag.
    source = path.read_text()
    assert "def main()" in source
    assert f'"--models"' in source
    assert f'"{expected_models_flag}"' in source


@pytest.mark.parametrize("skill_id", ["ml-direction", "ml-volatility", "ml-rl"])
def test_layout_resolves_bootstrap_and_knowledge(skill_id: str):
    """P5-002/003/004: each ML skill now ships bootstrap.py + knowledge/."""
    layout = load_layout(SKILLS_ROOT / skill_id)
    assert layout.has_bootstrap is True, f"{skill_id} missing bootstrap.py"
    assert layout.has_knowledge is True, f"{skill_id} missing knowledge/"
    assert "bootstrap" in layout.plugins
    entry = layout.plugins["bootstrap"]
    assert entry.path == "bootstrap.py"
    # X-004 §6 default for bootstrap: workspace write.
    assert entry.caps is not None
    assert entry.caps.fs_write == "workspace"


@pytest.mark.parametrize("skill_id", ["ml-direction", "ml-volatility", "ml-rl"])
@pytest.mark.asyncio
async def test_dry_mode_contract_via_plugin_runner(skill_id: str, tmp_path: Path):
    """The dry-mode path short-circuits before invoking setup.py — it must work
    with zero repo dependencies and emit the expected JSON shape."""
    ws = tmp_path / "session"
    ws.mkdir()
    runner = PluginRunner()
    result = await runner.run(
        skill_dir=SKILLS_ROOT / skill_id,
        plugin="bootstrap.py",
        kind="bootstrap",
        input_json={
            "workspace": str(ws),
            "mode": "dry",
            "skill_params": {"subject_id": "DOGE_USDT", "variant": "15m"},
        },
        caps=PluginCaps(fs_write="workspace", timeout_s=10.0),
        workspace=ws,
    )
    assert result.ok is True, f"dry bootstrap failed: {result.error}"
    assert result.output is not None
    assert result.output["mode"] == "dry"
    assert "rendered" in result.output
    # Dry mode must NOT have written to the real workspace.
    assert not any(ws.iterdir())


@pytest.mark.parametrize("skill_id", ["ml-direction", "ml-volatility", "ml-rl"])
@pytest.mark.asyncio
async def test_missing_params_fails_with_error_json(skill_id: str, tmp_path: Path):
    """No subject_id/variant → exit 2 + a JSON error object (fail-closed, structured)."""
    ws = tmp_path / "session"
    ws.mkdir()
    runner = PluginRunner()
    result = await runner.run(
        skill_dir=SKILLS_ROOT / skill_id,
        plugin="bootstrap.py",
        kind="bootstrap",
        input_json={"workspace": str(ws), "mode": "live", "skill_params": {}},
        caps=PluginCaps(fs_write="workspace", timeout_s=10.0),
        workspace=ws,
    )
    assert result.ok is False
    assert result.returncode == 2
    # The error JSON is on stdout; the runner captures it in raw_output.
    assert "subject_id" in (result.raw_output or result.error or "")


@pytest.mark.parametrize("skill_id", ["ml-direction", "ml-volatility", "ml-rl"])
def test_knowledge_primer_and_heuristics_present(skill_id: str):
    """Each ML skill's knowledge corpus has primer.md + heuristics.yaml."""
    knowledge = SKILLS_ROOT / skill_id / "knowledge"
    assert (knowledge / "primer.md").is_file()
    assert (knowledge / "heuristics.yaml").is_file()
    assert (knowledge / "prior_findings").is_dir()
