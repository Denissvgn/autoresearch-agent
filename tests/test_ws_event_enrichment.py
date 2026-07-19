"""P3-018 — WebSocket event payload enrichment tests (ARC-011 C-stream).

Validates that ``_enrich_event`` adds canonical ``skill_id``, ``skill_phase``,
``evidence_keys``, and ``metrics`` to WebSocket payloads additively (§10 #5:
event names unchanged; payloads only gain fields).
"""

from __future__ import annotations

import os

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")
os.environ.setdefault("USE_VAULT", "false")

from src.ws.events import _enrich_event

# --- skill_id derived from model_type ---

def test_enrich_adds_skill_id_from_model_type():
    event = {"type": "iteration_result", "research_id": "res_001", "model_type": "direction"}
    enriched = _enrich_event(event)
    assert enriched["skill_id"] == "ml-direction"
    # Legacy field preserved.
    assert enriched["model_type"] == "direction"


def test_enrich_preserves_existing_skill_id():
    event = {"type": "iteration_result", "model_type": "direction", "skill_id": "custom-override"}
    enriched = _enrich_event(event)
    assert enriched["skill_id"] == "custom-override"  # not overwritten


# --- skill_phase derived from search_phase ---

def test_enrich_adds_skill_phase_from_search_phase():
    event = {"type": "iteration_result", "search_phase": "walkforward"}
    enriched = _enrich_event(event)
    assert enriched["skill_phase"] == "walkforward"
    # Legacy field preserved.
    assert enriched["search_phase"] == "walkforward"


def test_enrich_skill_phase_absent_when_no_search_phase():
    event = {"type": "iteration_result"}
    enriched = _enrich_event(event)
    assert "skill_phase" not in enriched


# --- evidence_keys derived from phase_evidence ---

def test_enrich_adds_evidence_keys_from_phase_evidence():
    event = {
        "type": "iteration_result",
        "phase_evidence": {"fold_0": {"auc": 0.7}, "fold_1": {"auc": 0.8}},
    }
    enriched = _enrich_event(event)
    assert enriched["evidence_keys"] == ["fold_0", "fold_1"]


def test_enrich_evidence_keys_absent_when_no_phase_evidence():
    event = {"type": "iteration_result"}
    enriched = _enrich_event(event)
    assert "evidence_keys" not in enriched


# --- metrics summary ---

def test_enrich_adds_metrics_summary():
    event = {
        "type": "iteration_result",
        "primary_metric": 0.82,
        "metric_name": "walkforward_mean_auc",
        "all_gates_passed": True,
    }
    enriched = _enrich_event(event)
    assert enriched["metrics"]["primary_metric"] == 0.82
    assert enriched["metrics"]["metric_name"] == "walkforward_mean_auc"
    assert enriched["metrics"]["all_gates_passed"] is True


# --- Additive only: existing fields untouched ---

def test_enrich_does_not_remove_existing_fields():
    event = {
        "type": "iteration_result",
        "research_id": "res_001",
        "model_type": "volatility",
        "search_phase": "hyperopt",
        "primary_metric": 0.5,
        "custom_field": "keep-me",
    }
    enriched = _enrich_event(event)
    assert enriched["research_id"] == "res_001"
    assert enriched["custom_field"] == "keep-me"
    assert enriched["model_type"] == "volatility"
    assert enriched["skill_id"] == "ml-volatility"
    assert enriched["skill_phase"] == "hyperopt"


def test_enrich_non_dict_returns_unchanged():
    assert _enrich_event("not-a-dict") == "not-a-dict"
    assert _enrich_event(None) is None
