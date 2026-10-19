"""Instruction assembly: common research directives vs harness specifics.

Instructions are product assets with two owners. Common research
instructions are domain-agnostic and harness-free; tool and harness
instructions describe one harness's execution surface and are supplied by
the harness adapter. Workspace instruction files (the built-in harness's
``CLAUDE.md``, another harness's ``AGENTS.md``) are rendered only through
adapters — core behavior never depends on a particular filename or on any
provider's tool-block shape.
"""
from __future__ import annotations

from typing import Iterable, Sequence

COMMON_RESEARCH_INSTRUCTIONS = """\
# Research conduct

- Every attempt records its configuration, its metrics, and its outcome
  honestly; a declined candidate is recorded as declined, never as failure.
- Metric direction comes from the objective policy: do not assume higher is
  better.
- Gate results are evidence: pass or fail them against the declared checks,
  and never edit the evaluator that judges you.
- Budgets bound the run. When a budget is reached, stop and report; never
  extend a budget to fit more attempts.
"""

_TOOL_USAGE_TEMPLATE = """\
# Tool usage ({surface_name})

{tool_lines}
- All tool calls run inside the declared sandbox and access policy; a
  refused command is a policy boundary, not an error to route around.
"""


def harness_tool_instructions(
    tools: Sequence[tuple[str, str]],
    *,
    surface_name: str,
) -> str:
    """Render one harness's tool instructions as provider-neutral prose.

    ``tools`` is a sequence of (name, description) pairs. The output is
    plain text on purpose: no provider's tool-block shape is assumed.
    """
    lines = "\n".join(f"- `{name}` — {description}" for name, description in tools)
    return _TOOL_USAGE_TEMPLATE.format(surface_name=surface_name, tool_lines=lines)


def assemble_instructions(
    *,
    common: str = COMMON_RESEARCH_INSTRUCTIONS,
    harness: str = "",
    skill_primer: str = "",
) -> str:
    """Assemble the run's instructions deterministically.

    The order is fixed (common, harness, skill primer) so rendered prompts
    are stable product assets.
    """
    sections = [section for section in (common, harness, skill_primer) if section]
    return "\n\n".join(sections)


def render_workspace_instructions(
    *,
    filename: str,
    common: str = COMMON_RESEARCH_INSTRUCTIONS,
    harness: str = "",
) -> tuple[str, str]:
    """Render a workspace instruction file for the harness's chosen name.

    Returns ``(filename, content)`` — the adapter owns the filename, so
    core behavior cannot depend on it.
    """
    return filename, assemble_instructions(common=common, harness=harness)


__all__ = [
    "COMMON_RESEARCH_INSTRUCTIONS",
    "assemble_instructions",
    "harness_tool_instructions",
    "render_workspace_instructions",
]
