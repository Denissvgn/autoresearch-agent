"""Tool-dispatch authorization regressions for the shared file-tool context.

Every file operation (read, write, glob, grep, copy, and path-bearing tool
arguments) must resolve through one server-derived authorization context:
a run may only reach its own session workspace, never sibling sessions,
control-plane storage, interpreter environments, or evaluator assets, while
allowed candidate edits keep working. Server-owned evidence and skill-
declared evaluation data are not candidate-writable.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from src.core.agent_tools import _execute_tool, _tool_glob, _tool_grep
from src.core.command_policy import evaluate_command_policy
from src.core.tool_access import (
    PROTECTED_SESSION_DIRS,
    build_tool_access_context,
)

# ── fixture layout ─────────────────────────────────────────────────────────
#
#   shared/
#     db/experiments.db          control-plane storage
#     .env                       secret material
#     .venv/bin/python           interpreter environment
#     scripts/eval/run.py        evaluator code
#     runs/<skill>/<subject>/<variant>/   session A and session B workspaces


def _setup(tmp_path: Path) -> tuple[str, str, str]:
    shared = tmp_path / "shared"
    for rel in (
        "db",
        ".venv/bin",
        "scripts/eval",
        "runs/skill/subject/variant-a",
        "runs/skill/subject/variant-b",
    ):
        (shared / rel).mkdir(parents=True, exist_ok=True)
    (shared / "db" / "experiments.db").write_text("CONTROL-PLANE-SECRET", encoding="utf-8")
    (shared / ".env").write_text("API_TOKEN=CONTROL-PLANE-SECRET", encoding="utf-8")
    (shared / ".venv" / "bin" / "python").write_text("#!/bin/sh", encoding="utf-8")
    (shared / "scripts" / "eval" / "run.py").write_text("EVALUATOR = True", encoding="utf-8")
    session_a = shared / "runs" / "skill" / "subject" / "variant-a"
    session_b = shared / "runs" / "skill" / "subject" / "variant-b"
    (session_a / "prompt.yaml").write_text("candidate: a", encoding="utf-8")
    (session_b / "prompt.yaml").write_text("candidate: b", encoding="utf-8")
    (session_b / "private.txt").write_text("SESSION-B-PRIVATE", encoding="utf-8")
    return str(shared), str(session_a), str(session_b)


def _access(shared: str, session_a: str):
    return build_tool_access_context(session_a, workspace_root=shared)


# ── context derivation ─────────────────────────────────────────────────────


def test_context_roots_come_from_run_ownership(tmp_path: Path) -> None:
    shared, session_a, _ = _setup(tmp_path)
    access = _access(shared, session_a)

    assert access.readable_roots == (str(Path(session_a).resolve()),)
    assert access.writable_roots == (str(Path(session_a).resolve()),)
    # The shared root is carried for command plumbing only — never a root.
    assert access.workspace_root == str(Path(shared).resolve())
    assert str(Path(shared).resolve()) not in access.readable_roots


def test_context_protects_server_owned_state(tmp_path: Path) -> None:
    shared, session_a, _ = _setup(tmp_path)
    access = _access(shared, session_a)

    for name in PROTECTED_SESSION_DIRS:
        assert access.is_write_protected(str(Path(session_a) / name / "x.json"))
    assert access.is_write_protected(str(Path(session_a) / "research_manifest.json"))
    assert access.is_write_protected(str(Path(session_a) / "research_manifest_res9.json"))
    assert access.is_write_protected(str(Path(session_a) / "session_bootstrap.v1.json"))
    assert not access.is_write_protected(str(Path(session_a) / "prompt.yaml"))


# ── cross-session isolation: reads ─────────────────────────────────────────


def test_read_file_cannot_inspect_sibling_session(tmp_path: Path) -> None:
    shared, session_a, session_b = _setup(tmp_path)
    access = _access(shared, session_a)

    result = _execute_tool(
        "read_file", {"path": str(Path(session_b) / "private.txt")}, access
    )
    assert "SESSION-B-PRIVATE" not in result.content
    assert "resolves outside" in result.content


def test_read_file_sibling_style_path_never_returns_content(tmp_path: Path) -> None:
    shared, session_a, _ = _setup(tmp_path)
    access = _access(shared, session_a)

    result = _execute_tool(
        "read_file", {"path": "runs/skill/subject/variant-b/private.txt"}, access
    )
    assert "SESSION-B-PRIVATE" not in result.content


def test_read_file_rejects_paths_outside_any_root(tmp_path: Path) -> None:
    shared, session_a, _ = _setup(tmp_path)
    access = _access(shared, session_a)

    result = _execute_tool("read_file", {"path": "/etc/passwd"}, access)
    assert "resolves outside" in result.content
    assert "root:" not in result.content


# ── control-plane secrets are unreachable through tool-readable files ──────


@pytest.mark.parametrize(
    "target",
    [
        "db/experiments.db",
        ".env",
    ],
)
def test_control_plane_files_never_reachable(tmp_path: Path, target: str) -> None:
    shared, session_a, _ = _setup(tmp_path)
    access = _access(shared, session_a)

    absolute = _execute_tool("read_file", {"path": str(Path(shared) / target)}, access)
    assert "CONTROL-PLANE-SECRET" not in absolute.content

    relative = _execute_tool("read_file", {"path": target}, access)
    assert "CONTROL-PLANE-SECRET" not in relative.content


def test_interpreter_environment_and_evaluator_code_unreachable(tmp_path: Path) -> None:
    shared, session_a, _ = _setup(tmp_path)
    access = _access(shared, session_a)

    for target in ("scripts/eval/run.py", ".venv/bin/python"):
        result = _execute_tool("read_file", {"path": str(Path(shared) / target)}, access)
        assert "EVALUATOR" not in result.content
        assert "#!/bin/sh" not in result.content


# ── writes: sibling sessions, shared-root targets, traversal ───────────────


def test_write_file_cannot_modify_sibling_candidate(tmp_path: Path) -> None:
    shared, session_a, session_b = _setup(tmp_path)
    access = _access(shared, session_a)

    absolute = _execute_tool(
        "write_file",
        {"path": str(Path(session_b) / "prompt.yaml"), "content": "tampered"},
        access,
    )
    assert "resolves outside" in absolute.content
    assert (Path(session_b) / "prompt.yaml").read_text(encoding="utf-8") == "candidate: b"

    legacy_style = _execute_tool(
        "write_file",
        {"path": "runs/skill/subject/variant-b/prompt.yaml", "content": "tampered"},
        access,
    )
    # The sibling candidate is never modified: the legacy-style path aimed at
    # another session resolves into the caller's own tree instead.
    assert (Path(session_b) / "prompt.yaml").read_text(encoding="utf-8") == "candidate: b"
    assert legacy_style.content.startswith("Wrote")
    nested = Path(session_a) / "runs" / "skill" / "subject" / "variant-b" / "prompt.yaml"
    assert nested.read_text(encoding="utf-8") == "tampered"


def test_write_file_rejects_traversal_and_shared_root_targets(tmp_path: Path) -> None:
    shared, session_a, _ = _setup(tmp_path)
    access = _access(shared, session_a)

    traversal = _execute_tool(
        "write_file",
        {"path": "../../../shared/db/experiments.db", "content": "tampered"},
        access,
    )
    assert "resolves outside" in traversal.content

    absolute = _execute_tool(
        "write_file",
        {"path": str(Path(shared) / "db" / "experiments.db"), "content": "tampered"},
        access,
    )
    assert "resolves outside" in absolute.content
    assert (Path(shared) / "db" / "experiments.db").read_text(encoding="utf-8") == (
        "CONTROL-PLANE-SECRET"
    )


def test_allowed_candidate_edits_still_work(tmp_path: Path) -> None:
    shared, session_a, session_b = _setup(tmp_path)
    access = _access(shared, session_a)

    update = _execute_tool(
        "write_file", {"path": "prompt.yaml", "content": "candidate: a2"}, access
    )
    assert update.content.startswith("Wrote")
    assert (Path(session_a) / "prompt.yaml").read_text(encoding="utf-8") == "candidate: a2"

    create = _execute_tool(
        "write_file", {"path": "variants/new.yaml", "content": "x: 1"}, access
    )
    assert create.content.startswith("Wrote")
    assert (Path(session_a) / "variants" / "new.yaml").read_text(encoding="utf-8") == "x: 1"

    legacy_style = _execute_tool(
        "write_file",
        {"path": "runs/skill/subject/variant-a/note.txt", "content": "ok"},
        access,
    )
    assert legacy_style.content.startswith("Wrote")
    assert (Path(session_a) / "note.txt").read_text(encoding="utf-8") == "ok"


# ── writes: server-owned state and evaluation data ─────────────────────────


@pytest.mark.parametrize(
    "target",
    [
        "server_snapshots/iteration_0001_results.json",
        "command_logs/turn.log",
        ".trials/turn-001-seq-01/config.json",
        "research_manifest.json",
        "research_manifest_res9.json",
        "session_bootstrap.v1.json",
    ],
)
def test_server_owned_state_is_not_candidate_writable(tmp_path: Path, target: str) -> None:
    shared, session_a, _ = _setup(tmp_path)
    access = _access(shared, session_a)

    result = _execute_tool("write_file", {"path": target, "content": "tampered"}, access)
    assert "protected" in result.content
    assert not (Path(session_a) / target).exists()


def test_skill_declared_evaluation_data_is_write_protected(tmp_path: Path) -> None:
    shared, session_a, _ = _setup(tmp_path)
    (Path(session_a) / "tests_target.jsonl").write_text('{"needle": "x"}', encoding="utf-8")
    access = build_tool_access_context(
        session_a,
        workspace_root=shared,
        extra_protected_names=["tests_target.jsonl"],
    )

    result = _execute_tool(
        "write_file",
        {"path": "tests_target.jsonl", "content": '{"needle": "always pass"}'},
        access,
    )
    assert "protected" in result.content
    assert (Path(session_a) / "tests_target.jsonl").read_text(encoding="utf-8") == (
        '{"needle": "x"}'
    )
    # Reading the evaluation data remains allowed.
    read = _execute_tool("read_file", {"path": "tests_target.jsonl"}, access)
    assert '{"needle": "x"}' in read.content


# ── glob expansion and grep confinement ────────────────────────────────────


def test_glob_expansion_cannot_escape_the_roots(tmp_path: Path) -> None:
    shared, session_a, _ = _setup(tmp_path)
    access = _access(shared, session_a)

    traversal = _tool_glob({"pattern": "../*"}, access)
    assert "variant-b" not in traversal
    assert "db" not in traversal

    absolute = _tool_glob({"pattern": str(Path(shared) / "db" / "*")}, access)
    assert "experiments.db" not in absolute

    sibling_style = _tool_glob({"pattern": "runs/skill/subject/variant-b/*"}, access)
    assert "private.txt" not in sibling_style

    own = _tool_glob({"pattern": "*.yaml"}, access)
    assert "prompt.yaml" in own


def test_grep_rejects_outside_search_paths_and_finds_own_files(tmp_path: Path) -> None:
    shared, session_a, _ = _setup(tmp_path)
    access = _access(shared, session_a)

    denied = _execute_tool(
        "grep",
        {"pattern": "CONTROL-PLANE-SECRET", "path": str(Path(shared) / "db")},
        access,
    )
    assert "resolves outside" in denied.content
    assert "CONTROL-PLANE-SECRET" not in denied.content

    found = _tool_grep({"pattern": "candidate: a"}, access)
    assert "prompt.yaml" in found


# ── command-path arguments share the same authorization ────────────────────


def _skill_extension() -> dict:
    return {
        "allowed_scripts": {"eval/run.py"},
        "copyable_files": {"prompt.yaml", "tests_target.jsonl"},
        "readable_files": {"prompt.yaml", "eval_result.json"},
        "write_protected_files": {"tests_target.jsonl"},
    }


def test_cp_destination_faces_write_protection(tmp_path: Path) -> None:
    shared, session_a, _ = _setup(tmp_path)
    access = _access(shared, session_a)
    (Path(session_a) / "tests_target.jsonl").write_text("{}", encoding="utf-8")

    decision = evaluate_command_policy(
        "cp prompt.yaml tests_target.jsonl",
        workspace_root=shared,
        session_workspace=session_a,
        policy_extension=_skill_extension(),
        access=access,
    )
    assert not decision.allowed
    assert "session workspace" in decision.reason
    assert (Path(session_a) / "tests_target.jsonl").read_text(encoding="utf-8") == "{}"


def test_cp_and_cat_reject_sibling_and_outside_paths(tmp_path: Path) -> None:
    shared, session_a, session_b = _setup(tmp_path)
    access = _access(shared, session_a)

    cp_sibling = evaluate_command_policy(
        f"cp prompt.yaml {session_b}/prompt.yaml",
        workspace_root=shared,
        session_workspace=session_a,
        policy_extension=_skill_extension(),
        access=access,
    )
    assert not cp_sibling.allowed
    assert (Path(session_b) / "prompt.yaml").read_text(encoding="utf-8") == "candidate: b"

    cat_outside = evaluate_command_policy(
        "cat /etc/passwd",
        workspace_root=shared,
        session_workspace=session_a,
        policy_extension=_skill_extension(),
        access=access,
    )
    assert not cat_outside.allowed
    assert "session workspace" in cat_outside.reason


def test_config_flag_path_faces_shared_authorization(tmp_path: Path) -> None:
    shared, session_a, _ = _setup(tmp_path)
    access = _access(shared, session_a)

    # The declared evaluator must resolve to a digest-pinned packaged
    # asset; pin one so the flow reaches the config-path authorization check.
    packaged = tmp_path / "pkg" / "scripts" / "eval" / "run.py"
    packaged.parent.mkdir(parents=True)
    content = "print('eval')\n"
    packaged.write_text(content, encoding="utf-8")

    decision = evaluate_command_policy(
        f".venv/bin/python scripts/eval/run.py --prompt {shared}/db/experiments.db",
        workspace_root=shared,
        session_workspace=session_a,
        policy_extension={
            "allowed_scripts": {"eval/run.py", "scripts/eval/run.py"},
            "script_paths": {"scripts/eval/run.py": str(packaged)},
            "script_digests": {
                "scripts/eval/run.py": hashlib.sha256(
                    content.encode("utf-8")
                ).hexdigest(),
            },
            "copyable_files": {"prompt.yaml", "experiments.db"},
            "config_flag": "--prompt",
        },
        access=access,
    )
    assert not decision.allowed
    assert "session workspace" in decision.reason


def test_legacy_style_workspace_paths_still_authorize(tmp_path: Path) -> None:
    shared, session_a, _ = _setup(tmp_path)
    access = _access(shared, session_a)

    decision = evaluate_command_policy(
        "cat runs/skill/subject/variant-a/eval_result.json",
        workspace_root=shared,
        session_workspace=session_a,
        policy_extension=_skill_extension(),
        access=access,
    )
    assert decision.allowed, decision.reason


# ── symlink leaves ─────────────────────────────────────────────────────────


def test_write_file_rejects_symlink_leaves(tmp_path: Path) -> None:
    shared, session_a, _ = _setup(tmp_path)
    access = _access(shared, session_a)
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    (Path(session_a) / "linked.txt").symlink_to(outside)
    (Path(session_a) / "dangling.txt").symlink_to(tmp_path / "missing.txt")

    for name in ("linked.txt", "dangling.txt"):
        result = _execute_tool(
            "write_file", {"path": name, "content": "tampered"}, access
        )
        assert "symlink" in result.content
        assert "writ" in result.content  # the denial names the operation
    assert outside.read_text(encoding="utf-8") == "outside"
    # The original defect: a dangling leaf link created its outside target.
    assert not (tmp_path / "missing.txt").exists()


def test_write_file_rejects_hardlinked_alias(tmp_path: Path) -> None:
    shared, session_a, _ = _setup(tmp_path)
    access = _access(shared, session_a)
    shared_file = Path(shared) / "db" / "experiments.db"
    os.link(shared_file, Path(session_a) / "alias.db")

    result = _execute_tool(
        "write_file", {"path": "alias.db", "content": "tampered"}, access
    )
    assert "hard links" in result.content
    assert shared_file.read_text(encoding="utf-8") == "CONTROL-PLANE-SECRET"


def test_cp_source_must_not_be_a_link_or_alias(tmp_path: Path) -> None:
    shared, session_a, _ = _setup(tmp_path)
    access = _access(shared, session_a)
    (Path(session_a) / "real.yaml").write_text("x: 1", encoding="utf-8")
    os.unlink(Path(session_a) / "prompt.yaml")
    (Path(session_a) / "prompt.yaml").symlink_to(Path(session_a) / "real.yaml")

    decision = evaluate_command_policy(
        "cp prompt.yaml best.yaml",
        workspace_root=shared,
        session_workspace=session_a,
        policy_extension={
            "copyable_files": {"prompt.yaml", "best.yaml"},
        },
        access=access,
    )
    assert not decision.allowed
    assert "symlink" in decision.reason or "import denied" in decision.reason


# ── skill declarations reach the enforcement layer ─────────────────────────


def test_skill_manifest_evaluation_data_declaration_is_enforced() -> None:
    from unittest.mock import MagicMock

    from src.core.skill_registry import default_registry
    from src.core.skill_runtime import ManifestSkillRuntime

    for skill_id, expected in (
        ("code-refactor", "tests_target.jsonl"),
        ("prompt-engineering", "eval_set.jsonl"),
    ):
        manifest = default_registry.get(skill_id)
        assert expected in manifest.command_policy.write_protected_files
        # The runtime extension carries the declaration to the enforcement
        # layer — the field is load-bearing, not advisory.
        ext = ManifestSkillRuntime(manifest, host=MagicMock()).command_policy_extension()
        assert expected in ext.get("write_protected_files", [])