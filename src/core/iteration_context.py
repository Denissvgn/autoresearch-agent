"""Compact iteration context digests for autoresearch agents."""

from __future__ import annotations

import json
import logging
import math
from typing import Any, Iterable, List, Mapping, Optional, Tuple

try:
    import yaml
except ImportError:  # pragma: no cover — pyyaml is a runtime dep
    yaml = None  # type: ignore[assignment]

from src.core.consistency_validator import parse_consistency_report
from src.core.gate_status import training_gates_passed_from_iteration

logger = logging.getLogger(__name__)

ITERATION_CONTEXT_DIGEST_MARKER = "[system] Iteration context digest"

# Per-model "salient knobs": YAML keys whose values, when surfaced together,
# uniquely identify the agent's intent for a given iteration. Used by the
# "Tried in prior sessions" digest section to render parameter signatures
# (e.g. ``direction_pct_threshold=0.05, purge_multiplier=4.0``) instead of
# opaque canonical_config_hash values that the agent cannot map back to its
# own draft YAML.
#
# Order matters: the digest renders keys in the order listed below so two
# rows with the same salient parameters always produce the same string.
_SALIENT_PARAMS_BY_MODEL: dict[str, tuple[str, ...]] = {
    "direction": (
        "direction_pct_threshold",
        "purge_multiplier",
        "horizon",
        "roster_preset",
        "calibration_method",
        "meta_model",
        "sample_weight_halflife",
        "threshold_strategy",
        "threshold_beta",
        "deadzone_width",
    ),
    "volatility": (
        "volatility_atr_mult",
        "atr_mult_sweep_enabled",
        "prediction_horizon",
        "threshold_strategy",
        "threshold_beta",
        "calibration_method",
        "roster_preset",
        "sample_weight_halflife",
        "purge_multiplier",
    ),
    "rl": (
        "net_arch_pi",
        "net_arch_vf",
        "n_envs",
        "n_steps",
        "learning_rate",
        "ent_coef",
        "clip_range",
        "total_timesteps",
        "trade_penalty",
    ),
}

# Numeric bucket widths for parameter-space clustering. Params NOT listed here
# (categoricals like roster_preset/calibration_method, list-valued like
# net_arch_pi) use their exact value as the cluster-key component. The
# special width ``"log"`` buckets by floor(log10(value)) — order of
# magnitude — for RL learning_rate / ent_coef where absolute step is
# meaningless.
_PARAM_BUCKETS: dict[str, dict[str, "float | str"]] = {
    "direction": {
        "direction_pct_threshold": 0.01,
        "purge_multiplier": 1.0,
        "horizon": 1,
        "sample_weight_halflife": 30,
        "threshold_beta": 0.25,
        "deadzone_width": 0.01,
    },
    "volatility": {
        "volatility_atr_mult": 0.5,
        "prediction_horizon": 1,
        "threshold_beta": 0.25,
        "sample_weight_halflife": 30,
        "purge_multiplier": 1.0,
    },
    "rl": {
        "n_envs": 2,
        "n_steps": 1024,
        "learning_rate": "log",
        "ent_coef": "log",
        "clip_range": 0.1,
        "total_timesteps": 100000,
        "trade_penalty": 0.005,
    },
}


# Gap 1 — map each salient knob to the phase-advancement marker key its
# presence-vs-baseline contributes to. After Issue 10A narrowed advancement
# keys to deliberate-exploration markers (e.g. ``tabular_sweep_variant``),
# agents that don't emit those keys explicitly fell through to the slow
# >=6 cardinality fallback (live: ``res_baf6605ce94f``). This map lets the
# server auto-derive the marker from any salient-knob diff vs the baseline
# iter's config_snapshot, restoring the fast key-path without requiring
# LLM compliance with the prompt instruction.
#
# Keys may be dotted to address nested config blocks (e.g. the ``feature_config``
# lane sub-flags), resolved against the parsed config_snapshot by
# ``derive_exploration_markers`` → ``_resolve_dotted``.
_KNOB_TO_MARKER: dict[str, dict[str, str]] = {
    "direction": {
        "direction_pct_threshold": "tabular_sweep_variant",
        "roster_preset": "tabular_sweep_variant",
        "deadzone_width": "tabular_sweep_variant",
        "calibration_method": "tabular_sweep_variant",
        "purge_multiplier": "tabular_sweep_variant",
        "horizon": "tabular_sweep_variant",
        "sample_weight_halflife": "tabular_sweep_variant",
        "threshold_strategy": "tabular_sweep_variant",
        "threshold_beta": "tabular_sweep_variant",
        # Feature-lane toggles (nested under feature_config) — flipping a lane is a
        # deliberate feature-set change, so credit it as a tabular_sweep_variant so
        # the phase advances and the iter is not treated as a no-op/duplicate.
        # NOTE: feature_config.vdmc_enabled is a historical lane key retained for
        # pre-migration config_snapshot rendering; new skills declare lanes via manifest.
        "feature_config.funding_features_enabled": "tabular_sweep_variant",
        "feature_config.open_interest_features_enabled": "tabular_sweep_variant",
        "feature_config.directional_change_features_enabled": "tabular_sweep_variant",
        "feature_config.vdmc_enabled": "tabular_sweep_variant",  # historical lane key
        "feature_config.spectral_features_enabled": "tabular_sweep_variant",
    },
    "volatility": {
        "volatility_atr_mult": "atr_mult_sweep_enabled",
        "atr_mult_sweep_enabled": "atr_mult_sweep_enabled",
        "threshold_strategy": "threshold_calibration_attempt_id",
        "threshold_beta": "threshold_calibration_attempt_id",
        "calibration_method": "threshold_calibration_attempt_id",
        "sample_weight_halflife": "temporal_ensemble_attempt_id",
        "prediction_horizon": "temporal_ensemble_attempt_id",
    },
}


def derive_exploration_markers(
    model_type: str,
    current_config: Mapping[str, Any] | None,
    baseline_config: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return phase-advancement markers this iter should emit, derived
    from salient-knob diffs vs the baseline iter's config_snapshot.

    An empty dict means the current config matches baseline on every
    salient knob (this iter IS the baseline, or a re-run with no
    deliberate exploration). The phase plan's advancement-key check will
    see no marker and require either an explicit key from the agent OR
    the cardinality fallback.

    The marker VALUE encodes which knobs drove the variant (e.g.
    ``"direction_pct_threshold=0.04+roster_preset=v2"``) so downstream
    digests can show *what* the agent changed without re-deriving it.
    """
    if not current_config or not baseline_config:
        return {}
    knob_map = _KNOB_TO_MARKER.get(model_type, {})
    markers: dict[str, Any] = {}
    for knob, marker_key in knob_map.items():
        cur = _resolve_dotted(current_config, knob)
        base = _resolve_dotted(baseline_config, knob)
        if cur is not None and cur != base:
            existing = markers.get(marker_key)
            # Drop the nesting prefix in the human-readable variant label.
            entry = f"{knob.rsplit('.', 1)[-1]}={cur}"
            markers[marker_key] = f"{existing}+{entry}" if existing else entry
    return markers


def _resolve_dotted(config: Mapping[str, Any], key: str) -> Any:
    """Resolve a possibly-dotted knob name against a (possibly nested) config.

    ``"threshold_beta"`` reads ``config["threshold_beta"]``;
    ``"feature_config.vdmc_enabled"`` walks into the nested ``feature_config``
    block. Returns None if any segment is missing or not a mapping."""
    if "." not in key:
        return config.get(key)
    node: Any = config
    for part in key.split("."):
        if not isinstance(node, Mapping):
            return None
        node = node.get(part)
    return node


def build_iteration_context_digest(
    *,
    session: Mapping[str, Any],
    iterations: Iterable[Mapping[str, Any]],
    hpo_studies: Iterable[Mapping[str, Any]] = (),
    planned_trials: Iterable[Mapping[str, Any]] = (),
    phase_state: Optional[Mapping[str, Any]] = None,
    prior_session_summary: Optional[Iterable[Mapping[str, Any]]] = None,
    promotion_readiness: Optional[Iterable[Mapping[str, Any]]] = None,
    max_chars: int = 6000,
    recent_attempts: int = 5,
) -> str:
    """Build a deterministic, bounded digest of persisted iteration state.

    ``prior_session_summary`` (optional) is the aggregated cross-session view
    produced by ``ResultsStore.get_cross_session_iteration_summary``: one row
    per ``canonical_config_hash`` already explored by other sessions on the
    same (instrument, timeframe, model_type). Surfaced to the agent so it
    can avoid re-trying configs that other sessions already covered, and so
    it can spot server-side feature gaps (e.g. ``adaptive_features
    unavailable``) without burning a training cycle to re-confirm them.
    """

    rows = list(iterations)
    studies = list(hpo_studies)
    trials = list(planned_trials)
    prior_summary = list(prior_session_summary or [])
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
    # Action 5: within-session foresight — list the distinct configs already tried so
    # the agent avoids spending a turn proposing a duplicate the guard would reject.
    lines.extend(_tried_configs_lines(rows))
    hpo_line = _hpo_line(studies, trials)
    if hpo_line:
        lines.append(f"- HPO/planned trials: {hpo_line}")
    lines.append(f"- Next decision guidance: {_next_guidance(rows)}")

    # Cross-session "tried configs" hint (Fix B) — surfaces canonical config
    # hashes that other sessions already explored on the same instrument /
    # timeframe / model_type so the agent does not re-discover them through
    # duplicate-rejection collisions in tabular_sweeps and later phases.
    tried_lines = _prior_session_tried_lines(
        prior_summary, model_type=model_type,
    )
    if tried_lines:
        lines.extend(tried_lines)

    # Server-side feature availability hint (Fix C) — observation-based:
    # mines the same cross-session summary for known "unavailable" markers
    # (e.g. adaptive_features_unavailable) so the agent stops re-attempting
    # features that the server cannot enable regardless of YAML config.
    availability_lines = _feature_availability_lines(rows, prior_summary)
    if availability_lines:
        lines.extend(availability_lines)

    # Phase guidance — surfaced every turn so the LLM knows which research
    # phase to advance and is warned immediately when it stalls in one phase.
    if phase_state:
        current_phase_id = phase_state.get("current_phase") or ""
        phase_next_action = phase_state.get("next_action") or ""
        stalled = int(
            phase_state.get("stalled_iterations")
            or phase_state.get("iterations_in_current_phase")
            or 0
        )
        if current_phase_id and phase_next_action:
            lines.append(
                f"- Research phase: {current_phase_id} \u2192 {phase_next_action}"
            )
        if stalled >= 5:
            lines.append(
                f"  \u26a0 STALL DETECTED: {stalled} consecutive iterations in "
                f"phase '{current_phase_id}' without advancing. "
                "Switch tools/approach now — do not run another experiment "
                "of the same kind until phase-appropriate tooling has been used."
            )

    # Promotion readiness — surface model-quality gate blockers on the current
    # best candidate so the agent can tune for them before the terminal phase,
    # rather than discovering them only at server-side promotion review.
    readiness = list(promotion_readiness or [])
    if readiness:
        lines.append(
            "- PROMOTION GATE would BLOCK the current best candidate "
            "(fix these in the relevant earlier phase):"
        )
        for detail in readiness:
            if not isinstance(detail, Mapping):
                continue
            code = detail.get("code") or "unknown"
            label = detail.get("label") or ""
            fix = detail.get("likely_fix") or ""
            lines.append(f"    - {code}: {label} {fix}".rstrip())

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
        f"training_gates={_yes_no(training_gates_passed_from_iteration(best))} "
        f"decision={best.get('decision') or '?'}"
    )


def _attempt_line(row: Mapping[str, Any]) -> str:
    metrics = _parse_mapping(row.get("metrics_json"))
    status = metrics.get("status") or row.get("status") or "recorded"
    parts = [
        f"#{row.get('iteration', '?')}",
        f"metric={_fmt(_number(row.get('primary_metric')))}",
        f"training_gates={_yes_no(training_gates_passed_from_iteration(row))}",
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


def _tried_configs_lines(iterations: List[Mapping[str, Any]]) -> List[str]:
    """Action 5: enumerate the distinct configs already attempted THIS session,
    decoded with their label levers (label_mode / threshold / atr_barrier_mult), so
    the agent does not spend a turn re-proposing a config the dedup guard will reject.
    Reuses the per-iteration levers surfaced into the iteration record (P5)."""
    seen: set[str] = set()
    entries: List[str] = []
    for row in reversed(iterations):  # most-recent first
        metrics = _parse_mapping(row.get("metrics_json"))
        chash = (
            row.get("canonical_config_hash")
            or metrics.get("canonical_config_hash")
        )
        label_mode = metrics.get("label_mode") or row.get("label_mode")
        threshold = metrics.get("direction_pct_threshold")
        if threshold is None:
            threshold = row.get("direction_pct_threshold")
        atr_mult = metrics.get("atr_barrier_mult")
        key = str(chash) if chash else f"{label_mode}|{threshold}|{atr_mult}"
        if key in seen:
            continue
        seen.add(key)
        desc: List[str] = []
        if label_mode:
            desc.append(str(label_mode))
        if threshold is not None:
            desc.append(f"thr={_fmt(_number(threshold))}")
        if label_mode == "vol_scaled" and atr_mult is not None:
            desc.append(f"atr_mult={_fmt(_number(atr_mult))}")
        if chash:
            desc.append(f"hash={_short(str(chash), 12)}")
        if desc:
            entries.append(f"#{row.get('iteration', '?')} " + " ".join(desc))
        if len(entries) >= 8:
            break
    if not entries:
        return []
    return [
        "- Already tried this session (do NOT re-propose an identical canonical "
        "config — it will be dedup-rejected; vary a meaningful lever):",
        *[f"  - {entry}" for entry in entries],
    ]


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
    if training_gates_passed_from_iteration(latest):
        return (
            "compare against best metric and collect promotion evidence "
            "instead of repeating the same trial."
        )
    return "adjust one bounded tuning dimension and explain the expected metric impact."


# Maximum number of prior-session canonical-config-hash lines to surface in
# the digest. Each line is short; cap is mostly defensive against truncation
# of more important sections by ``_cap_text``.
# Digest shows at most this many explored *regions* (clusters), not raw
# configs. The hybrid fill takes the top-_CLUSTER_TOP_BEST clusters by metric
# then stride-samples the remainder for breadth.
_PRIOR_SESSION_MAX_ENTRIES = 12
_CLUSTER_TOP_BEST = 5
_UNSIGNATURED_KEY: Tuple[Any, ...] = ("__nosig__",)


def _prior_session_tried_lines(
    summary: List[Mapping[str, Any]],
    *,
    model_type: str = "",
) -> List[str]:
    """Render the "Tried in prior sessions" digest block.

    The cross-session population (hundreds of configs) is collapsed into
    explored *regions* via parameter-space clustering, then a hybrid
    selection (top performers + a diversity spread across the metric range)
    fills a bounded number of digest lines. This shows the agent the shape
    of the already-explored space — not just the single best peak — so it
    can steer into an unexplored band before submitting instead of after a
    dedup rejection.

    Returns an empty list when the cross-session summary is empty so the
    digest stays unchanged for first-ever sessions on an instrument.
    """
    if not summary:
        return []
    rows = [r for r in summary if r.get("canonical_config_hash")]
    if not rows:
        return []

    clusters = _select_representative_clusters(
        rows, model_type, _PRIOR_SESSION_MAX_ENTRIES,
    )
    if not clusters:
        return []

    total_configs = sum(int(r.get("attempts") or 1) for r in rows)
    n_clusters = clusters[0]["_total_clusters"]
    best_metric = max(
        (c["best_metric"] for c in clusters if c["best_metric"] is not None),
        default=None,
    )
    out: List[str] = [
        (
            f"- Tried in prior sessions: {total_configs} configs in "
            f"{n_clusters} explored regions"
            f"{' (best=' + _fmt(best_metric) + ')' if best_metric is not None else ''}"
            ". Each line is one region — any YAML matching a region's "
            "signature is dedup-rejected. Move a salient knob into an "
            "unexplored band:"
        ),
    ]
    for c in clusters:
        chash = _short(str(c["representative_hash"] or ""), 12)
        metric = _fmt(c["best_metric"])
        size = c["size"]
        from_id = c["first_research_id"] or "prior session"
        if c["signature"]:
            out.append(
                f"  - {c['signature']} → best={metric} "
                f"({size} configs explored here, e.g. {chash} from {from_id})"
            )
        else:
            out.append(
                f"  - (no config snapshot) {size} configs, "
                f"e.g. hash={chash} from {from_id}"
            )
    shown = len(clusters)
    if n_clusters > shown:
        out.append(
            f"  - …{n_clusters - shown} more regions omitted (lower-metric "
            "variants of the above). Vary a salient knob into an unexplored "
            "band to avoid collisions."
        )
    return out


def _select_representative_clusters(
    rows: List[Mapping[str, Any]],
    model_type: str,
    max_entries: int,
) -> List[dict]:
    """Group rows into parameter-space clusters and pick a bounded,
    deterministic, representative subset (hybrid: top performers + spread).

    Returns a list of dicts in metric-descending order, each with:
    ``signature`` (str | None), ``best_metric`` (float | None),
    ``size`` (int), ``representative_hash`` (str), ``first_research_id``
    (str), and ``_total_clusters`` (int, identical on every element).
    """
    grouped: dict[Tuple[Any, ...], List[Mapping[str, Any]]] = {}
    for row in rows:
        parsed = _parse_snapshot(row.get("sample_config_snapshot"))
        key = _cluster_key(parsed, model_type)
        grouped.setdefault(key if key is not None else _UNSIGNATURED_KEY, []).append(
            row
        )

    clusters: List[dict] = []
    for key, members in grouped.items():
        # Representative = highest metric, tie-break lexicographic hash.
        def _rank(r: Mapping[str, Any]) -> Tuple[float, str]:
            m = _number(r.get("best_metric"))
            return (
                m if m is not None else float("-inf"),
                str(r.get("canonical_config_hash") or ""),
            )

        rep = max(members, key=_rank)
        rep_metric = _number(rep.get("best_metric"))
        if key == _UNSIGNATURED_KEY:
            signature = None
        else:
            parsed_rep = _parse_snapshot(rep.get("sample_config_snapshot"))
            signature = _signature_from_parsed(parsed_rep, model_type)
        clusters.append(
            {
                "signature": signature,
                "best_metric": rep_metric,
                "size": sum(int(m.get("attempts") or 1) for m in members),
                "representative_hash": rep.get("canonical_config_hash") or "",
                "first_research_id": rep.get("first_research_id"),
                "_sort_key": (
                    -(rep_metric if rep_metric is not None else float("-inf")),
                    repr(key),
                ),
            }
        )

    clusters.sort(key=lambda c: c["_sort_key"])
    total = len(clusters)

    if total <= max_entries:
        selected = clusters
    else:
        top = clusters[:_CLUSTER_TOP_BEST]
        rest = clusters[_CLUSTER_TOP_BEST:]
        remaining = max_entries - len(top)
        if rest and remaining > 0:
            step = max(1, len(rest) // remaining)
            spread = rest[::step][:remaining]
        else:
            spread = []
        selected = top + spread
        # Preserve global metric-desc order for display stability.
        selected.sort(key=lambda c: c["_sort_key"])

    for c in selected:
        c["_total_clusters"] = total
        c.pop("_sort_key", None)
    return selected


def _parse_snapshot(config_snapshot: Any) -> Optional[dict]:
    """Parse a YAML config_snapshot once. Returns the dict or None."""
    if not config_snapshot or not isinstance(config_snapshot, str):
        return None
    if yaml is None:
        return None
    try:
        parsed = yaml.safe_load(config_snapshot)
    except Exception as exc:  # pragma: no cover — corrupt snapshot
        logger.debug("Failed to parse config_snapshot: %s", exc)
        return None
    return parsed if isinstance(parsed, dict) else None


def _cluster_key(
    parsed: Optional[dict],
    model_type: str,
) -> Optional[Tuple[Any, ...]]:
    """Build a hashable, bucketed cluster key from a parsed config.

    Numeric salient params are bucketed per ``_PARAM_BUCKETS``; categorical
    / list params use their exact value. Missing params get a ``None`` slot
    so configs that omit a knob still cluster consistently. Returns ``None``
    when there is no parseable config or no salient keys for the model
    (caller routes those to the unsignatured bucket).
    """
    if not parsed:
        return None
    salient = _SALIENT_PARAMS_BY_MODEL.get(model_type or "", ())
    if not salient:
        return None
    buckets = _PARAM_BUCKETS.get(model_type or "", {})
    key_parts: List[Tuple[str, Any]] = []
    any_present = False
    for name in salient:
        if name not in parsed:
            key_parts.append((name, None))
            continue
        any_present = True
        value = parsed[name]
        key_parts.append((name, _bucket_value(value, buckets.get(name))))
    if not any_present:
        return None
    return tuple(key_parts)


def _bucket_value(value: Any, width: "float | str | None") -> Any:
    """Bucket a single value for clustering. Lists → tuple, numerics →
    rounded bucket index (or log10 magnitude for ``"log"``), everything
    else → the raw value."""
    if isinstance(value, list):
        return tuple(value)
    if width is None:
        return value
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return value
    if width == "log":
        try:
            return math.floor(math.log10(abs(value))) if value else 0
        except (ValueError, OverflowError):  # pragma: no cover
            return 0
    try:
        return round(float(value) / float(width))
    except (TypeError, ValueError, ZeroDivisionError):  # pragma: no cover
        return value


def _signature_from_parsed(
    parsed: Optional[dict],
    model_type: str,
) -> Optional[str]:
    """Render the ``key=value, …`` signature from an already-parsed config."""
    if not parsed:
        return None
    salient = _SALIENT_PARAMS_BY_MODEL.get(model_type or "", ())
    if not salient:
        return None
    parts: List[str] = []
    for key in salient:
        if key in parsed:
            value = parsed[key]
            if isinstance(value, list):
                rendered = "[" + ",".join(str(v) for v in value) + "]"
            elif isinstance(value, float):
                rendered = (
                    f"{value:.4f}".rstrip("0").rstrip(".")
                    if not value.is_integer()
                    else str(int(value))
                )
            else:
                rendered = str(value)
            parts.append(f"{key}={rendered}")
    if not parts:
        return None
    return ", ".join(parts)


def _extract_param_signature(
    config_snapshot: Any,
    model_type: str,
) -> Optional[str]:
    """Back-compat wrapper: parse a raw snapshot then render its signature.

    Retained for any external callers / tests; the clustering path uses
    ``_parse_snapshot`` + ``_signature_from_parsed`` directly to avoid
    re-parsing the YAML.
    """
    return _signature_from_parsed(
        _parse_snapshot(config_snapshot), model_type,
    )


# Minimum iteration-count + minimum distinct-session-count for an
# observation-based feature unavailability claim. Below these thresholds we
# stay silent to avoid false positives from a single transient failure.
_FEATURE_OBS_MIN_ITERATIONS = 3
_FEATURE_OBS_MIN_SESSIONS = 2


def _feature_availability_lines(
    same_session_rows: List[Mapping[str, Any]],
    prior_summary: List[Mapping[str, Any]],
) -> List[str]:
    """Detect persistent server-side feature unavailability across sessions.

    Currently scans for:
      - ``adaptive_feature_noop_reason: adaptive_features_unavailable``
      - ``tsfm_fallback_validation: True`` with no explicit ``tsfm_adapter``

    The data sources are:
      - ``same_session_rows``: parsed ``metrics_json`` of recorded iterations
        in the current session (covers transient gaps that the agent should
        not immediately retry).
      - ``prior_summary``: aggregated cross-session rows (covers persistent
        capability gaps observed across many sessions).
    """
    adaptive_iter_count = 0
    adaptive_session_count = 0
    tsfm_fallback_iter_count = 0
    tsfm_fallback_session_count = 0

    for row in prior_summary:
        attempts = int(row.get("attempts") or 0)
        session_count = int(row.get("session_count") or 0)
        noop_reasons = (row.get("noop_reasons") or "").lower()
        if "adaptive_features_unavailable" in noop_reasons:
            adaptive_iter_count += attempts
            adaptive_session_count += session_count
        tsfm_adapters = (row.get("tsfm_adapters") or "").strip()
        tsfm_fallback_flags = (row.get("tsfm_fallback_flags") or "").lower()
        has_real_adapter = tsfm_adapters and tsfm_adapters not in ("null", "none", "")
        has_fallback = "true" in tsfm_fallback_flags or "1" in tsfm_fallback_flags
        if has_fallback and not has_real_adapter:
            tsfm_fallback_iter_count += attempts
            tsfm_fallback_session_count += session_count

    same_session_seen_sessions = 1 if same_session_rows else 0
    for row in same_session_rows:
        metrics = _parse_mapping(row.get("metrics_json"))
        if metrics.get("adaptive_feature_noop_reason") == "adaptive_features_unavailable":
            adaptive_iter_count += 1
        if metrics.get("tsfm_fallback_validation") and not metrics.get("tsfm_adapter"):
            tsfm_fallback_iter_count += 1
    if same_session_seen_sessions and adaptive_iter_count > 0:
        adaptive_session_count = max(adaptive_session_count, 1)
    if same_session_seen_sessions and tsfm_fallback_iter_count > 0:
        tsfm_fallback_session_count = max(tsfm_fallback_session_count, 1)

    findings: List[str] = []
    if (
        adaptive_iter_count >= _FEATURE_OBS_MIN_ITERATIONS
        and adaptive_session_count >= _FEATURE_OBS_MIN_SESSIONS
    ):
        findings.append(
            f"  - adaptive_features: UNAVAILABLE (seen in {adaptive_iter_count} "
            f"iterations across {adaptive_session_count} sessions — do NOT "
            f"retry enabling; server cannot satisfy this config)"
        )
    if (
        tsfm_fallback_iter_count >= _FEATURE_OBS_MIN_ITERATIONS
        and tsfm_fallback_session_count >= _FEATURE_OBS_MIN_SESSIONS
    ):
        findings.append(
            f"  - tsfm: tabular-fallback only (seen in {tsfm_fallback_iter_count} "
            f"iterations across {tsfm_fallback_session_count} sessions — no "
            f"adapter candidate available; phase advances on fallback evidence)"
        )

    if not findings:
        return []
    return ["- Server-side feature availability:", *findings]


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
