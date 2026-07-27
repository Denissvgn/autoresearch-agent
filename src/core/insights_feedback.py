"""Insights feedback loop (ARC-011 P5-027 / P5-030).

Appends a completed session's structured insights to the skill's
``knowledge/prior_findings/`` corpus as an append-only markdown file. The
``auto_absorb_insights`` manifest flag (P5-028) controls whether the next
session auto-feeds these findings into its system prompt (default off —
insights land on disk regardless, but require operator review before they
shape agent behavior).

Design decisions (P1-007 house style):

* **Append-only.** The file is named with the ``research_id`` for uniqueness;
  re-running with the same session id overwrites the same file (idempotent on
  retry) but never clobbers a different session's findings.
* **No orchestrator import.** This module is a pure helper; the orchestrator
  calls it at session completion with the already-assembled insight summary.
  Keeps the feedback loop testable in isolation.
* **Safe filename derivation.** The ``research_id`` is sanitized to a filename-
  safe form; the subject/variant provide human-readable context.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def _safe_filename_component(value: str) -> str:
    """Reduce a free-form string to a filename-safe component."""
    return re.sub(r"[^A-Za-z0-9._-]", "_", value) or "unknown"


def prior_findings_path(
    skill_dir: Path,
    *,
    subject_id: str,
    variant: str,
    research_id: str,
) -> Path:
    """Derive the append-only prior-findings path for one session.

    ``skill_dir`` is the skill package root (``skills/<id>/``). The file lands
    under ``knowledge/prior_findings/<subject>_<variant>_<research_id>.md``.
    """
    safe_subject = _safe_filename_component(subject_id)
    safe_variant = _safe_filename_component(variant)
    safe_research = _safe_filename_component(research_id)
    return (
        Path(skill_dir)
        / "knowledge"
        / "prior_findings"
        / f"{safe_subject}_{safe_variant}_{safe_research}.md"
    )


def render_findings_markdown(
    *,
    skill_id: str,
    subject_id: str,
    variant: str,
    research_id: str,
    insight_summary: str,
    primary_metric: Optional[float] = None,
    metric_name: Optional[str] = None,
    iterations: int = 0,
    completed_at: Optional[str] = None,
    extra: Optional[dict[str, Any]] = None,
) -> str:
    """Render the markdown body for a prior-findings file (P5-027).

    The shape is stable and append-friendly: a YAML front-matter block carrying
    the structured fields, then the free-text insight summary. Downstream
    consumers (the system-prompt assembly when ``auto_absorb_insights`` is on)
    parse the front-matter to decide relevance.
    """
    ts = completed_at or datetime.now(timezone.utc).isoformat()
    lines = [
        "---",
        f"skill_id: {skill_id}",
        f"subject_id: {subject_id}",
        f"variant: {variant}",
        f"research_id: {research_id}",
        f"completed_at: {ts}",
        f"iterations: {iterations}",
    ]
    if primary_metric is not None:
        lines.append(f"primary_metric: {primary_metric}")
    if metric_name:
        lines.append(f"metric_name: {metric_name}")
    if extra:
        for key, value in sorted(extra.items()):
            lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")
    lines.append(f"# Prior findings — {research_id}")
    lines.append("")
    lines.append(f"_{skill_id}_ on **{subject_id} {variant}** ({iterations} iterations).")
    lines.append("")
    lines.append(insight_summary.strip())
    lines.append("")
    return "\n".join(lines)


def append_findings(
    skill_dir: Path,
    *,
    skill_id: str,
    subject_id: str,
    variant: str,
    research_id: str,
    insight_summary: str,
    primary_metric: Optional[float] = None,
    metric_name: Optional[str] = None,
    iterations: int = 0,
    completed_at: Optional[str] = None,
    extra: Optional[dict[str, Any]] = None,
) -> Path:
    """Write the session's prior-findings file (P5-027).

    Idempotent on ``research_id``: re-running with the same id overwrites the
    same file (safe for retry). Returns the written path. Creates
    ``knowledge/prior_findings/`` if absent.
    """
    path = prior_findings_path(
        skill_dir, subject_id=subject_id, variant=variant, research_id=research_id,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    body = render_findings_markdown(
        skill_id=skill_id,
        subject_id=subject_id,
        variant=variant,
        research_id=research_id,
        insight_summary=insight_summary,
        primary_metric=primary_metric,
        metric_name=metric_name,
        iterations=iterations,
        completed_at=completed_at,
        extra=extra,
    )
    path.write_text(body, encoding="utf-8")
    return path


__all__ = [
    "append_findings",
    "prior_findings_path",
    "render_findings_markdown",
]
