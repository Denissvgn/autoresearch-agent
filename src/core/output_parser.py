"""``OutputParser`` protocol + concrete parsers (ARC-011 P1-010..012).

This module introduces the ``OutputParser`` protocol — the abstraction every
consumer reaches through to turn experiment output (``prepare.py`` stdout or
agent-emitted ``ITERATION_RESULT:`` markers) into a structured result dict.

Two concrete implementations land alongside the protocol:

* ``DelimitedKVParser`` (P1-011) — extracts the ``---`` delimited key:value
  block parsing that lived in ``experiment_parser.parse_prepare_output``.
* ``JSONMarkerParser`` (P1-012) — extracts the ``ITERATION_RESULT:`` JSON-line
  scanning that lived in ``experiment_parser.parse_iteration_marker``.

The extraction is **behavior-identical**: every parser body is unchanged, and
the X-002 parity suite is preserved. ``experiment_parser.py`` keeps the four
historical module-level functions (``parse_prepare_output``,
``parse_iteration_marker``, ``is_hpo_study_output``, ``parse_hpo_study_output``)
as thin facades over the new classes so the parity engine
(``tests/parity/_engine.py``, which dispatches by string function name and
imports ``from src.core.experiment_parser import ...``) keeps resolving without
a fixture re-capture. Mirrors the P1-007 ``results_store`` back-compat shim.

Design decisions baked in here:

* **Not ``@runtime_checkable``.** ``isinstance`` against a ``Protocol`` only
  checks attribute presence (false confidence on signatures). This is a
  typing-time contract; consumers accept it as a typed parameter. Mirrors the
  ``LLMProvider`` / ``StateStore`` decisions.
* **Two methods, not one.** ``parse_prepare_output`` and
  ``parse_iteration_marker`` have different semantics (delimited KV-block vs
  JSON-line-scan) and the orchestrator calls them at different points, so the
  protocol carries both rather than collapsing them into a single overloaded
  ``parse``. ``SkillRuntime.parse_iteration`` (P1-023) composes both.
* **``session_nonce`` is accepted but ignored (P1-010 deviation).** The
  ``SkillRuntime`` design calls for nonce validation on ``parse_iteration`` to
  reject forged metrics blocks, but **zero nonce-validation code exists today**
  and introducing it is a Phase-4 behavior change (P4 anti-forgery epic). The
  ``parse_iteration`` signature here accepts ``session_nonce: bytes`` for
  forward-compatibility, but ``JSONMarkerParser.parse_iteration`` ignores it and
  delegates to the unchanged marker scanner. Recorded as an AC-deviation in the
  CHANGELOG and this module docstring (P1-007 house style).

``IterationResult`` is a ``TypedDict`` alias over the flat dict shape produced
by ``IterationMetrics.to_dict()`` (``experiment_parser.py``): ``status``,
``primary_metric``, ``metric_name``, ``direction``, ``training_gates_passed``,
``all_gates_passed``, ``training_time_s`` plus any splatted ``extra`` keys.
``TypedDict`` (not a dataclass) is deliberate — callers (orchestrator, parity
engine) keep treating the result as a plain mutable dict, so a typing-only
alias preserves byte-identical behavior with zero construction churn.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional, Protocol, TypedDict

from src.core.artifact_reference import (
    ARTIFACT_REFERENCE_KEYS,
    normalize_optional_artifact_ref,
)
from src.core.gate_status import coerce_bool, normalize_training_gate_aliases

logger = logging.getLogger(__name__)

# prepare.py outputs a --- delimited block of key: value pairs
_KV_PATTERN = re.compile(r"^\s*(\w[\w_]*)\s*:\s*(.*?)\s*$")
_ITERATION_MARKER = "ITERATION_RESULT:"

# Statuses prepare.py emits when a run did NOT produce a valid model. The
# failure blocks (auth_failed / gpubusy / timeout / crash / generic failure)
# print a placeholder ``primary_metric: 0.000000`` so the --- block stays
# well-formed — but that 0.0 is NOT a result. Without nulling it, the phantom
# 0.0 surfaces as the iteration's metric and can even register as an
# "improvement" over a prior failure (observed for RL on res_76d405b8caf9,
# where a failed HPO study reported composite_rl_score=0.0). Keep this aligned
# with the failure-status set the orchestrator uses to record discard
# iterations and with research_phase_plan.FAILED_ITERATION_STATUSES.
# (Moved verbatim from experiment_parser.py; see P1-011.)
FAILURE_STATUSES = frozenset(
    {"crash", "timeout", "failed", "error", "pruned", "auth_failed", "gpu_busy"}
)


class IterationResult(TypedDict, total=False):
    """Structured result of parsing one experiment output.

    Alias over the flat dict shape ``IterationMetrics.to_dict()`` produces
    (``experiment_parser.py``). ``total=False`` because every key is optional
    in practice — a failure block omits ``primary_metric``, an absent marker
    omits everything. Callers continue to read these via ``dict.get(...)``.
    """

    status: str
    primary_metric: Optional[float]
    metric_name: Optional[str]
    direction: str
    training_gates_passed: bool
    all_gates_passed: bool
    training_time_s: Optional[float]
    # ``extra`` keys are splatted to the top level by IterationMetrics.to_dict()
    # (e.g. gate_failures, calibration, *_json, artifact refs). TypedDict cannot
    # express "arbitrary additional keys" statically; callers use .get().


class OutputParser(Protocol):
    """The experiment-output parsing contract (ARC-011 P1-010).

    A concrete parser (``DelimitedKVParser`` for ``prepare.py`` stdout,
    ``JSONMarkerParser`` for ``ITERATION_RESULT:`` agent markers) implements
    this surface. The orchestrator (P1-013) is wired to accept any
    ``OutputParser``.

    ``parse`` covers the ``---`` delimited KV-block form; ``parse_iteration``
    covers the JSON-line-scan form with a (forward-compat, currently ignored)
    ``session_nonce`` forgery hook.
    """

    def parse(self, raw_output: str) -> Optional[IterationResult]:
        """Parse a ``---`` delimited key:value block into a result dict.

        Returns ``None`` if no ``---`` block is present (delegates to the
        ``parse_prepare_output`` logic; never returns ``None`` today — it
        returns an ``IterationMetrics`` with defaults — but the protocol
        permits ``None`` so a future parser can signal "no parseable block").
        """
        ...

    def parse_iteration(
        self,
        text: str,
        *,
        session_nonce: Optional[bytes] = None,
        config_snapshot: Optional[str] = None,
    ) -> Optional[IterationResult]:
        """Scan agent text for an ``ITERATION_RESULT:`` JSON marker.

        ``session_nonce`` is accepted for forward-compatibility with the P4
        anti-forgery work but **ignored** by the transitional parsers (no nonce
        validation exists today — see module docstring deviation note).
        """
        ...


class DelimitedKVParser:
    """Parse the ``---`` delimited key:value block from ``prepare.py`` stdout.

    Extracted verbatim (P1-011) from ``experiment_parser.parse_prepare_output``;
    the module-level function is now a thin facade over this class. The body is
    unchanged — every load-bearing edge case (``_json`` dual-write, int-via-JSON
    preservation, bool coercion for ``auto_phase_evidence`` /
    ``is_tsfm_candidate`` / ``tsfm_candidate``, ``gate_failures`` semicolon
    split, ``ARTIFACT_REFERENCE_KEYS`` normalization, gate-alias reconciliation
    with conflict warning, ``FAILURE_STATUSES`` primary_metric nulling) is
    preserved bit-for-bit. The X-002 parity fixtures gate this.

    Returns a flat dict shaped like ``IterationMetrics.to_dict()`` (the same
    shape the orchestrator consumes after calling ``.to_dict()`` on the old
    return value). Keys absent from the block take their ``IterationMetrics``
    defaults.
    """

    def parse(self, raw_output: str) -> Optional[IterationResult]:
        """Parse the ``---`` delimited block into a flat result dict.

        Never returns ``None`` today (mirrors ``parse_prepare_output`` which
        always returns an ``IterationMetrics``); the ``Optional`` honors the
        protocol's forward-compatible contract.
        """
        return _parse_delimited_block(raw_output)

    def parse_iteration(
        self,
        text: str,
        *,
        session_nonce: Optional[bytes] = None,
        config_snapshot: Optional[str] = None,
    ) -> Optional[IterationResult]:
        """``DelimitedKVParser`` does not scan for ``ITERATION_RESULT:`` markers.

        Provided to satisfy the ``OutputParser`` protocol; delegates to
        :meth:`parse` so a caller that hands arbitrary text to a KV parser gets
        the same behavior as the old ``parse_prepare_output`` (block absent →
        defaults). ``session_nonce`` is ignored (see module docstring).
        """
        return self.parse(text)


class JSONMarkerParser:
    """Parse an ``ITERATION_RESULT:`` JSON line from agent output.

    Extracted verbatim (P1-012) from ``experiment_parser.parse_iteration_marker``;
    the module-level function is now a thin facade over this class. The body is
    unchanged — scan-past-malformed-JSON and in-place gate-alias normalization
    are preserved bit-for-bit. The X-002 parity fixtures gate this.

    ``parse_iteration`` is the primary entry point (matches the protocol);
    ``parse_marker`` is the historical name kept as an alias so
    ``experiment_parser.parse_iteration_marker`` can delegate without rename.
    """

    def parse(self, raw_output: str) -> Optional[IterationResult]:
        """KV-block parsing is not this parser's concern.

        Provided to satisfy the ``OutputParser`` protocol; a JSON-marker parser
        handed a ``---`` block returns ``None`` (no ``ITERATION_RESULT:`` line).
        """
        return self.parse_iteration(raw_output)

    def parse_iteration(
        self,
        text: str,
        *,
        session_nonce: Optional[bytes] = None,
        config_snapshot: Optional[str] = None,
    ) -> Optional[IterationResult]:
        """Scan ``text`` line-by-line for an ``ITERATION_RESULT:`` JSON marker.

        ``session_nonce`` is accepted for forward-compatibility with the P4
        anti-forgery work but **ignored** (no nonce validation exists today —
        see module docstring). Returns the parsed dict (gate-alias-normalized
        in place) or ``None`` if no well-formed marker dict is found.
        """
        return _scan_iteration_marker(text)

    def parse_marker(self, text: str) -> Optional[IterationResult]:
        """Historical alias for :meth:`parse_iteration` (no nonce kwarg)."""
        return self.parse_iteration(text)


# ---------------------------------------------------------------------------
# Implementation helpers (moved verbatim from experiment_parser.py, P1-011/P1-012).
# Kept module-private so the facade functions in experiment_parser.py and the
# parser classes above share one source of truth.
# ---------------------------------------------------------------------------


def _parse_delimited_block(stdout: str) -> IterationResult:
    """Parse the ``---`` delimited block — body moved from parse_prepare_output."""
    # Mirrors the field set of IterationMetrics (experiment_parser.py). Kept as
    # a plain dict so the return type matches IterationMetrics.to_dict() and the
    # orchestrator's existing .get()/mutation usage is unchanged.
    status: str = "unknown"
    primary_metric: Optional[float] = None
    metric_name: Optional[str] = None
    direction: str = "higher_is_better"
    training_gates_passed: bool = False
    all_gates_passed: bool = False
    training_time_s: Optional[float] = None
    extra: dict[str, Any] = {}
    saw_training_gates = False
    saw_legacy_gates = False

    in_block = False
    for line in stdout.splitlines():
        stripped = line.strip()
        if stripped == "---":
            if in_block:
                break  # End of block
            in_block = True
            continue
        if not in_block:
            continue

        match = _KV_PATTERN.match(line)
        if not match:
            continue

        key, value = match.group(1), match.group(2).strip()

        if key == "status":
            status = value
        elif key == "primary_metric":
            try:
                primary_metric = float(value)
            except ValueError:
                logger.warning("Could not parse primary_metric: %s", value)
        elif key == "metric_name":
            metric_name = value
        elif key == "direction":
            direction = value
        elif key == "training_gates_passed":
            training_gates_passed = coerce_bool(value)
            saw_training_gates = True
        elif key == "all_gates_passed":
            all_gates_passed = coerce_bool(value)
            saw_legacy_gates = True
        elif key == "training_time_s":
            try:
                training_time_s = float(value)
            except ValueError:
                pass
        elif key == "gate_failures":
            # Semicolon-separated list of gate failure reasons
            extra[key] = [s.strip() for s in value.split(";") if s.strip()]
        elif key in ARTIFACT_REFERENCE_KEYS:
            extra[key] = normalize_optional_artifact_ref(value)
        elif key in {"is_tsfm_candidate", "tsfm_candidate", "auto_phase_evidence"}:
            extra[key] = coerce_bool(value)
        elif key.endswith("_json"):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                extra[key] = value
            else:
                extra[key] = parsed
                extra[key[: -len("_json")]] = parsed
        else:
            # Store any extra metrics
            try:
                extra[key] = float(value)
            except ValueError:
                extra[key] = value

    if saw_training_gates:
        if saw_legacy_gates and all_gates_passed != training_gates_passed:
            logger.warning(
                "Conflicting prepare.py gate aliases: "
                "training_gates_passed=%s all_gates_passed=%s; "
                "using training_gates_passed",
                training_gates_passed,
                all_gates_passed,
            )
        all_gates_passed = training_gates_passed
    elif saw_legacy_gates:
        training_gates_passed = all_gates_passed

    # A failed run has no meaningful primary metric. prepare.py's failure
    # blocks emit a placeholder ``primary_metric: 0.000000`` to keep the ---
    # block parseable; null it here so the 0.0 cannot masquerade as a result
    # (phantom metric / false "improvement" over a prior failure).
    if primary_metric is not None and status.lower() in FAILURE_STATUSES:
        primary_metric = None

    result: IterationResult = {
        "status": status,
        "primary_metric": primary_metric,
        "metric_name": metric_name,
        "direction": direction,
        "training_gates_passed": training_gates_passed,
        "all_gates_passed": all_gates_passed,
        "training_time_s": training_time_s,
    }
    # Splatted extras land at the top level, exactly as
    # IterationMetrics.to_dict() does.
    result.update(extra)
    return result


def _scan_iteration_marker(text: str) -> Optional[IterationResult]:
    """Scan for an ``ITERATION_RESULT:`` JSON line — body moved from
    parse_iteration_marker."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(_ITERATION_MARKER):
            json_str = stripped[len(_ITERATION_MARKER):].strip()
            try:
                payload = json.loads(json_str)
            except json.JSONDecodeError:
                logger.warning("Failed to parse iteration marker JSON: %s", json_str)
                continue
            if isinstance(payload, dict):
                if (
                    "training_gates_passed" in payload
                    or "all_gates_passed" in payload
                ):
                    normalize_training_gate_aliases(
                        payload,
                        logger=logger,
                        context="ITERATION_RESULT",
                    )
                return payload  # type: ignore[return-value]
            logger.warning("Iteration marker JSON was not an object: %s", json_str)
    return None


__all__ = [
    "DelimitedKVParser",
    "FAILURE_STATUSES",
    "IterationResult",
    "JSONMarkerParser",
    "OutputParser",
]
