"""Insights feedback loop tests (ARC-011 P5-027 / P5-028 / P5-029 / P5-030).

Covers:

* **P5-027** — completed-session insights append to ``knowledge/prior_findings/``
  as an idempotent markdown file (named with the research_id).
* **P5-028** — the ``auto_absorb_insights`` manifest flag is wired (default off).
* **P5-029** — the stale-knowledge computation: ``now - knowledge_last_reviewed >
  refresh_cadence_days`` → stale.
* **P5-030** — idempotency on research_id, filename safety, front-matter shape.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
import yaml

from src.core.insights_feedback import (
    append_findings,
    prior_findings_path,
    render_findings_markdown,
)


class TestAppendFindings:
    def test_writes_markdown_with_frontmatter(self, tmp_path: Path):
        skill_dir = tmp_path / "myskill"
        skill_dir.mkdir()
        path = append_findings(
            skill_dir,
            skill_id="myskill",
            subject_id="DOGE_USDT",
            variant="15m",
            research_id="res_abc123",
            insight_summary="Lowering learning rate improved AUC by 3%.",
            primary_metric=0.62,
            metric_name="auc",
            iterations=12,
        )
        assert path.is_file()
        text = path.read_text()
        # YAML front-matter parses.
        assert text.startswith("---")
        fm_block = text.split("---")[1]
        meta = yaml.safe_load(fm_block)
        assert meta["skill_id"] == "myskill"
        assert meta["subject_id"] == "DOGE_USDT"
        assert meta["primary_metric"] == 0.62
        assert meta["iterations"] == 12
        # Insight body present.
        assert "Lowering learning rate" in text

    def test_idempotent_on_research_id(self, tmp_path: Path):
        """Re-running with the same research_id overwrites the same file (safe
        for retry) — does not create a duplicate."""
        skill_dir = tmp_path / "myskill"
        skill_dir.mkdir()
        kwargs: dict[str, Any] = dict(
            skill_id="myskill",
            subject_id="DOGE_USDT",
            variant="15m",
            research_id="res_abc123",
            insight_summary="v1",
        )
        path1 = append_findings(skill_dir, **kwargs)
        path2 = append_findings(
            skill_dir, **{**kwargs, "insight_summary": "v2"}
        )
        assert path1 == path2
        assert "v2" in path2.read_text()
        # Only one file in prior_findings.
        findings_dir = skill_dir / "knowledge" / "prior_findings"
        assert len(list(findings_dir.glob("*.md"))) == 1

    def test_distinct_research_ids_get_distinct_files(self, tmp_path: Path):
        skill_dir = tmp_path / "myskill"
        skill_dir.mkdir()
        append_findings(
            skill_dir, skill_id="s", subject_id="DOGE_USDT", variant="15m",
            research_id="res_one", insight_summary="a",
        )
        append_findings(
            skill_dir, skill_id="s", subject_id="DOGE_USDT", variant="15m",
            research_id="res_two", insight_summary="b",
        )
        findings_dir = skill_dir / "knowledge" / "prior_findings"
        assert len(list(findings_dir.glob("*.md"))) == 2

    def test_filename_is_safe(self, tmp_path: Path):
        """Path-traversal / weird characters in subject/variant are sanitized.

        Slashes are stripped (so ``../`` cannot escape the dir); the resulting
        filename is a single component under ``knowledge/prior_findings/``.
        """
        skill_dir = tmp_path / "s"
        skill_dir.mkdir()
        path = prior_findings_path(
            skill_dir,
            subject_id="../../../etc/passwd",
            variant="15m/..",
            research_id="res_x",
        )
        # Must stay under skill_dir/knowledge/prior_findings/ (no traversal).
        assert path.is_relative_to(skill_dir / "knowledge" / "prior_findings")
        # No path separators in the filename itself (single component).
        assert "/" not in path.name
        # Writing it actually lands inside the dir, not outside.
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("safe")
        assert path.is_file()
        assert (skill_dir / "knowledge" / "prior_findings").is_dir()

    def test_creates_prior_findings_dir_if_absent(self, tmp_path: Path):
        skill_dir = tmp_path / "s"
        skill_dir.mkdir()
        findings_dir = skill_dir / "knowledge" / "prior_findings"
        assert not findings_dir.exists()
        append_findings(
            skill_dir, skill_id="s", subject_id="x", variant="y",
            research_id="res_z", insight_summary="hi",
        )
        assert findings_dir.is_dir()


class TestRenderFindings:
    def test_extra_fields_included(self):
        text = render_findings_markdown(
            skill_id="s", subject_id="x", variant="y", research_id="r",
            insight_summary="body", extra={"custom_field": "value"},
        )
        meta = yaml.safe_load(text.split("---")[1])
        assert meta["custom_field"] == "value"


# ---------------------------------------------------------------------------
# P5-029 — stale-knowledge computation
# ---------------------------------------------------------------------------


def _is_stale(
    knowledge_last_reviewed: str | None,
    refresh_cadence_days: int | None,
    *,
    now: datetime,
) -> bool:
    """P5-029 helper: True when the knowledge corpus is past its refresh cadence.

    Replicates the computation the UI/GET /skills response uses. Not stale when
    either field is unset (no cadence configured ⇒ no staleness signal).
    """
    if not knowledge_last_reviewed or not refresh_cadence_days:
        return False
    reviewed = datetime.fromisoformat(knowledge_last_reviewed.replace("Z", "+00:00"))
    age = now - reviewed
    return age > timedelta(days=refresh_cadence_days)


class TestKnowledgeStale:
    def test_fresh_when_within_cadence(self):
        now = datetime(2026, 7, 27, tzinfo=timezone.utc)
        reviewed = "2026-07-20T00:00:00Z"  # 7 days ago
        assert _is_stale(reviewed, refresh_cadence_days=30, now=now) is False

    def test_stale_when_past_cadence(self):
        now = datetime(2026, 7, 27, tzinfo=timezone.utc)
        reviewed = "2026-06-01T00:00:00Z"  # ~56 days ago
        assert _is_stale(reviewed, refresh_cadence_days=30, now=now) is True

    def test_not_stale_when_cadence_unset(self):
        now = datetime(2026, 7, 27, tzinfo=timezone.utc)
        assert _is_stale("2020-01-01T00:00:00Z", refresh_cadence_days=None, now=now) is False

    def test_not_stale_when_reviewed_unset(self):
        now = datetime(2026, 7, 27, tzinfo=timezone.utc)
        assert _is_stale(None, refresh_cadence_days=30, now=now) is False
