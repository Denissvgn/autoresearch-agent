"""Automated §7.14 generalization falsifiability suite (ARC-011 P3-030, §8.2/§8.3).

This is the **Phase 3 exit gate**. It encodes ARC-011 §7.14 / §8.2 / §8.3 as
executable assertions. If any of these fail, the generalization is falsified —
the orchestrator or UI is still domain-coupled and Phase 3 is not done.

Assertions (from §8.2 / §8.3):

* **GEN-003** — ``GET /skills`` lists ``ml-direction``, ``ml-volatility``, ``ml-rl``.
* **Uniformity** — every skill descriptor carries the fields the UI needs
  (``form_fields``, ``metric_schema.chart_series``, ``metric_schema.iteration_table_columns``,
  ``promotion_target.primary.kind``) so the *same* UI renders any skill.
* **Drop-a-directory** — a new skill ships under ``skills/<id>/`` with no
  orchestrator or UI code changes; it appears in ``GET /skills`` after reload.
* **Domain-coupling grep guard** — ``orchestrator.py`` has zero hits for the
  Phase-3 deny-list patterns (§1.7).
* **GEN-009** — ML and non-ML sessions have identical row shape (by construction:
  the dual-shape helpers populate the same fields for every ``model_type``).
"""

from __future__ import annotations

import os
import textwrap
from pathlib import Path

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")
os.environ.setdefault("USE_VAULT", "false")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import skills as skills_module
from src.api.skills import router as skills_router
from src.config import settings
from src.core.skill_registry import DEFAULT_SKILLS_ROOT, SkillRegistry

API_TOKEN = "test-autoresearch-token"
_EXPECTED_SKILL_IDS = {"ml-direction", "ml-volatility", "ml-rl"}

# Phase-3 grep deny-list (§1.7): these patterns must return 0 hits in
# orchestrator.py after Phase 2+3. The orchestrator should be domain-agnostic.
# Phase-2 targets: config.model_type / config.instrument / config.timeframe
# Phase-3 targets (§1.7 row "3"): the above PLUS DIRECTION_PHASES,
# VOLATILITY_PHASES, RL_PHASES, _ALLOWED_SCRIPTS.
_ORCHESTRATOR_DENY_PATTERNS = [
    "config\\.model_type",
    "config\\.instrument",
    "config\\.timeframe",
    "DIRECTION_PHASES",
    "VOLATILITY_PHASES",
    "RL_PHASES",
    "_ALLOWED_SCRIPTS",
]


def create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(skills_router, prefix="/api/v1")
    return app


@pytest.fixture(autouse=True)
def configure(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "autoresearch_api_token", API_TOKEN)


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_test_app())


def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {API_TOKEN}"}


# ------------------------------------------------------------------
# GEN-003: GET /skills lists the three ML skills
# ------------------------------------------------------------------


def test_gen003_skills_lists_all_ml_skills(client: TestClient):
    """GEN-003: GET /skills lists ml-direction, ml-volatility, ml-rl."""
    response = client.get("/api/v1/skills", headers=auth_headers())
    assert response.status_code == 200
    ids = {s["id"] for s in response.json()}
    assert _EXPECTED_SKILL_IDS.issubset(ids)


# ------------------------------------------------------------------
# Uniformity: every skill descriptor has the fields the UI needs
# ------------------------------------------------------------------


@pytest.mark.parametrize("skill_id", sorted(_EXPECTED_SKILL_IDS))
def test_every_skill_has_ui_render_fields(client: TestClient, skill_id: str):
    """§8.2: the same UI renders every skill's form/chart/table from
    ``GET /api/v1/skills/{id}`` responses. Every descriptor must carry the
    fields the generic UI components consume."""
    desc = client.get(f"/api/v1/skills/{skill_id}", headers=auth_headers()).json()
    # Form fields (P3-022 dynamic form renderer).
    ff = client.get(
        f"/api/v1/skills/{skill_id}/form-fields", headers=auth_headers()
    ).json()["form_fields"]
    assert isinstance(ff, list), f"{skill_id}: form_fields must be a list"
    # Metric schema (P3-024/P3-025 manifest-driven chart + table).
    ms = client.get(
        f"/api/v1/skills/{skill_id}/metric-schema", headers=auth_headers()
    ).json()
    assert "primary" in ms, f"{skill_id}: metric_schema.primary missing"
    assert "chart_series" in ms, f"{skill_id}: metric_schema.chart_series missing"
    assert "iteration_table_columns" in ms, (
        f"{skill_id}: metric_schema.iteration_table_columns missing"
    )
    # Promotion target kind (P3-026 modal branches on target_kind).
    assert "promotion_target" in desc, f"{skill_id}: promotion_target missing"
    assert "primary" in desc["promotion_target"]
    assert "kind" in desc["promotion_target"]["primary"], (
        f"{skill_id}: promotion_target.primary.kind missing"
    )


# ------------------------------------------------------------------
# Drop-a-directory: a new skill appears after reload, no code changes
# ------------------------------------------------------------------


def test_drop_a_directory_skill_appears_after_reload(tmp_path: Path):
    """§8.2 / §7.14: a new skill ships as a directory under ``skills/`` with
    no orchestrator or UI code changes. Create a minimal skill package in a
    temp root, point a fresh registry at it, and verify it's discoverable."""
    skill_id = "test-falsify-skill"
    skill_dir = tmp_path / skill_id
    skill_dir.mkdir()
    manifest = textwrap.dedent("""\
        schema_version: research_skill.v1
        id: test-falsify-skill
        version: 0.1.0
        category: exploratory
        display_name: "Falsifiability Test Skill"
        description: "A minimal skill used only by the P3-030 drop-a-directory test."
        llm:
          provider: anthropic
          primary_model: claude-sonnet-4-20250514
          max_output_tokens: 8192
          system_prompt: SKILL.md
        workspace:
          session_path_template: "runs/{skill_id}/{subject_id}/{variant}"
        subjects:
          static: ["test-subject"]
        variants:
          static: ["default"]
        param_schema:
          type: object
          additionalProperties: false
          properties: {}
          required: []
        metric_schema:
          primary:
            field: score
            label: "Score"
            direction: higher_is_better
          chart_series: []
          iteration_table_columns: []
          goal: optimize
        decision_vocabulary:
          base: [continue]
          success_values: [done]
        phase_plan:
          - id: main
            min_iterations: 1
            max_iterations: 10
        phase_advancement:
          mode: declarative
        command_policy:
          allowed_scripts: []
        output_parser:
          format: json_marker
          iteration_marker: "ITERATION_RESULT:"
        promotion_target:
          primary:
            kind: file_path
            path_template: "/tmp/test.yaml"
          scopes:
            - id: development
        prompt:
          setup_command: "echo setup"
          experiment_command: "echo experiment"
    """)
    (skill_dir / "SKILL.yaml").write_text(manifest)
    (skill_dir / "SKILL.md").write_text("# Test Skill\n")

    registry = SkillRegistry(root=tmp_path)
    assert skill_id in registry.available()
    manifest_obj = registry.get(skill_id)
    assert manifest_obj.id == skill_id
    assert manifest_obj.display_name == "Falsifiability Test Skill"


# ------------------------------------------------------------------
# Domain-coupling grep guard (§1.7, Phase 3 target)
# ------------------------------------------------------------------


def test_orchestrator_domain_coupling_grep_guard():
    """§1.7 / §7.14: ``orchestrator.py`` must have zero hits for the Phase-3
    deny-list patterns (``config.model_type``, ``config.instrument``,
    ``config.timeframe``). The orchestrator must be domain-agnostic."""
    import re

    orchestrator_path = (
        Path(__file__).resolve().parents[1]
        / "src" / "core" / "orchestrator.py"
    )
    if not orchestrator_path.is_file():
        pytest.skip("orchestrator.py not found at expected path")
    source = orchestrator_path.read_text(encoding="utf-8")
    violations = []
    for pattern in _ORCHESTRATOR_DENY_PATTERNS:
        matches = re.findall(pattern, source)
        if matches:
            violations.append(f"{pattern}: {len(matches)} hits")
    assert not violations, (
        "orchestrator.py has domain-coupling grep violations (Phase 3 target): "
        + "; ".join(violations)
    )


# ------------------------------------------------------------------
# GEN-009: ML and non-ML sessions have identical row shape
# ------------------------------------------------------------------


def test_gen009_dual_shape_uniformity_across_model_types():
    """GEN-009 / §8.2: an ML session and a (future) non-ML session are
    indistinguishable in the response shape except by ``skill_id``.

    Today only ML skills exist, but the dual-shape helper must produce the
    same set of canonical+legacy fields for every ``model_type``. We verify
    this by calling the helper with each known model type and asserting the
    field sets are identical."""
    from src.api.research import _dual_shape_session

    base_session = {
        "id": "res_test",
        "status": "running",
        "tag": "test",
        "quick_mode": False,
        "max_iterations": 30,
        "max_budget_usd": 10.0,
        "workspace_path": "/tmp",
        "best_metric": None,
        "best_iteration": None,
        "total_api_cost_usd": 0.0,
        "started_at": "2026-01-01T00:00:00Z",
        "completed_at": None,
        "error_message": None,
        "resumed_from": None,
        "skill_name": "",
    }
    field_sets = []
    for mt in ("direction", "volatility", "rl"):
        session = {**base_session, "model_type": mt, "instrument": "TEST", "timeframe": "15m"}
        shaped = _dual_shape_session(session)
        field_sets.append(frozenset(shaped.keys()))
    # All model types produce the same field set.
    assert field_sets[0] == field_sets[1] == field_sets[2], (
        "dual-shape session fields differ across model types — GEN-009 violation"
    )
    # Canonical + legacy fields are all present.
    expected_fields = {"skill_id", "subject_id", "variant", "model_type", "instrument", "timeframe"}
    assert expected_fields.issubset(field_sets[0]), (
        f"dual-shape fields missing: {expected_fields - field_sets[0]}"
    )


# ------------------------------------------------------------------
# GEN-010: Dual-shape iteration responses (P3-015/016)
# ------------------------------------------------------------------


def test_gen010_dual_shape_iteration_has_canonical_fields():
    """GEN-010 / P3-015/016: iteration responses carry canonical skill fields
    (``skill_id``, ``skill_phase``, ``evidence_keys``) alongside legacy
    (``model_type``, ``search_phase``). Both shapes always populated."""
    from src.api.results import _enrich_iteration

    base_row = {
        "research_id": "res_test",
        "iteration": 1,
        "id": 1,
        "primary_metric": 0.75,
        "metric_name": "walkforward_auc",
        "all_gates_passed": True,
        "decision": "keep",
        "config_snapshot": "foo: bar",
        "created_at": "2026-01-01T00:00:00Z",
        "metrics_json": '{"walkforward_auc": 0.75, "phase_evidence": {"hpo_screening": true}}',
        "search_phase": "hpo_screening",
    }
    for mt in ("direction", "volatility", "rl"):
        enriched = _enrich_iteration(dict(base_row), mt)
        # Canonical fields present.
        assert "skill_id" in enriched, f"{mt}: skill_id missing"
        assert "skill_phase" in enriched, f"{mt}: skill_phase missing"
        assert "evidence_keys" in enriched, f"{mt}: evidence_keys missing"
        # skill_id derived from model_type via the alias registry.
        assert enriched["skill_id"] == f"ml-{mt}", (
            f"{mt}: skill_id={enriched['skill_id']!r}, expected ml-{mt}"
        )
        # skill_phase mirrors search_phase.
        assert enriched["skill_phase"] == "hpo_screening"
        # evidence_keys derived from phase_evidence dict keys.
        assert enriched["evidence_keys"] == ["hpo_screening"]
        # Legacy search_phase still present (additive, not replaced).
        assert enriched["search_phase"] == "hpo_screening"


# ------------------------------------------------------------------
# P3-017: Promotion preview target_kind injection
# ------------------------------------------------------------------


def test_p3_017_inject_target_kind_defaults_to_file_path():
    """P3-017: ``_inject_target_kind`` defaults to ``file_path`` when the
    registry is not wired (legacy sessions, tests without a registry)."""
    from src.api.promotion import _inject_target_kind

    result = {"research_id": "res_test", "model_type": "direction", "target_path": "/tmp/test.yaml"}
    enriched = _inject_target_kind(result)
    assert enriched["target_kind"] == "file_path"
    # Existing fields preserved.
    assert enriched["model_type"] == "direction"


def test_p3_017_inject_target_kind_does_not_overwrite():
    """P3-017: ``_inject_target_kind`` is additive — it never overwrites an
    existing ``target_kind``."""
    from src.api.promotion import _inject_target_kind

    result = {"target_kind": "registry_api", "model_type": "direction"}
    enriched = _inject_target_kind(result)
    assert enriched["target_kind"] == "registry_api"


def test_p3_017_inject_target_kind_from_registry():
    """P3-017: when a skill registry is wired, ``target_kind`` is derived from
    the skill manifest's ``promotion_target.primary.kind``."""
    from src.api.promotion import _inject_target_kind, _registry
    from src.core.skill_registry import SkillRegistry

    # Use the default registry which has the ML skills loaded.
    if _registry is None:
        # In tests, the registry is not wired by main.py; use the default.
        from src.api import promotion as promo_module
        promo_module._registry = SkillRegistry()
        promo_module._registry.discover()

    result = {"model_type": "direction", "target_path": "/tmp/test.yaml"}
    enriched = _inject_target_kind(result)
    # ML skills have file_path promotion targets.
    assert enriched["target_kind"] == "file_path"
