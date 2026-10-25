"""ARC-012 P7-011 — the API-level non-ML end-to-end proof.

This is the test whose absence let blocker B1 (ARC-011 review C4 / P4-016:
"no non-ML session has ever run end-to-end") ship unnoticed. Unlike
``test_skill_prompt_engineering_e2e.py`` — which drives ``AgentOrchestrator``
directly, seeds the DB by hand, and builds ``ResearchConfig`` itself — this
suite exercises exactly the path a real operator hits:

    POST /api/v1/research/start (canonical skill_id shape, demo mode)
      → 201 → poll GET /research/{id} to a terminal state
      → GET /results + /iterations populate
      → POST /promote/preview reports the skill-appropriate target_kind

Everything between is the real machinery: the real app (lifespan wiring, real
``SessionManager``, real state store), the real skill bootstrap
(``BootstrapRunner`` renders the workspace), the real governed-command policy
(the eval subprocess runs under the skill's declared command policy with the
W11 nonce env), and the real marker-relay loop on the zero-credential
``MockProvider`` — no network anywhere (demo provider + offline evaluator).

The demo path P7-011 had to make real (each piece was previously dead):

* ``BootstrapRunner`` existed but had no production consumer — invoked here
  by ``SessionManager`` at session start (P7-011 implementation note).
* The mock provider's default eval command was skill-agnostic, relative-path,
  and never relayed the governed eval's ``ITERATION_RESULT`` marker — skills
  now declare ``prompt.demo_experiment_command`` (rendered with absolute
  ``{session_workspace}`` paths) and the mock relays the marker verbatim.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")
os.environ.setdefault("USE_VAULT", "false")

from fastapi.testclient import TestClient

from src.config import settings
from src.main import app as real_app

API_TOKEN = "e2e-test-token"

#: Statuses after which the session admits no further work (the poll target).
_TERMINAL = {"completed", "failed", "timed_out", "stopped"}

#: Both non-ML promotion target kinds (P7-007): registry_api (webhook
#: transport, declared register_endpoint) and file_path (path_template).
_SKILL_CASES = [
    ("prompt-engineering", "registry_api"),
    ("code-refactor", "file_path"),
]


def _auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {API_TOKEN}"}


def _preserve_lifespan_globals(monkeypatch: pytest.MonkeyPatch) -> None:
    """Snapshot the module globals main's lifespan wires so teardown restores
    them — otherwise this suite's (closed) SQLite store leaks into later test
    files that build their own app without re-initializing every module
    (observed: test_skills_api hitting a closed store's audit path)."""
    import src.main as main_module
    from src.api import promotion as promotion_module
    from src.api import research as research_module
    from src.api import results as results_module
    from src.api import skills as skills_module
    from src.api import subjects as subjects_module

    for module, names in (
        (skills_module, ("_registry", "_store")),
        (subjects_module, ("_registry",)),
        (research_module, ("_session_manager", "_store")),
        (results_module, ("_store",)),
        (promotion_module, ("_promoter", "_store", "_registry")),
        (main_module, ("_store", "_session_manager", "_promoter")),
    ):
        for name in names:
            if hasattr(module, name):
                monkeypatch.setattr(module, name, getattr(module, name))


@pytest.fixture
def demo_workspace(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """A hermetic demo deployment: temp workspace root with the workspace
    venv the governed-command policy expects (the Docker image ships
    ``/app/workspace/.venv``; the test symlinks the real interpreter)."""
    ws_root = tmp_path / "workspace"
    venv_bin = ws_root / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    os.symlink(sys.executable, venv_bin / "python")
    monkeypatch.setattr(settings, "demo_mode", True)
    monkeypatch.setattr(settings, "workspace_root", str(ws_root))
    monkeypatch.setattr(settings, "autoresearch_api_token", API_TOKEN)
    from src.config import get_settings
    from src.core.isolation import probe_host

    if not probe_host().get("ready"):
        monkeypatch.setenv(
            "AUTORESEARCH_EXECUTION_ISOLATION_MODE", "trusted_local_code"
        )
        monkeypatch.setattr(
            settings, "execution_isolation_mode", "trusted_local_code"
        )
        get_settings.cache_clear()
    _preserve_lifespan_globals(monkeypatch)
    try:
        yield ws_root
    finally:
        get_settings.cache_clear()


def _poll_terminal(client: TestClient, research_id: str, timeout_s: float = 90.0) -> dict:
    deadline = time.monotonic() + timeout_s
    session: dict = {}
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/research/{research_id}", headers=_auth())
        assert response.status_code == 200, response.text
        session = response.json()
        if session.get("status") in _TERMINAL:
            return session
        time.sleep(0.25)
    return session


def _valid_params(skill_id: str, staging_dir: Path) -> dict:
    """Per-skill parameter objects valid against each declared param_schema.

    The prompt-engineering schema declares ``eval_set`` required — stage a
    real dataset file (the declared-input contract) and pass its path.
    """
    if skill_id == "prompt-engineering":
        eval_set = staging_dir / "fixture_eval_set.jsonl"
        eval_set.write_text(
            '{"input": "q", "expected": "a"}\n', encoding="utf-8"
        )
        return {"eval_set": str(eval_set)}
    return {}


@pytest.mark.parametrize(("skill_id", "expected_target_kind"), _SKILL_CASES)
def test_non_ml_session_runs_end_to_end(
    demo_workspace: Path, skill_id: str, expected_target_kind: str,
) -> None:
    with TestClient(real_app) as client:
        # ── Start: canonical skill_id shape → 201 with the dual-shape body. ──
        started = client.post(
            "/api/v1/research/start",
            headers=_auth(),
            json={"skill_id": skill_id, "max_iterations": 1,
                "skill_params": _valid_params(skill_id, demo_workspace)},
        )
        assert started.status_code == 201, started.text
        body = started.json()
        research_id = body["id"]
        assert body["skill_id"] == skill_id
        assert body["model_type"] == "", "non-ML skills carry no legacy alias"

        # ── Run to a terminal state on the scripted demo provider. ──────────
        session = _poll_terminal(client, research_id)
        assert session.get("status") == "completed", (
            f"demo session for {skill_id} reached "
            f"{session.get('status')!r} instead of completed: "
            f"{session.get('error_message')}"
        )
        assert session.get("error_message") is None

        # ── Iterations populated from the governed eval's relayed marker. ───
        iterations_response = client.get(
            f"/api/v1/research/{research_id}/iterations", headers=_auth(),
        )
        assert iterations_response.status_code == 200, iterations_response.text
        iterations = iterations_response.json()
        assert isinstance(iterations, list) and iterations, (
            "at least one iteration must be recorded"
        )
        first = iterations[0]
        assert first.get("skill_id") == skill_id
        assert first.get("primary_metric") is not None, (
            "the recorded metric comes from the governed eval — never None"
        )

        # ── /results carries the enriched history for the UI. ───────────────
        results_response = client.get(
            f"/api/v1/research/{research_id}/results", headers=_auth(),
        )
        assert results_response.status_code == 200, results_response.text
        results = results_response.json()
        assert results.get("research_id") == research_id
        assert results.get("iterations"), "/results must be populated"

        # ── Promotion preview reports the skill-appropriate target kind. ────
        preview_response = client.post(
            f"/api/v1/research/{research_id}/promote/preview",
            headers=_auth(),
            json={"scope": "development"},
        )
        assert preview_response.status_code == 200, preview_response.text
        preview = preview_response.json()
        assert preview.get("target_kind") == expected_target_kind, (
            f"preview target_kind={preview.get('target_kind')!r} "
            f"(expected {expected_target_kind!r} for {skill_id})"
        )
        assert preview.get("research_id") == research_id


def test_demo_workspace_bootstrap_files_exist(demo_workspace: Path) -> None:
    """The start-path bootstrap (P7-011) renders the evaluator's inputs —
    asserted directly on disk for both skills' known file sets."""
    with TestClient(real_app) as client:
        for skill_id, expected_file in (
            ("prompt-engineering", "eval_set.jsonl"),
            ("code-refactor", "tests_target.jsonl"),
        ):
            started = client.post(
                "/api/v1/research/start",
                headers=_auth(),
                json={"skill_id": skill_id, "max_iterations": 1,
                "skill_params": _valid_params(skill_id, demo_workspace)},
            )
            assert started.status_code == 201, started.text
            session_ws = (
                demo_workspace / "runs" / skill_id
                / started.json()["subject_id"] / started.json()["variant"]
                / started.json()["id"]
            )
            assert (session_ws / expected_file).is_file(), (
                f"{skill_id} bootstrap must render {expected_file} in the "
                "session workspace"
            )
