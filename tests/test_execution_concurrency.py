"""Execution-config plumbing tests (P1-4).

``execution.concurrency`` (1..3, default 1) declares a skill's parallel-trial
opt-in. Default preserves the strictly-sequential loop byte-for-byte; the
orchestrator-side parallel dispatch is staged behind this field.
"""
from __future__ import annotations

import os

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from src.core.skill_loader import load_skill_manifest
from src.core.skill_manifest import ExecutionConfig
from src.core.skill_runtime import ManifestSkillRuntime

SKILLS_ROOT = Path(__file__).resolve().parents[1] / "skills"


def _runtime_for(primary_overrides: dict | None = None, execution=None):
    base = yaml.safe_load(
        (SKILLS_ROOT / "prompt-engineering" / "SKILL.yaml").read_text()
    )
    if primary_overrides is not None:
        base["promotion_target"]["primary"] = primary_overrides
    if execution is not None:
        base["execution"] = execution
    manifest = load_skill_manifest(yaml.safe_dump(base))
    return ManifestSkillRuntime(manifest, orchestrator=MagicMock())


def test_manifest_without_execution_defaults_to_sequential():
    rt = _runtime_for()
    assert rt.execution_concurrency() == 1


def test_manifest_execution_concurrency_opt_in():
    rt = _runtime_for(
        primary_overrides={
            "kind": "webhook",
            "endpoint": "http://receiver.local/api/v1/prompts",
        },
        execution={"concurrency": 3},
    )
    assert rt.execution_concurrency() == 3


def test_execution_concurrency_bounds_enforced():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ExecutionConfig(concurrency=0)
    with pytest.raises(ValidationError):
        ExecutionConfig(concurrency=4)


def test_execution_rejects_unknown_keys():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ExecutionConfig(concurrency=2, extra_knob=True)
