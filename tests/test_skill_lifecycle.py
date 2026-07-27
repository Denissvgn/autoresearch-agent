"""Skill lifecycle + promotion tests (ARC-011 P5-010..013).

Covers:

* **P5-010** — the four lifecycle states, the transition table (legal + illegal),
  production gating (drafts excluded), and the per-skill async lock serializing
  concurrent transitions.
* **P5-011** — ``SkillRegistryPromotionTarget`` moves a draft into the live
  skills dir atomically, rejects missing-draft / existing-stable, and rolls
  back on failure.
* **P5-012** wiring is covered indirectly via the target's contract; the HTTP
  endpoints land in a follow-up that wires the FastAPI router (the
  ``src/api/skills.py`` DI pattern is the template).

House style (P1-007): pydantic v2 models, async transitions, fail-closed
precondition checks, no DB handle in the state machine.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from src.core.promotion_target import (
    SkillPromotionError,
    SkillRegistryPromotionTarget,
)
from src.core.skill_lifecycle import (
    IllegalLifecycleTransitionError,
    LifecycleTransitionResult,
    SkillLifecycleEvent,
    SkillLifecycleMachine,
    SkillLifecycleState,
    is_legal_transition,
    selectable_for,
    target_state,
)

# ===========================================================================
# P5-010 — lifecycle state machine
# ===========================================================================


class TestLifecycleStates:
    def test_four_states_defined(self):
        assert {s.value for s in SkillLifecycleState} == {
            "draft", "reviewed", "stable", "deprecated",
        }

    def test_default_for_installed_is_stable(self):
        assert SkillLifecycleState.default_for_installed() is SkillLifecycleState.STABLE

    def test_default_for_draft_is_draft(self):
        assert SkillLifecycleState.default_for_draft() is SkillLifecycleState.DRAFT


class TestTransitionTable:
    def test_legal_forward_transitions(self):
        assert target_state(
            SkillLifecycleState.DRAFT, SkillLifecycleEvent.SUBMIT_FOR_REVIEW
        ) is SkillLifecycleState.REVIEWED
        assert target_state(
            SkillLifecycleState.REVIEWED, SkillLifecycleEvent.APPROVE
        ) is SkillLifecycleState.STABLE
        assert target_state(
            SkillLifecycleState.STABLE, SkillLifecycleEvent.DEPRECATE
        ) is SkillLifecycleState.DEPRECATED

    def test_un_retire_path(self):
        assert target_state(
            SkillLifecycleState.DEPRECATED, SkillLifecycleEvent.UN_RETIRE
        ) is SkillLifecycleState.REVIEWED

    def test_illegal_transitions_return_none(self):
        # draft cannot be approved directly (must be reviewed first).
        assert target_state(
            SkillLifecycleState.DRAFT, SkillLifecycleEvent.APPROVE
        ) is None
        # stable cannot be submitted for review.
        assert target_state(
            SkillLifecycleState.STABLE, SkillLifecycleEvent.SUBMIT_FOR_REVIEW
        ) is None
        # deprecated cannot be approved.
        assert target_state(
            SkillLifecycleState.DEPRECATED, SkillLifecycleEvent.APPROVE
        ) is None

    def test_is_legal_transition_predicate(self):
        assert is_legal_transition(
            SkillLifecycleState.DRAFT, SkillLifecycleEvent.SUBMIT_FOR_REVIEW
        ) is True
        assert is_legal_transition(
            SkillLifecycleState.DRAFT, SkillLifecycleEvent.APPROVE
        ) is False


class TestProductionGating:
    """P5-010 AC: production sessions require stable; drafts never auto-select."""

    def test_stable_selectable_for_production(self):
        assert selectable_for(SkillLifecycleState.STABLE, production=True) is True

    def test_draft_not_selectable_for_production(self):
        assert selectable_for(SkillLifecycleState.DRAFT, production=True) is False

    def test_reviewed_not_selectable_for_production(self):
        assert selectable_for(SkillLifecycleState.REVIEWED, production=True) is False

    def test_deprecated_never_selectable(self):
        assert selectable_for(SkillLifecycleState.DEPRECATED, production=True) is False
        assert selectable_for(SkillLifecycleState.DEPRECATED, production=False) is False

    def test_dev_allows_reviewed_and_stable(self):
        assert selectable_for(SkillLifecycleState.REVIEWED, production=False) is True
        assert selectable_for(SkillLifecycleState.STABLE, production=False) is True

    def test_dev_excludes_draft(self):
        assert selectable_for(SkillLifecycleState.DRAFT, production=False) is False


class TestLifecycleMachine:
    @pytest.mark.asyncio
    async def test_full_happy_path(self):
        machine = SkillLifecycleMachine()
        machine.register("gen-skill", SkillLifecycleState.DRAFT)
        r1 = await machine.transition("gen-skill", SkillLifecycleEvent.SUBMIT_FOR_REVIEW)
        assert r1.to_state is SkillLifecycleState.REVIEWED
        r2 = await machine.transition("gen-skill", SkillLifecycleEvent.APPROVE)
        assert r2.to_state is SkillLifecycleState.STABLE
        r3 = await machine.transition("gen-skill", SkillLifecycleEvent.DEPRECATE)
        assert r3.to_state is SkillLifecycleState.DEPRECATED
        r4 = await machine.transition("gen-skill", SkillLifecycleEvent.UN_RETIRE)
        assert r4.to_state is SkillLifecycleState.REVIEWED

    @pytest.mark.asyncio
    async def test_illegal_transition_raises(self):
        machine = SkillLifecycleMachine()
        machine.register("s", SkillLifecycleState.DRAFT)
        with pytest.raises(IllegalLifecycleTransitionError) as exc:
            await machine.transition("s", SkillLifecycleEvent.APPROVE)
        assert "s" in str(exc.value)
        assert exc.value.from_state is SkillLifecycleState.DRAFT

    @pytest.mark.asyncio
    async def test_audit_action_vocabulary(self):
        machine = SkillLifecycleMachine()
        machine.register("s", SkillLifecycleState.DRAFT)
        result = await machine.transition("s", SkillLifecycleEvent.SUBMIT_FOR_REVIEW)
        assert result.audit_action == "skill.lifecycle.submit_for_review"

    @pytest.mark.asyncio
    async def test_unregistered_defaults_to_stable(self):
        machine = SkillLifecycleMachine()
        assert machine.get_state("unknown") is SkillLifecycleState.STABLE

    @pytest.mark.asyncio
    async def test_concurrent_transitions_serialized(self):
        """Two concurrent transitions on the same skill do not race — the lock
        serializes them, and the second sees the first's result."""
        machine = SkillLifecycleMachine()
        machine.register("s", SkillLifecycleState.DRAFT)

        async def submit():
            return await machine.transition("s", SkillLifecycleEvent.SUBMIT_FOR_REVIEW)

        # Run two submits concurrently; the first succeeds, the second is illegal
        # (REVIEWED + SUBMIT_FOR_REVIEW is not in the table).
        results = await asyncio.gather(
            submit(), submit(), return_exceptions=True
        )
        # Exactly one succeeded, exactly one raised IllegalLifecycleTransitionError.
        oks = [r for r in results if isinstance(r, LifecycleTransitionResult)]
        errs = [r for r in results if isinstance(r, IllegalLifecycleTransitionError)]
        assert len(oks) == 1
        assert len(errs) == 1
        assert machine.get_state("s") is SkillLifecycleState.REVIEWED


# ===========================================================================
# P5-011 — SkillRegistryPromotionTarget
# ===========================================================================


def _make_draft(skills_root: Path, skill_id: str) -> Path:
    """Create a minimal draft package under ``skills_root/_drafts/<id>/``."""
    draft = skills_root / "_drafts" / skill_id
    draft.mkdir(parents=True)
    (draft / "SKILL.yaml").write_text("id: test\n")
    (draft / "bootstrap.py").write_text("# noop\n")
    return draft


class TestSkillRegistryPromotionTarget:
    @pytest.mark.asyncio
    async def test_promote_moves_draft_to_stable(self, tmp_path: Path):
        skills_root = tmp_path / "skills"
        skills_root.mkdir()
        _make_draft(skills_root, "gen-skill")
        target = SkillRegistryPromotionTarget(skills_root=skills_root)

        assert target.draft_exists("gen-skill") is True
        result = await target.promote("gen-skill")

        assert result.skill_id == "gen-skill"
        assert target.stable_exists("gen-skill") is True
        assert target.draft_exists("gen-skill") is False
        assert (skills_root / "gen-skill" / "SKILL.yaml").is_file()

    @pytest.mark.asyncio
    async def test_promote_missing_draft_raises(self, tmp_path: Path):
        target = SkillRegistryPromotionTarget(skills_root=tmp_path / "skills")
        with pytest.raises(SkillPromotionError) as exc:
            await target.promote("ghost")
        assert "draft not found" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_promote_existing_stable_raises(self, tmp_path: Path):
        skills_root = tmp_path / "skills"
        skills_root.mkdir()
        _make_draft(skills_root, "conflict")
        # Pre-create the stable path.
        stable = skills_root / "conflict"
        stable.mkdir()
        (stable / "SKILL.yaml").write_text("id: existing\n")
        target = SkillRegistryPromotionTarget(skills_root=skills_root)
        with pytest.raises(SkillPromotionError) as exc:
            await target.promote("conflict")
        assert "already exists" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_rollback_moves_stable_back_to_drafts(self, tmp_path: Path):
        skills_root = tmp_path / "skills"
        skills_root.mkdir()
        _make_draft(skills_root, "gen-skill")
        target = SkillRegistryPromotionTarget(skills_root=skills_root)
        await target.promote("gen-skill")
        assert target.stable_exists("gen-skill") is True

        await target.rollback("gen-skill")

        assert target.stable_exists("gen-skill") is False
        assert target.draft_exists("gen-skill") is True

    @pytest.mark.asyncio
    async def test_rollback_noop_if_stable_gone(self, tmp_path: Path):
        target = SkillRegistryPromotionTarget(skills_root=tmp_path / "skills")
        # Should not raise even though nothing exists.
        await target.rollback("ghost")

    def test_path_helpers(self, tmp_path: Path):
        target = SkillRegistryPromotionTarget(skills_root=tmp_path)
        assert target.draft_path("x") == tmp_path / "_drafts" / "x"
        assert target.stable_path("x") == tmp_path / "x"
