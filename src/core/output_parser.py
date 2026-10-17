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

import hmac
import json
import logging
import math
import re
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import Any, Mapping, Optional, Protocol, TypedDict, cast

from src.core.artifact_reference import (
    ARTIFACT_REFERENCE_KEYS,
    normalize_optional_artifact_ref,
)
from src.core.gate_status import coerce_bool, normalize_training_gate_aliases

logger = logging.getLogger(__name__)

# prepare.py outputs a --- delimited block of key: value pairs
_KV_PATTERN = re.compile(r"^\s*(\w[\w_]*)\s*:\s*(.*?)\s*$")
_ITERATION_MARKER = "ITERATION_RESULT:"

# ── Normalized result contract ─────────────────────────────────────────────
#
# One contract for every result source (agent-visible stdout markers and
# artifact/marker-file collection apply identical rules). A payload either
# validates against the declared result semantics or becomes explicit invalid
# evidence — never implicit success.

#: Version stamp a result payload may declare. An unknown version is invalid
#: evidence; absence is accepted (legacy payloads) and recorded as this
#: contract's version on the normalized result.
RESULT_SCHEMA_VERSION = "iteration_result.v1"

#: Statuses that mean the run completed AND may carry a winning metric.
SUCCESS_STATUSES = frozenset({"completed", "success"})

#: Declared field types. The unit-bearing names are numeric (finite) values
#: whose unit is part of the declaration and is preserved on the normalized
#: result so a reported number can never silently change meaning.
FIELD_TYPE_VOCABULARY = frozenset(
    {
        "string",
        "integer",
        "number",
        "boolean",
        "seconds",
        "milliseconds",
        "bytes",
        "ratio",
    }
)
_UNIT_FIELD_TYPES = frozenset({"seconds", "milliseconds", "bytes", "ratio"})

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


@dataclass(frozen=True)
class ResultSpec:
    """The declared result semantics (built from ``output_parser``).

    ``failure_statuses`` is the declared list unioned with the core
    :data:`FAILURE_STATUSES` — a run whose status is in the set is a
    non-winning outcome regardless of which side declared it.
    """

    format: str = "json_marker"
    marker_prefix: str = _ITERATION_MARKER
    block_delimiter: str = "---"
    required_fields: tuple[str, ...] = ()
    field_types: Mapping[str, str] = dataclass_field(default_factory=dict)
    failure_statuses: frozenset[str] = FAILURE_STATUSES
    schema_versions: frozenset[str] = frozenset({RESULT_SCHEMA_VERSION})

    @classmethod
    def from_output_parser(cls, op: Any) -> "ResultSpec":
        """Build the spec from a manifest ``OutputParserConfig`` (or None)."""
        if op is None:
            return cls()
        declared_failures = frozenset(str(s) for s in (op.failure_statuses or ()))
        return cls(
            format=str(getattr(op, "format", None) or "json_marker"),
            marker_prefix=str(
                getattr(op, "iteration_marker", None) or _ITERATION_MARKER
            ),
            block_delimiter=str(getattr(op, "block_delimiter", None) or "---"),
            required_fields=tuple(str(f) for f in (op.required_fields or ())),
            field_types=dict(getattr(op, "field_types", None) or {}),
            failure_statuses=FAILURE_STATUSES | declared_failures,
        )


@dataclass(frozen=True)
class NormalizedResult:
    """One normalized result with its trusted raw evidence preserved.

    ``outcome`` is the semantics class: ``completed`` (may be a win),
    ``failed`` (declared failure status — non-winning, never carrying a
    promotable metric), ``invalid`` (contract violations — explicit invalid
    evidence, never implicit success). ``raw_evidence`` keeps the verbatim
    parsed payload so audits can see exactly what the source said.
    """

    outcome: str
    status: Optional[str]
    primary_metric: Optional[float]
    metric_name: Optional[str]
    direction: str
    gates_passed: Optional[bool]
    training_time_s: Optional[float]
    fields: Mapping[str, Any]
    units: Mapping[str, str]
    raw_evidence: Mapping[str, Any]
    violations: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.violations

    def to_dict(self) -> dict[str, Any]:
        """The record-facing dict (IterationMetrics shape + explicit flags)."""
        out: dict[str, Any] = {
            "status": self.status if self.status is not None else "",
            "primary_metric": self.primary_metric,
            "metric_name": self.metric_name,
            "direction": self.direction,
            "training_gates_passed": bool(self.gates_passed),
            "all_gates_passed": bool(self.gates_passed),
            "gates_declared": self.gates_passed is not None,
            "training_time_s": self.training_time_s,
            "result_valid": self.valid,
            "result_outcome": self.outcome,
            "result_schema_version": RESULT_SCHEMA_VERSION,
        }
        if self.violations:
            out["invalid_evidence"] = list(self.violations)
        if self.units:
            out["field_units"] = dict(self.units)
        # The trusted raw evidence is preserved verbatim, separately from the
        # normalized fields above (audits read exactly what the source said).
        out["raw_evidence"] = dict(self.raw_evidence)
        for key, value in self.fields.items():
            out.setdefault(key, value)
        return out


def _coerce_kv_value(key: str, value: str) -> Any:
    """Legacy-compatible coercion of one raw KV pair into a typed value."""
    if key == "gate_failures":
        return [part.strip() for part in value.split(";") if part.strip()]
    if key in ARTIFACT_REFERENCE_KEYS:
        return normalize_optional_artifact_ref(value)
    if key in {"is_tsfm_candidate", "tsfm_candidate", "auto_phase_evidence"}:
        return coerce_bool(value)
    if key.endswith("_json"):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    try:
        return float(value)
    except ValueError:
        return value


def extract_raw_result(
    text: str, spec: ResultSpec, *, allow_bare_json: bool = True
) -> Optional[dict[str, Any]]:
    """Extract the raw result payload in the DECLARED form.

    The marker channel (the declared prefix) is independent of the block
    format and always available — agent relays and marker files use it. The
    block channel honors the declared ``format``: ``delimited_kv`` reads the
    declared-delimiter block; ``json_marker`` accepts a bare top-level JSON
    object when ``allow_bare_json`` (the artifact-file form). The returned
    dict is verbatim source evidence — no defaults.
    """
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith(spec.marker_prefix):
            continue
        payload = stripped[len(spec.marker_prefix):].strip()
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            logger.warning("Failed to parse result marker JSON: %s", payload)
            continue
        if isinstance(parsed, dict):
            return dict(parsed)
        logger.warning("Result marker JSON was not an object: %s", payload)

    if spec.format == "delimited_kv":
        raw: dict[str, Any] = {}
        in_block = False
        saw = False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped == spec.block_delimiter:
                if in_block:
                    break
                in_block = True
                continue
            if not in_block:
                continue
            match = _KV_PATTERN.match(line)
            if not match:
                continue
            raw[match.group(1)] = _coerce_kv_value(
                match.group(1), match.group(2).strip()
            )
            saw = True
        return raw if saw else None

    if not allow_bare_json:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return dict(parsed) if isinstance(parsed, dict) else None


def normalize_result(raw: Mapping[str, Any], spec: ResultSpec) -> NormalizedResult:
    """Apply the declared result semantics to one raw payload.

    Structural violations (missing status, unknown schema version, missing
    required fields, declared-type mismatches, nonfinite numbers, unknown
    status semantics) make the result **invalid**; a declared failure status
    makes it **failed** (non-winning, never carrying a promotable metric);
    only a well-formed ``completed``/``success`` payload is **completed**.
    Missing gates normalize to ``None`` — never a successful default.
    """
    violations: list[str] = []
    payload = dict(raw)
    if "training_gates_passed" in payload or "all_gates_passed" in payload:
        normalize_training_gate_aliases(payload, logger=logger, context="result")

    raw_status = payload.get("status")
    status: Optional[str]
    if isinstance(raw_status, str) and raw_status.strip():
        status = raw_status.strip()
    else:
        status = None
        violations.append("missing status")

    declared_version = payload.get("schema_version")
    if (
        declared_version is not None
        and str(declared_version) not in spec.schema_versions
    ):
        violations.append(f"unknown result schema version {declared_version!r}")

    for name in spec.required_fields:
        value = payload.get(name)
        if value is None or (isinstance(value, str) and not value.strip()):
            violations.append(f"missing required field {name}")

    def _check_finite(name: str, value: Any) -> None:
        if isinstance(value, bool):
            return
        if isinstance(value, (int, float)) and not math.isfinite(float(value)):
            violations.append(f"nonfinite value for {name}")

    for name, value in payload.items():
        if isinstance(value, (list, tuple)):
            for item in value:
                _check_finite(name, item)
        else:
            _check_finite(name, value)

    fields: dict[str, Any] = {
        name: value for name, value in payload.items() if name != "status"
    }
    units: dict[str, str] = {}
    for name, type_name in dict(spec.field_types).items():
        type_name = str(type_name)
        if type_name not in FIELD_TYPE_VOCABULARY:
            violations.append(f"unknown declared field type {type_name!r} for {name}")
            continue
        if name not in payload:
            continue
        value = payload[name]
        if type_name == "string":
            if not isinstance(value, str):
                violations.append(f"{name} must be a string")
        elif type_name == "boolean":
            if isinstance(value, bool):
                pass
            elif isinstance(value, str) and value.strip().lower() in {"true", "false"}:
                fields[name] = value.strip().lower() == "true"
            else:
                violations.append(f"{name} must be a boolean")
        elif type_name == "integer":
            if isinstance(value, bool):
                violations.append(f"{name} must be an integer")
            elif isinstance(value, int):
                pass
            elif isinstance(value, float) and value.is_integer():
                fields[name] = int(value)
            else:
                violations.append(f"{name} must be an integer")
        else:  # number / seconds / milliseconds / bytes / ratio
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                violations.append(f"{name} must be a finite number")
            elif not math.isfinite(float(value)):
                violations.append(f"nonfinite value for {name}")
            else:
                fields[name] = float(value)
                if type_name in _UNIT_FIELD_TYPES:
                    units[name] = type_name

    metric_raw = payload.get("primary_metric")
    primary_metric: Optional[float] = None
    if isinstance(metric_raw, bool):
        violations.append("primary_metric must be a finite number")
    elif isinstance(metric_raw, (int, float)):
        if math.isfinite(float(metric_raw)):
            primary_metric = float(metric_raw)
        else:
            violations.append("nonfinite value for primary_metric")
    elif isinstance(metric_raw, str):
        try:
            parsed_metric = float(metric_raw)
        except ValueError:
            parsed_metric = None
        if parsed_metric is not None and math.isfinite(parsed_metric):
            primary_metric = parsed_metric
        else:
            violations.append("primary_metric must be a finite number")
    elif metric_raw is not None:
        violations.append("primary_metric must be a finite number")

    gates_raw = payload.get("training_gates_passed")
    if gates_raw is None:
        gates_raw = payload.get("all_gates_passed")
    if gates_raw is None:
        gates_raw = payload.get("gates_passed")
    gates_passed = None if gates_raw is None else coerce_bool(gates_raw)

    training_time_raw = payload.get("training_time_s")
    training_time_s: Optional[float] = None
    if isinstance(training_time_raw, (int, float)) and not isinstance(
        training_time_raw, bool
    ):
        if math.isfinite(float(training_time_raw)):
            training_time_s = float(training_time_raw)

    status_key = (status or "").lower()
    if status is not None and status_key in spec.failure_statuses:
        outcome = "failed"
    elif status is not None and status_key in SUCCESS_STATUSES:
        outcome = "completed"
    else:
        outcome = "invalid"
        if status is not None:
            violations.append(f"unknown status semantics {status!r}")
    if violations and outcome != "failed":
        outcome = "invalid"

    # A failed or invalid result never carries a promotable metric — the
    # placeholder or measured value stays in the raw evidence only.
    if outcome != "completed":
        primary_metric = None

    return NormalizedResult(
        outcome=outcome,
        status=status,
        primary_metric=primary_metric,
        metric_name=(
            str(payload["metric_name"])
            if payload.get("metric_name") is not None
            else None
        ),
        direction=str(payload.get("direction") or "higher_is_better"),
        gates_passed=gates_passed,
        training_time_s=training_time_s,
        fields=fields,
        units=units,
        raw_evidence=dict(raw),
        violations=tuple(violations),
    )


def parse_result_text(
    text: str, spec: ResultSpec, *, allow_bare_json: bool = True
) -> Optional[NormalizedResult]:
    """Parse ``text`` in the declared format and normalize the result.

    The one entry point for stdout and artifact collection: identical
    extraction and identical rules for both. Returns ``None`` only when no
    result payload is present at all — a present-but-broken payload yields a
    normalized ``invalid`` result (explicit evidence, never a silent success).
    """
    raw = extract_raw_result(text, spec, allow_bare_json=allow_bare_json)
    if raw is None:
        return None
    return normalize_result(raw, spec)


def parse_and_verify_text(
    text: str,
    spec: ResultSpec,
    *,
    session_nonce: Optional[bytes] = None,
    nonce_field: Optional[str] = None,
    require_signed_metrics: bool = False,
    allow_bare_json: bool = True,
) -> Optional[IterationResult]:
    """Contract parse plus the W11 nonce check — the runtime's one entry."""
    normalized = parse_result_text(text, spec, allow_bare_json=allow_bare_json)
    if normalized is None:
        return None
    return _verify_nonce(
        cast(IterationResult, normalized.to_dict()),
        session_nonce=session_nonce,
        nonce_field=nonce_field,
        require_signed_metrics=require_signed_metrics,
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
    metrics_verification: Optional[str]
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
    covers the JSON-line-scan form. P4-003/P4-005 add ``nonce_field`` and
    ``require_signed_metrics`` parameters for the W11 anti-forgery contract:
    when ``require_signed_metrics`` is true, the parser validates the echoed
    nonce against ``session_nonce`` and rejects forged blocks.
    """

    def parse(self, raw_output: str) -> Optional[IterationResult]:
        """Parse a ``---`` delimited key:value block into a result dict."""
        ...

    def parse_iteration(
        self,
        text: str,
        *,
        session_nonce: Optional[bytes] = None,
        config_snapshot: Optional[str] = None,
        nonce_field: Optional[str] = None,
        require_signed_metrics: bool = False,
    ) -> Optional[IterationResult]:
        """Scan agent text for an ``ITERATION_RESULT:`` JSON marker.

        When ``require_signed_metrics`` is true, validates the echoed nonce
        (under ``nonce_field``) against ``session_nonce``. A missing or wrong
        nonce rejects the block (returns ``None``). A verified result carries
        ``metrics_verification: "metrics_verified"``; an unverified one (flag
        false or legacy session) carries ``"metrics_unverified"`` (P4-005).
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
        nonce_field: Optional[str] = None,
        require_signed_metrics: bool = False,
    ) -> Optional[IterationResult]:
        """``DelimitedKVParser`` does not scan for ``ITERATION_RESULT:`` markers.

        Provided to satisfy the ``OutputParser`` protocol; delegates to
        :meth:`parse` so a caller that hands arbitrary text to a KV parser gets
        the same behavior as the old ``parse_prepare_output`` (block absent →
        defaults). P4-003: when ``require_signed_metrics`` is true, validates
        the echoed nonce in the ``---`` block.
        """
        result = self.parse(text)
        return _verify_nonce(
            result,
            session_nonce=session_nonce,
            nonce_field=nonce_field,
            require_signed_metrics=require_signed_metrics,
        )


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

    def __init__(self, marker_prefix: str = _ITERATION_MARKER) -> None:
        self._marker_prefix = marker_prefix

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
        nonce_field: Optional[str] = None,
        require_signed_metrics: bool = False,
    ) -> Optional[IterationResult]:
        """Scan ``text`` line-by-line for an ``ITERATION_RESULT:`` JSON marker.

        P4-003: when ``require_signed_metrics`` is true, validates the echoed
        nonce (under ``nonce_field``) against ``session_nonce``. A missing or
        wrong nonce rejects the marker (returns ``None``). Returns the parsed
        dict (gate-alias-normalized in place) or ``None`` if no well-formed
        marker dict is found.
        """
        result = _scan_iteration_marker(text, self._marker_prefix)
        return _verify_nonce(
            result,
            session_nonce=session_nonce,
            nonce_field=nonce_field,
            require_signed_metrics=require_signed_metrics,
        )

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
    cast(dict[str, Any], result).update(extra)
    return result


def _scan_iteration_marker(
    text: str, marker_prefix: str = _ITERATION_MARKER
) -> Optional[IterationResult]:
    """Scan for a marker-prefixed JSON line — body moved from
    parse_iteration_marker (the prefix is the DECLARED one)."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(marker_prefix):
            json_str = stripped[len(marker_prefix):].strip()
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


def _verify_nonce(
    result: Optional[IterationResult],
    *,
    session_nonce: Optional[bytes],
    nonce_field: Optional[str],
    require_signed_metrics: bool,
) -> Optional[IterationResult]:
    """Verify the W11 anti-forgery nonce in a parsed result (P4-003/P4-005).

    Returns the result (possibly annotated) or ``None`` (rejected as forged).

    * ``require_signed_metrics=False`` (default): no validation; the result is
      returned **unchanged** (no ``metrics_verification`` key) so the X-002
      parity fixtures for ML skills stay byte-identical.
    * ``require_signed_metrics=True`` + nonce matches: the result gains
      ``metrics_verification: "metrics_verified"``.
    * ``require_signed_metrics=True`` + nonce missing/wrong: returns ``None``
      (forged — the iteration is not recorded).
    * ``require_signed_metrics=True`` but ``session_nonce`` is ``None`` (legacy
      session without a nonce): graceful downgrade — the result gains
      ``metrics_verification: "metrics_unverified"`` and a warning is logged.
    """
    if result is None:
        return None

    if not require_signed_metrics:
        return result

    # Normalize the session nonce to a hex string for comparison.
    if session_nonce is None:
        logger.warning(
            "require_signed_metrics=true but session has no nonce; "
            "downgrading to metrics_unverified (legacy session)"
        )
        result["metrics_verification"] = "metrics_unverified"
        return result

    expected = session_nonce.hex() if isinstance(session_nonce, bytes) else str(session_nonce)
    field = nonce_field or "server_nonce"
    echoed = result.get(field)

    if echoed is None:
        logger.warning(
            "Iteration marker rejected: nonce field %r is absent (forged)", field,
        )
        return None

    if not hmac.compare_digest(str(echoed).encode("utf-8"), expected.encode("utf-8")):
        # ARC-011 review C3: constant-time compare — consistent with the
        # fail-closed posture elsewhere (production-approval HMAC) even though
        # a 256-bit hex nonce makes timing attacks impractical.
        logger.warning(
            "Iteration marker rejected: nonce mismatch (expected %s, got %s) — forged",
            expected[:8] + "...", str(echoed)[:8] + "...",
        )
        return None

    result["metrics_verification"] = "metrics_verified"
    return result


__all__ = [
    "DelimitedKVParser",
    "FAILURE_STATUSES",
    "FIELD_TYPE_VOCABULARY",
    "IterationResult",
    "JSONMarkerParser",
    "NormalizedResult",
    "OutputParser",
    "RESULT_SCHEMA_VERSION",
    "ResultSpec",
    "SUCCESS_STATUSES",
    "extract_raw_result",
    "normalize_result",
    "parse_and_verify_text",
    "parse_result_text",
]
