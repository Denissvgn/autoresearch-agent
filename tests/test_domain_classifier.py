"""Domain classifier tests (ARC-011 P5-016..020).

Covers the lexical-first classifier:

* **P5-016** — ranks installed skills by similarity to a ``goal``; embeddings
  cached + invalidated on reload; cold-start degrades to "list all".
* **P5-018** — ``ClassificationResult.to_audit_dict()`` shape for the
  ``skill.classify`` audit row.
* **P5-019** — threshold + confidence logic (high/medium/low, auto-select).

The classifier is built on a temp ``SkillRegistry`` stubbed with hand-authored
skill manifests so the lexical similarity is deterministic and observable.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from src.core.domain_classifier import (
    DEFAULT_AUTO_SELECT_THRESHOLD,
    ClassificationResult,
    DomainClassifier,
    LexicalEmbeddingBackend,
    SkillMatch,
)
from src.core.skill_manifest import SCHEMA_VERSION
from src.core.skill_registry import SKILL_MANIFEST_FILENAME, SkillRegistry


def _manifest_dict(
    *,
    skill_id: str,
    display_name: str,
    description: str,
    category: str = "optimization",
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "id": skill_id,
        "version": "1.0.0",
        "category": category,
        "display_name": display_name,
        "description": description,
        "llm": {"provider": "anthropic", "primary_model": "m"},
        "workspace": {"session_path_template": "runs/{skill_id}"},
        "variants": {"static": ["v1"]},
        "param_schema": {"type": "object"},
        "metric_schema": {
            "primary": {"field": "m", "label": "M", "direction": "higher_is_better"}
        },
        "decision_vocabulary": {"base": ["keep"]},
        "phase_plan": [{"id": "p1", "min_iterations": 1, "max_iterations": 2}],
        "command_policy": {},
        "output_parser": {"format": "delimited_kv"},
        "preflight": [],
        "promotion_target": {
            "primary": {"kind": "file_path", "path_template": "/tmp/x"}
        },
    }


class _StubSettings:
    """Minimal settings object (the manifests here use no {settings.*} refs)."""


@pytest.fixture()
def registry_with_skills(tmp_path: Path) -> SkillRegistry:
    """A registry with three distinct-domain skills for classification."""
    skills = [
        _manifest_dict(
            skill_id="ml-direction",
            display_name="ML Direction Model Tuning",
            description="Tune the direction up/down classification model AUC calibration",
        ),
        _manifest_dict(
            skill_id="ml-volatility",
            display_name="ML Volatility Model Tuning",
            description="Tune the volatility breakout model ATR threshold AUC",
        ),
        _manifest_dict(
            skill_id="prompt-engineering",
            display_name="Prompt Engineering",
            description="Iterate on LLM prompt templates eval set quality",
            category="generative",
        ),
    ]
    for data in skills:
        skill_dir = tmp_path / data["id"]
        skill_dir.mkdir()
        (skill_dir / SKILL_MANIFEST_FILENAME).write_text(yaml.safe_dump(data))
    return SkillRegistry(root=tmp_path, settings_obj=_StubSettings())


# ---------------------------------------------------------------------------
# P5-016 — ranking
# ---------------------------------------------------------------------------


class TestClassifyRanking:
    def test_ranks_by_similarity(self, registry_with_skills: SkillRegistry):
        clf = DomainClassifier(registry=registry_with_skills)
        result = clf.classify("tune the direction model AUC")
        assert len(result.matched_skills) == 3
        # The direction skill should rank highest for a direction-goal.
        assert result.matched_skills[0].skill_id == "ml-direction"

    def test_different_goal_ranks_differently(self, registry_with_skills: SkillRegistry):
        clf = DomainClassifier(registry=registry_with_skills)
        result = clf.classify("improve prompt template quality")
        # The prompt-engineering skill should rank highest for a prompt-goal.
        assert result.matched_skills[0].skill_id == "prompt-engineering"

    def test_scores_in_unit_interval(self, registry_with_skills: SkillRegistry):
        clf = DomainClassifier(registry=registry_with_skills)
        result = clf.classify("anything")
        for m in result.matched_skills:
            assert 0.0 <= m.score <= 1.0 + 1e-9


# ---------------------------------------------------------------------------
# P5-019 — threshold + confidence
# ---------------------------------------------------------------------------


class TestThresholdAndConfidence:
    def test_clear_top_match_auto_selects(self, registry_with_skills: SkillRegistry):
        clf = DomainClassifier(registry=registry_with_skills, threshold=0.1)
        result = clf.classify("tune direction model AUC calibration")
        assert result.auto_selected == "ml-direction"
        assert result.matched_skills[0].confidence in ("high", "medium")

    def test_below_threshold_no_autoselect(self, registry_with_skills: SkillRegistry):
        clf = DomainClassifier(registry=registry_with_skills, threshold=0.99)
        result = clf.classify("tune direction model")
        assert result.auto_selected is None
        assert result.confidence == "low"

    def test_cold_start_low_confidence(self, tmp_path: Path):
        """Fewer than _MIN_SKILLS_FOR_AUTOSELECT installed ⇒ low confidence."""
        skill_dir = tmp_path / "only-skill"
        skill_dir.mkdir()
        (skill_dir / SKILL_MANIFEST_FILENAME).write_text(
            yaml.safe_dump(_manifest_dict(skill_id="only-skill", display_name="X", description="d"))
        )
        reg = SkillRegistry(root=tmp_path, settings_obj=_StubSettings())
        clf = DomainClassifier(registry=reg)
        result = clf.classify("anything")
        assert result.auto_selected is None
        assert result.confidence == "low"


# ---------------------------------------------------------------------------
# P5-016 AC #3 — embedding cache
# ---------------------------------------------------------------------------


class TestEmbeddingCache:
    def test_cache_persists_to_disk(self, registry_with_skills: SkillRegistry, tmp_path: Path):
        cache = tmp_path / "embeddings.json"
        clf = DomainClassifier(
            registry=registry_with_skills, cache_path=cache
        )
        clf.classify("goal")
        assert cache.is_file()
        data = json.loads(cache.read_text())
        assert "ml-direction" in data
        assert "content_hash" in data["ml-direction"]
        assert "vector" in data["ml-direction"]

    def test_invalidate_cache_drops_entry(self, registry_with_skills: SkillRegistry):
        clf = DomainClassifier(registry=registry_with_skills)
        clf.classify("goal")
        assert "ml-direction" in clf._cache
        clf.invalidate_cache("ml-direction")
        assert "ml-direction" not in clf._cache

    def test_invalidate_all(self, registry_with_skills: SkillRegistry):
        clf = DomainClassifier(registry=registry_with_skills)
        clf.classify("goal")
        assert clf._cache
        clf.invalidate_cache()
        assert clf._cache == {}


# ---------------------------------------------------------------------------
# P5-018 — audit shape
# ---------------------------------------------------------------------------


class TestAuditShape:
    def test_to_audit_dict_carries_required_fields(self, registry_with_skills: SkillRegistry):
        clf = DomainClassifier(registry=registry_with_skills)
        result = clf.classify("tune direction model")
        audit = result.to_audit_dict()
        assert "goal_hash" in audit
        assert "matched_skills" in audit
        assert "threshold" in audit
        assert "auto_selected" in audit
        # goal_hash is a stable sha256 prefix (not the raw goal — privacy).
        assert len(audit["goal_hash"]) == 16
        assert all(
            "id" in m and "score" in m and "confidence" in m
            for m in audit["matched_skills"]
        )


# ---------------------------------------------------------------------------
# Backend Protocol
# ---------------------------------------------------------------------------


class TestEmbeddingBackend:
    def test_lexical_backend_is_deterministic(self):
        backend = LexicalEmbeddingBackend()
        v1 = list(backend.embed("tune direction model"))
        v2 = list(backend.embed("tune direction model"))
        assert v1 == v2

    def test_lexical_backend_content_hash_stable(self):
        backend = LexicalEmbeddingBackend()
        assert backend.content_hash("abc") == backend.content_hash("abc")
        assert backend.content_hash("abc") != backend.content_hash("abd")
