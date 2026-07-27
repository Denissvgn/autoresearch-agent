"""Skill lifecycle state machine (ARC-011 P5-010).

Models the ``draft → reviewed → stable → deprecated`` lifecycle a skill package
moves through, with gating that keeps drafts out of production sessions. The
shape mirrors ``SessionStateMachine`` (ARC-011 P0-002): states + events as
enums, a transition table, per-skill locking, and the "server owns status /
audit only — domain side-effects stay with the caller" house-style separation
(documented in ``state_machine.py`` §13).

Lifecycle semantics (X-004 D1 / ARC-011 §8.7):

* ``draft`` — newly installed or generator-output (P5-023). NOT selectable for
  production sessions; selectable for dev sessions only with operator opt-in.
* ``reviewed`` — an operator has signed off on review; still not production.
* ``stable`` — production-eligible. The default for operator-installed skills.
* ``deprecated`` — retired; not selectable for new sessions.

Transitions are monotone-forward except the operator ``un_retire`` path
(``deprecated → reviewed``). A skill can never move backward past ``draft``
(drafts are deleted, not demoted).

Design decisions (P1-007 house style):

* **Async + per-skill lock.** Promotion is a file-move + status update that
  must be atomic per skill; the lock serializes concurrent promotes of the
  same id. Mirrors ``SessionStateMachine``'s per-session ``asyncio.Lock``.
* **No DB handle here.** The machine owns only state transitions + returns a
  ``LifecycleTransitionResult`` describing the side-effects the caller should
  perform (audit, broadcast, file move). Keeps the machine free of the store.
* **Production gating is a predicate, not a transition.** ``selectable_for(production=…)``
  answers "can this state be used in this session scope?" — it does not mutate.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class SkillLifecycleState(str, Enum):
    """The four lifecycle states a skill package moves through (ARC-011 §8.7)."""

    DRAFT = "draft"
    REVIEWED = "reviewed"
    STABLE = "stable"
    DEPRECATED = "deprecated"

    @classmethod
    def default_for_installed(cls) -> "SkillLifecycleState":
        """Operator-installed skills (dropped under ``skills/<id>/``) start here."""
        return cls.STABLE

    @classmethod
    def default_for_draft(cls) -> "SkillLifecycleState":
        """Generator output (under ``skills/_drafts/<id>/``) starts here."""
        return cls.DRAFT


class SkillLifecycleEvent(str, Enum):
    """Operator-initiated lifecycle events."""

    SUBMIT_FOR_REVIEW = "submit_for_review"   # draft → reviewed
    APPROVE = "approve"                        # reviewed → stable
    DEPRECATE = "deprecate"                    # stable → deprecated
    UN_RETIRE = "un_retire"                    # deprecated → reviewed


#: Legal (from, event) → to transitions. Monotone-forward except un-retire.
_TRANSITIONS: dict[tuple[SkillLifecycleState, SkillLifecycleEvent], SkillLifecycleState] = {
    (SkillLifecycleState.DRAFT, SkillLifecycleEvent.SUBMIT_FOR_REVIEW):
        SkillLifecycleState.REVIEWED,
    (SkillLifecycleState.REVIEWED, SkillLifecycleEvent.APPROVE):
        SkillLifecycleState.STABLE,
    (SkillLifecycleState.STABLE, SkillLifecycleEvent.DEPRECATE):
        SkillLifecycleState.DEPRECATED,
    (SkillLifecycleState.DEPRECATED, SkillLifecycleEvent.UN_RETIRE): SkillLifecycleState.REVIEWED,
}

#: Terminal states (no outbound transitions except un-retire from deprecated).
_TERMINAL: frozenset[SkillLifecycleState] = frozenset()


class IllegalLifecycleTransitionError(ValueError):
    """Raised when a (state, event) pair is not a legal transition."""

    def __init__(
        self,
        skill_id: str,
        from_state: SkillLifecycleState,
        event: SkillLifecycleEvent,
    ) -> None:
        super().__init__(
            f"skill {skill_id!r}: illegal lifecycle transition "
            f"{from_state.value} --{event.value}--> (not in transition table)"
        )
        self.skill_id = skill_id
        self.from_state = from_state
        self.event = event


@dataclass(frozen=True)
class LifecycleTransitionResult:
    """Outcome of a lifecycle transition (the caller performs the side-effects)."""

    skill_id: str
    from_state: SkillLifecycleState
    to_state: SkillLifecycleState
    event: SkillLifecycleEvent
    changed: bool

    @property
    def audit_action(self) -> str:
        """The audit_events ``action`` vocabulary for this transition."""
        return f"skill.lifecycle.{self.event.value}"


def is_legal_transition(
    from_state: SkillLifecycleState, event: SkillLifecycleEvent
) -> bool:
    """True if ``(from_state, event)`` is a legal transition."""
    return (from_state, event) in _TRANSITIONS


def target_state(
    from_state: SkillLifecycleState, event: SkillLifecycleEvent
) -> Optional[SkillLifecycleState]:
    """The state ``event`` moves ``from_state`` to, or None if illegal."""
    return _TRANSITIONS.get((from_state, event))


def selectable_for(
    state: SkillLifecycleState, *, production: bool
) -> bool:
    """P5-010 gating predicate: can a skill in ``state`` be selected for a
    session of the given scope?

    * Production sessions require ``stable``.
    * Dev sessions allow ``reviewed`` + ``stable``.
    * ``draft`` is never auto-selected (operator must explicitly opt in via the
      dev path); ``deprecated`` is never selectable.
    """
    if production:
        return state is SkillLifecycleState.STABLE
    return state in (SkillLifecycleState.REVIEWED, SkillLifecycleState.STABLE)


class SkillLifecycleMachine:
    """Per-skill lifecycle state machine (P5-010).

    Holds the current state for a set of skill ids and serializes transitions
    under a per-skill ``asyncio.Lock``. The machine owns ONLY state + returns a
    ``LifecycleTransitionResult``; the caller performs the file-move / audit /
    broadcast side-effects (house-style separation — see ``state_machine.py``).
    """

    def __init__(self) -> None:
        self._states: dict[str, SkillLifecycleState] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def register(
        self, skill_id: str, state: Optional[SkillLifecycleState] = None
    ) -> None:
        """Record the initial state for ``skill_id`` (idempotent; first write wins
        unless ``state`` is explicitly provided)."""
        if state is not None:
            self._states[skill_id] = state
        else:
            self._states.setdefault(skill_id, SkillLifecycleState.default_for_installed())
        self._locks.setdefault(skill_id, asyncio.Lock())

    def get_state(self, skill_id: str) -> SkillLifecycleState:
        """Current state; defaults to ``stable`` if never registered."""
        return self._states.get(skill_id, SkillLifecycleState.default_for_installed())

    def _lock_for(self, skill_id: str) -> asyncio.Lock:
        self._locks.setdefault(skill_id, asyncio.Lock())
        return self._locks[skill_id]

    async def transition(
        self, skill_id: str, event: SkillLifecycleEvent
    ) -> LifecycleTransitionResult:
        """Apply ``event`` to ``skill_id`` under its per-skill lock.

        Raises ``IllegalLifecycleTransitionError`` if the (state, event) pair is
        not legal. Returns a ``LifecycleTransitionResult`` the caller acts on.
        """
        lock = self._lock_for(skill_id)
        async with lock:
            current = self.get_state(skill_id)
            target = target_state(current, event)
            if target is None:
                raise IllegalLifecycleTransitionError(skill_id, current, event)
            self._states[skill_id] = target
            return LifecycleTransitionResult(
                skill_id=skill_id,
                from_state=current,
                to_state=target,
                event=event,
                changed=(target is not current),
            )


__all__ = [
    "IllegalLifecycleTransitionError",
    "LifecycleTransitionResult",
    "SkillLifecycleEvent",
    "SkillLifecycleMachine",
    "SkillLifecycleState",
    "is_legal_transition",
    "selectable_for",
    "target_state",
]
