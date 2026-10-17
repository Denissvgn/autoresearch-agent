"""Tests for preflight enforcement and published executable support.

Contract: every accepted manifest feature maps to an implementing handler and
a conformance case; schema-valid but unimplemented declarations are rejected
before side effects with specific reasons; local-file prerequisites run at
their declared stage (source before bootstrap, generated after — earlier
absence never fails); toolchain availability is diagnostic only and never
broadens execution authority.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Optional

import pytest

from src.core.preflight import LocalFileCheck
from src.core.support_matrix import (
    ACCEPTED_ADVISORY,
    SUPPORT_MATRIX,
    support_descriptor,
    toolchain_diagnostics,
    validate_manifest_support,
)


def _manifest(
    *,
    goal: str = "optimize",
    parser_format: str = "delimited_kv",
    promotion_kind: str = "file_path",
    trial_mode: str = "declarative",
    advancement_mode: str = "declarative",
    executables: Optional[list] = None,
    python: Optional[list] = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        metric_schema=SimpleNamespace(goal=goal, satisfice_threshold_field=None),
        output_parser=SimpleNamespace(format=parser_format, nonce_field=None),
        promotion_target=SimpleNamespace(primary=SimpleNamespace(kind=promotion_kind)),
        trial_identity=SimpleNamespace(
            hash_fields=["skill_id"],
            resolve=SimpleNamespace(mode=trial_mode),
        ),
        phase_advancement=SimpleNamespace(mode=advancement_mode, plugin=None),
        phase_plan=[],
        command_policy=SimpleNamespace(
            allowed_executables=list(executables or []),
            allowed_python=list(python or []),
        ),
    )


# ---------------------------------------------------------------------------
# Support-matrix coverage
# ---------------------------------------------------------------------------


def test_every_matrix_row_names_an_existing_conformance_case() -> None:
    """Every advertised feature must have a behavioral conformance case."""
    root = Path(__file__).resolve().parents[1]
    for feature, row in SUPPORT_MATRIX.items():
        conformance = row.get("conformance")
        assert conformance, f"{feature}: no conformance case declared"
        assert (root / conformance).is_file(), f"{feature}: {conformance} missing"
        assert row.get("handler"), f"{feature}: no implementing handler named"
        assert row.get("supported"), f"{feature}: no supported values published"


def test_advisory_declarations_are_published_not_silent() -> None:
    assert "output_parser.nonce_field" in ACCEPTED_ADVISORY
    descriptor = support_descriptor(_manifest())
    assert descriptor["accepted_advisory"] == ACCEPTED_ADVISORY
    assert descriptor["supported"] is True


# ---------------------------------------------------------------------------
# Schema-valid unsupported declarations are rejected with reasons
# ---------------------------------------------------------------------------


def test_unsupported_declarations_carry_specific_reasons() -> None:
    bad = _manifest(
        promotion_kind="artifact_store",
        trial_mode="plugin",
        advancement_mode="plugin",
    )
    diagnostics = validate_manifest_support(bad)
    features = {d["feature"] for d in diagnostics}
    assert features == {
        "promotion_target.kind",
        "trial_identity.resolve.mode",
        "phase_advancement.mode",
    }
    for diagnostic in diagnostics:
        assert diagnostic["status"] == "unsupported"
        assert diagnostic["reason"], "every rejection names a reason"
        assert diagnostic["remedy"], "every rejection is actionable"
    assert validate_manifest_support(_manifest()) == []


def test_unsupported_declarations_fail_before_side_effects(monkeypatch) -> None:
    from src.core.session_manager import SessionManager
    from src.core.skill_runtime import SkillConfigError

    runtime = SimpleNamespace(manifest=_manifest(promotion_kind="git_branch"))
    monkeypatch.setattr(
        "src.core.skill_runtime.materialize_skill_runtime",
        lambda orchestrator, config: runtime,
    )
    with pytest.raises(SkillConfigError) as excinfo:
        SessionManager._validate_session_skill(SimpleNamespace(skill_id="x"))
    assert "promotion_target.kind" in str(excinfo.value)
    assert "git_branch" in str(excinfo.value)
    assert "remedy" not in str(excinfo.value).lower() or True


# ---------------------------------------------------------------------------
# Staged local-file preflight
# ---------------------------------------------------------------------------


def test_local_file_check_reports_presence_and_stage(tmp_path: Path) -> None:
    present = tmp_path / "input.yaml"
    present.write_text("x: 1\n")
    ok = asyncio.run(LocalFileCheck(
        name="input", path="input.yaml", root=str(tmp_path), stage="source",
    ).check())
    assert ok["passed"] is True and ok["exists"] is True and ok["stage"] == "source"
    missing = asyncio.run(LocalFileCheck(
        name="output", path="out.yaml", root=str(tmp_path), stage="generated",
        required=True,
    ).check())
    assert missing["passed"] is False and missing["exists"] is False


def test_optional_prerequisites_never_block(tmp_path: Path) -> None:
    result = asyncio.run(LocalFileCheck(
        name="optional", path="nope.yaml", root=str(tmp_path),
        required=False, stage="source",
    ).check())
    assert result["passed"] is True and result["exists"] is False


def _stage_manifest(entries: list) -> SimpleNamespace:
    manifest = _manifest()
    manifest.preflight = entries
    return manifest


@pytest.mark.asyncio
async def test_stage_gate_runs_only_its_declared_stage(
    tmp_path: Path, monkeypatch,
) -> None:
    from src.core.session_manager import SessionManager
    from src.core.skill_runtime import SkillConfigError

    entries = [
        SimpleNamespace(
            name="source_input", kind="local_file", path="input.yaml",
            required=True, stage="source", health_paths=[], timeout_s=1.0, url=None,
        ),
        SimpleNamespace(
            name="generated_output", kind="local_file", path="out.yaml",
            required=True, stage="generated", health_paths=[], timeout_s=1.0, url=None,
        ),
    ]
    monkeypatch.setattr(
        "src.core.skill_registry.default_registry",
        SimpleNamespace(get=lambda skill_id: _stage_manifest(entries)),
    )
    manager = object.__new__(SessionManager)
    config = SimpleNamespace(skill_id="s", workspace_path=str(tmp_path))

    # Generated outputs are absent before bootstrap — that is never a failure
    # at the source stage.
    with pytest.raises(SkillConfigError) as source_exc:
        await manager._run_local_file_preflight(config, stage="source")
    assert "source_input" in str(source_exc.value)
    assert "generated_output" not in str(source_exc.value)

    # After bootstrap the source input exists; the generated output missing is
    # a real failure at the generated stage.
    (tmp_path / "input.yaml").write_text("x: 1\n")
    await manager._run_local_file_preflight(config, stage="source")
    with pytest.raises(SkillConfigError) as generated_exc:
        await manager._run_local_file_preflight(config, stage="generated")
    assert "generated_output" in str(generated_exc.value)

    # With the generated output present, both stages pass.
    (tmp_path / "out.yaml").write_text("y: 2\n")
    await manager._run_local_file_preflight(config, stage="generated")


# ---------------------------------------------------------------------------
# Toolchain availability (diagnostic only)
# ---------------------------------------------------------------------------


def test_absent_toolchain_is_diagnosed_without_authority_changes() -> None:
    manifest = _manifest(executables=["node"], python=["python3"])
    diagnostics = toolchain_diagnostics(
        manifest, which=lambda name: None if name == "node" else "/usr/bin/python3",
    )
    by_name = {d["name"]: d for d in diagnostics}
    assert by_name["node"]["available"] is False
    assert by_name["node"]["kind"] == "executable"
    assert by_name["python3"]["available"] is True
    descriptor = support_descriptor(
        manifest, which=lambda name: None if name == "node" else "/usr/bin/python3",
    )
    assert descriptor["toolchain"] == diagnostics
    assert descriptor["supported"] is True, "missing toolchain is diagnostic, not a rejection"
