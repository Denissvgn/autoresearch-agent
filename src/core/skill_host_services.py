"""Skill host services: the explicit context a skill runtime may use.

A skill runtime builds prompts and reads resume/contract material through
this protocol — never through orchestrator-private helpers. The value
contracts are stable strings and paths over the run's configuration value
(any object exposing the run identity fields the host reads, such as
``subject_id`` and ``variant``), so a different agent harness can provide
the same services without inheriting the built-in loop.
"""
from __future__ import annotations

from typing import Any, Protocol


class SkillHostServices(Protocol):
    """The host's explicit, stable surface for skill runtimes."""

    def load_claude_md(self) -> str:
        """The workspace's agent instructions (empty when absent)."""
        ...

    def load_research_resume(self, config: Any) -> str:
        """The cross-session resume material for this run (may be empty)."""
        ...

    def build_phase_contract_block(self, config: Any) -> str:
        """The rendered phase contract for this run (may be empty)."""
        ...

    def research_resume_path(self, config: Any) -> str:
        """Where this run's cross-session resume file lives."""
        ...


__all__ = ["SkillHostServices"]
