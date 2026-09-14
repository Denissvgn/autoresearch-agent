"""CLI tests for the P2 Skill SDK (``autoresearch new-skill`` / ``promote-skill``).

Drives the real ``src.cli.main`` argument path with a stub LLM provider
(same contract as ``tests/test_skill_generator.py``): the generator,
validator, plugin caps, and promotion target all run for real — only the
LLM call is scripted.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")
os.environ.setdefault("USE_VAULT", "false")

from src import cli  # noqa: E402
from src.core import llm_provider as llm_provider_module  # noqa: E402

# The stub bootstrap implements the real ABI: JSON stdin → renders one file
# into the workspace → prints the rendered list.
_BOOTSTRAP_PY = (
    "import json, pathlib, sys\n"
    "data = json.load(sys.stdin)\n"
    "ws = pathlib.Path(data['workspace'])\n"
    "ws.mkdir(parents=True, exist_ok=True)\n"
    "(ws / 'prompt.yaml').write_text('rendered', encoding='utf-8')\n"
    "print(json.dumps({'rendered': ['prompt.yaml']}))\n"
)


def _valid_payload(
    *, skill_id: str = "cli-test-skill", policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "schema_version": "research_skill.v1",
        "id": skill_id,
        "version": "1.0.0",
        "category": "optimization",
        "display_name": "CLI Test Skill",
        "description": "A CLI test skill.",
        "llm": {"provider": "anthropic", "primary_model": "m"},
        "workspace": {"session_path_template": "runs/{skill_id}"},
        "variants": {"static": ["v1"]},
        "param_schema": {"type": "object"},
        "metric_schema": {
            "primary": {"field": "m", "label": "M", "direction": "higher_is_better"}
        },
        "decision_vocabulary": {"base": ["keep"]},
        "phase_plan": [{"id": "p1", "min_iterations": 1, "max_iterations": 2}],
        "command_policy": policy or {"allowed_scripts": ["run.sh"]},
        "output_parser": {"format": "delimited_kv"},
        "preflight": [],
        "promotion_target": {
            "primary": {"kind": "file_path", "path_template": "/tmp/x"}
        },
    }
    return {
        "skill_id": skill_id,
        "manifest_yaml": yaml.safe_dump(manifest),
        "bootstrap_py": _BOOTSTRAP_PY,
        "eval_run_py": "import sys\nsys.exit(0)\n",
        "skill_md": "# CLI Test Skill\n\nA test primer.\n",
    }


class _StubProvider:
    """Deterministic LLMProvider.complete stand-in."""

    name = "stub"

    def __init__(self, response: str) -> None:
        self._response = response

    async def complete(self, *, model, prompt, max_tokens, system=None) -> str:
        return self._response


@pytest.fixture
def skills_root(tmp_path: Path) -> Path:
    root = tmp_path / "skills"
    root.mkdir()
    return root


def _run_cli(argv: list[str], payload: dict[str, Any], monkeypatch) -> int:
    monkeypatch.setattr(
        llm_provider_module,
        "build_provider",
        lambda name, **kw: _StubProvider(json.dumps(payload)),
    )
    return cli.main(argv)


def _last_lines(capsys, n: int = 3) -> str:
    return "\n".join(capsys.readouterr().out.strip().splitlines()[-n:])


# --- new-skill: generation -------------------------------------------------


def test_new_skill_writes_draft_under_skills_root(
    monkeypatch, tmp_path, skills_root, capsys,
):
    code = _run_cli(
        ["new-skill", "--goal", "tune a cache eviction policy",
         "--skills-root", str(skills_root)],
        _valid_payload(), monkeypatch,
    )
    assert code == cli.EXIT_OK
    draft = skills_root / "_drafts" / "cli-test-skill"
    assert (draft / "SKILL.yaml").is_file()
    assert (draft / "bootstrap.py").is_file()
    assert (draft / "SKILL.md").is_file()
    assert (draft / "eval" / "run.py").is_file()
    out = capsys.readouterr().out
    assert "draft generated: cli-test-skill" in out
    assert "policy audit: clean" in out
    assert "autoresearch promote-skill --id cli-test-skill" in out


def test_new_skill_dry_run_writes_nothing(
    monkeypatch, tmp_path, skills_root, capsys,
):
    code = _run_cli(
        ["new-skill", "--goal", "tune a cache eviction policy",
         "--dry-run", "--skills-root", str(skills_root)],
        _valid_payload(), monkeypatch,
    )
    assert code == cli.EXIT_OK
    assert not (skills_root / "_drafts").exists()
    assert not list(skills_root.iterdir())
    assert "dry-run — discarded" in capsys.readouterr().out


def test_new_skill_dry_bootstrap_previews_rendered_tree(
    monkeypatch, tmp_path, skills_root, capsys,
):
    code = _run_cli(
        ["new-skill", "--goal", "tune a cache eviction policy",
         "--dry-run", "--dry-bootstrap", "--skills-root", str(skills_root)],
        _valid_payload(), monkeypatch,
    )
    assert code == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "dry-bootstrap: bootstrap.py rendered 1 file(s):" in out
    assert "prompt.yaml" in out


def test_new_skill_invalid_llm_output_blocks_without_writing(
    monkeypatch, tmp_path, skills_root, capsys,
):
    monkeypatch.setattr(
        llm_provider_module,
        "build_provider",
        lambda name, **kw: _StubProvider("not json at all"),
    )
    code = cli.main(
        ["new-skill", "--goal", "tune something", "--skills-root", str(skills_root)],
    )
    assert code == cli.EXIT_BLOCKED
    assert not (skills_root / "_drafts").exists()
    assert "generation failed" in capsys.readouterr().err


def test_new_skill_openai_without_model_errors(monkeypatch, skills_root, capsys):
    code = _run_cli(
        ["new-skill", "--goal", "tune a cache eviction policy",
         "--provider", "openai", "--skills-root", str(skills_root)],
        _valid_payload(), monkeypatch,
    )
    assert code == cli.EXIT_ERROR
    assert "--model is required" in capsys.readouterr().err


# --- promote-skill -----------------------------------------------------------


def test_promote_skill_moves_draft_to_stable(
    monkeypatch, tmp_path, skills_root, capsys,
):
    _run_cli(
        ["new-skill", "--goal", "tune a cache eviction policy",
         "--skills-root", str(skills_root)],
        _valid_payload(), monkeypatch,
    )
    capsys.readouterr()
    code = cli.main(
        ["promote-skill", "--id", "cli-test-skill",
         "--yes", "--no-tag", "--skills-root", str(skills_root)],
    )
    assert code == cli.EXIT_OK
    assert (skills_root / "cli-test-skill" / "SKILL.yaml").is_file()
    assert not (skills_root / "_drafts" / "cli-test-skill").exists()
    assert "promoted:" in capsys.readouterr().out


def test_promote_skill_blocks_on_critical_findings(
    monkeypatch, tmp_path, skills_root, capsys,
):
    payload = _valid_payload(
        policy={"allowed_scripts": ["run.sh", "rm -rf /tmp/evil"]},
    )
    _run_cli(
        ["new-skill", "--goal", "tune a cache eviction policy",
         "--skills-root", str(skills_root)],
        payload, monkeypatch,
    )
    capsys.readouterr()
    code = cli.main(
        ["promote-skill", "--id", "cli-test-skill",
         "--yes", "--no-tag", "--skills-root", str(skills_root)],
    )
    assert code == cli.EXIT_BLOCKED
    assert (skills_root / "_drafts" / "cli-test-skill").is_dir()
    assert not (skills_root / "cli-test-skill").exists()
    assert "critical policy finding" in capsys.readouterr().err


def test_promote_skill_allow_critical_overrides(
    monkeypatch, tmp_path, skills_root, capsys,
):
    payload = _valid_payload(
        policy={"allowed_scripts": ["run.sh", "rm -rf /tmp/evil"]},
    )
    _run_cli(
        ["new-skill", "--goal", "tune a cache eviction policy",
         "--skills-root", str(skills_root)],
        payload, monkeypatch,
    )
    capsys.readouterr()
    code = cli.main(
        ["promote-skill", "--id", "cli-test-skill", "--yes",
         "--allow-critical", "--no-tag", "--skills-root", str(skills_root)],
    )
    assert code == cli.EXIT_OK
    assert (skills_root / "cli-test-skill" / "SKILL.yaml").is_file()


def test_promote_skill_missing_draft_errors(skills_root, capsys):
    code = cli.main(
        ["promote-skill", "--id", "ghost",
         "--yes", "--no-tag", "--skills-root", str(skills_root)],
    )
    assert code == cli.EXIT_ERROR
    assert "no draft" in capsys.readouterr().err


def test_promote_tag_skips_gracefully_outside_git(
    monkeypatch, tmp_path, skills_root, capsys,
):
    _run_cli(
        ["new-skill", "--goal", "tune a cache eviction policy",
         "--skills-root", str(skills_root)],
        _valid_payload(), monkeypatch,
    )
    capsys.readouterr()
    # --yes but WITHOUT --no-tag: the tmp skills root is not a git repo, so
    # the tag step must warn-and-continue, not fail the promotion.
    code = cli.main(
        ["promote-skill", "--id", "cli-test-skill",
         "--yes", "--skills-root", str(skills_root)],
    )
    assert code == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "git tag skipped" in out
    assert (skills_root / "cli-test-skill" / "SKILL.yaml").is_file()


def test_promote_declines_without_confirmation(
    monkeypatch, tmp_path, skills_root, capsys,
):
    _run_cli(
        ["new-skill", "--goal", "tune a cache eviction policy",
         "--skills-root", str(skills_root)],
        _valid_payload(), monkeypatch,
    )
    capsys.readouterr()
    monkeypatch.setattr("builtins.input", lambda prompt: "n")
    code = cli.main(
        ["promote-skill", "--id", "cli-test-skill",
         "--no-tag", "--skills-root", str(skills_root)],
    )
    assert code == cli.EXIT_BLOCKED
    assert (skills_root / "_drafts" / "cli-test-skill").is_dir()
    assert "aborted" in capsys.readouterr().out


def test_new_skill_inline_promote(
    monkeypatch, tmp_path, skills_root, capsys,
):
    code = _run_cli(
        ["new-skill", "--goal", "tune a cache eviction policy",
         "--promote", "--yes", "--no-tag", "--skills-root", str(skills_root)],
        _valid_payload(), monkeypatch,
    )
    assert code == cli.EXIT_OK
    assert (skills_root / "cli-test-skill" / "SKILL.yaml").is_file()
    assert "promoted:" in capsys.readouterr().out
