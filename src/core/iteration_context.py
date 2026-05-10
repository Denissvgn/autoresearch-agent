"""Compact iteration context digests for autoresearch agents."""

from __future__ import annotations

import json
from typing import Any, Iterable, List, Mapping, Optional

from src.core.consistency_validator import parse_consistency_report

ITERATION_CONTEXT_DIGEST_MARKER = "[system] Iteration context digest"


def build_iteration_context_digest(
    *,
    session: Mapping[str, Any],
    iterations: Iterable[Mapping[str, Any]],
    hpo_studies: Iterable[Mapping[str, Any]] = (),
    planned_trials: Iterable[Mapping[str, Any]] = (),
    max_chars: int = 6000,
    recent_attempts: int = 5,
) -> str:
    """Build a deterministic, bounded digest of persisted iteration state."""

    rows = list(iterations)
    studies = list(hpo_studies)
    trials = list(planned_trials)
    max_chars = max(500, int(max_chars or 6000))
    recent_attempts = max(1, int(recent_attempts or 5))
    research_id = session.get("id") or session.get("research_id") or "unknown"
    model_type = session.get("model_type") or "unknown"
    instrument = session.get("instrument") or "unknown"
    timeframe = session.get("timeframe") or "unknown"
    cost = _number(session.get("total_api_cost_usd"))
    budget = _number(session.get("max_budget_usd"))
    max_iterations = session.get("max_iterations")

    lines: List[str] = [
        f"{ITERATION_CONTEXT_DIGEST_MARKER}:",
        (
            f"- Session: {research_id} {model_type} {instrument} {timeframe}; "
            f"iterations={len(rows)}/{max_iterations if max_iterations is not None else '?'}; "
            f"cost={_money(cost)}/{_money(budget)}"
        ),
        f"- Best so far: {_best_line(rows)}",
        "- Recent attempts:",
    ]

    if rows:
        for row in rows[-recent_attempts:]:
            lines.append(f"  - {_attempt_line(row)}")
    else:
        lines.append("  - none recorded yet")

    lines.append(f"- Current blockers: {_blockers_line(rows)}")
    lines.append(f"- Do not repeat: {_duplicate_line(rows)}")
    hpo_line = _hpo_line(studies, trials)
    if hpo_line:
        lines.append(f"- HPO/planned trials: {hpo_line}")
    lines.append(f"- Next decision guidance: {_next_guidance(rows)}")
    return _cap_text("\n".join(lines), max_chars)


def _best_line(iterations: List[Mapping[str, Any]]) -> str:
    candidates = [
        row for row in iterations
        if _number(row.get("primary_metric")) is not None
        and row.get("decision") in {"keep", "improve", "hpo_screening"}
    ]
    if not candidates:
        return "none yet"
    best = max(candidates, key=lambda row: _number(row.get("primary_metric")) or float("-inf"))
    return (
        f"iteration {best.get('iteration', '?')} "
        f"{best.get('metric_name') or 'metric'}={_fmt(_number(best.get('primary_metric')))} "
        f"gates={_yes_no(best.get('all_gates_passed'))} "
        f"decision={best.get('decision') or '?'}"
    )


def _attempt_line(row: Mapping[str, Any]) -> str:
    metrics = _parse_mapping(row.get("metrics_json"))
    status = metrics.get("status") or row.get("status") or "recorded"
    parts = [
        f"#{row.get('iteration', '?')}",
        f"metric={_fmt(_number(row.get('primary_metric')))}",
        f"gates={_yes_no(row.get('all_gates_passed'))}",
        f"decision={row.get('decision') or '?'}",
        f"status={status}",
    ]
    blockers = _row_blockers(row)
    if blockers:
        parts.append("blockers=" + ",".join(blockers[:3]))
    duplicate = row.get("duplicate_reason") or metrics.get("duplicate_reason")
    if duplicate:
        parts.append("duplicate=" + _short(str(duplicate), 120))
    desc = row.get("description")
    if desc:
        parts.append("note=" + _short(str(desc), 120))
    return "; ".join(parts)


def _blockers_line(iterations: List[Mapping[str, Any]]) -> str:
    blockers: List[str] = []
    for row in reversed(iterations):
        for blocker in _row_blockers(row):
            if blocker not in blockers:
                blockers.append(blocker)
            if len(blockers) >= 6:
                break
        if len(blockers) >= 6:
            break
    return ", ".join(blockers) if blockers else "none recorded"


def _duplicate_line(iterations: List[Mapping[str, Any]]) -> str:
    duplicates = [
        row for row in reversed(iterations)
        if row.get("duplicate_reason")
        or (_parse_mapping(row.get("metrics_json")).get("status") == "rejected_duplicate")
    ]
    if not duplicates:
        hashes = [
            str(row.get("trial_identity_hash") or row.get("canonical_config_hash"))
            for row in reversed(iterations)
            if row.get("trial_identity_hash") or row.get("canonical_config_hash")
        ]
        if not hashes:
            return "no duplicate rejections recorded"
        compact = ", ".join(_short(value, 12) for value in hashes[:3])
        return f"avoid exact config/seed/mode repeats; recent identities={compact}"
    row = duplicates[0]
    ref = row.get("duplicate_of_research_id") or "existing session"
    iteration = row.get("duplicate_of_iteration")
    reason = row.get("duplicate_reason") or "duplicate training attempt"
    suffix = f" iteration {iteration}" if iteration is not None else ""
    return f"{_short(str(reason), 180)}; duplicate_of={ref}{suffix}"


def _hpo_line(
    studies: List[Mapping[str, Any]],
    trials: List[Mapping[str, Any]],
) -> Optional[str]:
    if not studies and not trials:
        return None
    statuses: dict[str, int] = {}
    for trial in trials:
        status = str(trial.get("status") or "unknown")
        statuses[status] = statuses.get(status, 0) + 1
    study_bits = []
    for study in studies[-2:]:
        study_id = study.get("study_id") or study.get("id") or "study"
        completed = study.get("completed_trials")
        maximum = study.get("max_trials") or study.get("n_trials")
        status = study.get("status") or "unknown"
        study_bits.append(f"{study_id}:{status}:{completed}/{maximum}")
    status_bits = ", ".join(f"{key}={value}" for key, value in sorted(statuses.items()))
    pieces = []
    if study_bits:
        pieces.append("studies " + "; ".join(study_bits))
    if status_bits:
        pieces.append("trials " + status_bits)
    return "; ".join(pieces) if pieces else None


def _next_guidance(iterations: List[Mapping[str, Any]]) -> str:
    if not iterations:
        return "run the baseline or first server-owned planned trial."
    latest = iterations[-1]
    if latest.get("duplicate_reason"):
        return "choose a materially different config identity before running again."
    blockers = _row_blockers(latest)
    if blockers:
        return "address the latest blockers before treating the candidate as promotable."
    if latest.get("all_gates_passed"):
        return "compare against best metric and collect promotion evidence instead of repeating the same trial."
    return "adjust one bounded tuning dimension and explain the expected metric impact."


def _row_blockers(row: Mapping[str, Any]) -> List[str]:
    blockers: List[str] = []
    report = parse_consistency_report(row.get("consistency_report_json"))
    raw = report.get("blockers") if report else None
    if isinstance(raw, list):
        blockers.extend(str(item) for item in raw if item)
    metrics = _parse_mapping(row.get("metrics_json"))
    for key in ("gate_failures", "blockers", "promotion_blockers"):
        value = metrics.get(key)
        if isinstance(value, list):
            blockers.extend(str(item) for item in value if item)
    return _unique(blockers)


def _parse_mapping(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _unique(values: Iterable[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _number(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _fmt(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    return f"{value:.4f}"


def _money(value: Optional[float]) -> str:
    if value is None:
        return "$?"
    return f"${value:.4f}"


def _yes_no(value: Any) -> str:
    return "yes" if bool(value) else "no"


def _short(value: str, limit: int) -> str:
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def _cap_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    suffix = "\n[truncated]"
    return text[: max_chars - len(suffix)] + suffix
