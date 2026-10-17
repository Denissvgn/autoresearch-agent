"""Research session management endpoints."""

from __future__ import annotations

import glob
import hashlib
import json
import logging
import os
from collections.abc import Awaitable, Callable
from typing import Any, Dict, Mapping, Optional

import yaml
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator, model_validator

from src.api.audit import record_api_audit_event
from src.api.auth import require_api_auth
from src.config import settings
from src.core.legacy_alias import (
    is_known_model_type,
    model_type_to_skill_id,
    skill_id_to_model_type,
)
from src.core.pagination import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    build_cursor_page,
    compute_next_cursor,
    decode_cursor,
)
from src.core.skill_manifest import ManifestValidationError
from src.core.skill_registry import SkillNotRegisteredError, default_registry
from src.core.skill_runtime import SkillConfigError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["research"], dependencies=[Depends(require_api_auth)])


def _started_at_id_cursor(row: Mapping[str, Any]) -> tuple[Any, Any]:
    """Cursor extractor for sessions/pipelines (sorted by started_at DESC, id DESC)."""

    return (row["started_at"], row["id"])

# These will be injected by main.py
_session_manager = None
_store = None


def init(session_manager, store):
    global _session_manager, _store
    _session_manager = session_manager
    _store = store


def _start_metadata(req: "StartResearchRequest") -> dict[str, Any]:
    return {
        "instrument": req.instrument,
        "timeframe": req.timeframe,
        "model_type": req.model_type,
        # ARC-011 implementation review C1 (2026-08-15): record the winning
        # canonical values, not just shape_conflict records.
        # record_api_audit_event drops None extras, so legacy requests audit
        # exactly as before.
        "skill_id": req.skill_id,
        "skill_params": req.skill_params,
        "subject_id": req.subject_id,
        "variant": req.variant,
        "tag": req.tag,
        "quick_mode": req.quick_mode,
        "max_iterations": req.max_iterations,
        "max_budget_usd": req.max_budget_usd,
        "timeout_minutes": req.timeout_minutes,
        "manifest_supplied": req.manifest is not None,
    }


def _continue_metadata(req: "ContinueResearchRequest") -> dict[str, Any]:
    return {
        "max_iterations": req.max_iterations,
        "max_budget_usd": req.max_budget_usd,
        "timeout_minutes": req.timeout_minutes,
        "focus_hint_supplied": req.focus_hint is not None,
    }


def _runtime_resume_metadata(req: "RuntimeResumeRequest") -> dict[str, Any]:
    return {
        "reason_supplied": bool(req.reason),
        "allow_interrupted": req.allow_interrupted,
        "max_iterations": req.max_iterations,
        "max_budget_usd": req.max_budget_usd,
        "timeout_minutes": req.timeout_minutes,
        "focus_hint_supplied": req.focus_hint is not None,
    }


async def _audit(
    request: Request,
    *,
    action: str,
    outcome: str,
    research_id: str | None = None,
    pipeline_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    error_message: str | None = None,
):
    return await record_api_audit_event(
        request,
        _store,
        action=action,
        outcome=outcome,
        research_id=research_id,
        pipeline_id=pipeline_id,
        metadata=metadata,
        error_message=error_message,
    )


def _dual_shape_session(session: Dict[str, Any]) -> Dict[str, Any]:
    """Augment a session dict with canonical (skill_id/subject_id/variant)
    and legacy (model_type/instrument/timeframe) fields (§10 guarantee #4:
    dual-shape responses).

    Legacy fields are the source of truth in the DB today; canonical fields are
    derived via the ``legacy_alias`` registry. When the DB gains native
    ``skill_id``/``subject_id``/``variant`` columns (P3-019), those become the
    source and legacy fields are derived — the response shape stays the same.

    Canonical fields are populated for every row via the identity alias
    fallback (a skill_id without a legacy short name is its own model_type).
    Legacy rows written before the skill migration keep rendering correctly.
    """
    augmented = dict(session)
    model_type = session.get("model_type", "") or ""
    instrument = session.get("instrument", "") or ""
    timeframe = session.get("timeframe", "") or ""

    # Canonical fields — derived from legacy via the alias registry.
    if "skill_id" not in augmented or not augmented.get("skill_id"):
        augmented["skill_id"] = model_type_to_skill_id(model_type) if model_type else ""
    if "subject_id" not in augmented or not augmented.get("subject_id"):
        augmented["subject_id"] = instrument
    if "variant" not in augmented or not augmented.get("variant"):
        augmented["variant"] = timeframe

    # Legacy fields — always populated (guarantee #4).
    augmented.setdefault("model_type", model_type)
    augmented.setdefault("instrument", instrument)
    augmented.setdefault("timeframe", timeframe)

    # Links block (ARC-011 §7.7).
    sid = session.get("id")
    if sid:
        augmented["links"] = {
            "self": f"/research/{sid}",
            "results": f"/research/{sid}/results",
            "iterations": f"/research/{sid}/iterations",
            "best": f"/research/{sid}/best",
            "stop": f"/research/{sid}/stop",
            "promote_preview": f"/research/{sid}/promote/preview",
        }
    return augmented


def _translate_legacy_request(req: "StartResearchRequest") -> None:
    """D3 translation shim (ARC-012 P7-010): translate a legacy
    ``model_type``-only request to the canonical ``skill_id`` shape.

    Mutates ``req`` in place. ``model_type`` goes through the alias map
    (``direction → ml-direction``; any other non-empty value is already a
    skill id per the identity fallback) and the legacy identity fields seed
    the canonical ``subject_id``/``variant`` when the caller did not send
    them explicitly. The translated request then faces the *same*
    installed-skill check as any canonical request in
    ``_translate_canonical_request`` — a legacy alias whose skill is not
    installed fails as 404 ``skill_not_found`` naming the translated id
    (e.g. ``ml-direction``), never a special "legacy rejected" error. If an
    ML skill is ever reinstalled, legacy callers work again unchanged.
    """
    req.skill_id = model_type_to_skill_id(req.model_type or "")
    if not req.subject_id:
        req.subject_id = req.instrument
    if not req.variant:
        req.variant = req.timeframe


def _skill_config_http_error(skill_id: str, exc: SkillConfigError) -> HTTPException:
    """Map a start-time ``SkillConfigError`` to a structured 4xx (P7-010).

    The API layer's translation already 404s unknown skills before the
    session manager runs; this maps the manager's defense-in-depth
    ``SkillConfigError`` (unresolvable skill id, no skill id at all, or a
    manifest that fails to load) so a guaranteed-fatal start is a 4xx with
    the skill id — not a 201 for a session that crashes on its first tick,
    and not a 500.
    """
    if not skill_id:
        return HTTPException(
            status_code=422,
            detail={
                "error": "skill_id_required",
                "message": str(exc),
            },
        )
    available = default_registry.available()
    if skill_id not in available:
        return HTTPException(
            status_code=404,
            detail={
                "error": "skill_not_found",
                "skill_id": skill_id,
                "available": available,
                "hint": "Install the skill under skills/<id>/ and reload.",
            },
        )
    return HTTPException(
        status_code=422,
        detail={
            "error": "skill_config_invalid",
            "skill_id": skill_id,
            "message": str(exc),
        },
    )


def _translate_canonical_request(
    req: "StartResearchRequest",
) -> list[dict[str, Any]]:
    """Translate a canonical request (skill_id/subject_id/variant) to the
    legacy fields (model_type/instrument/timeframe) the session_manager expects.

    Mutates ``req`` in place. Called only when ``req.skill_id`` is set (canonical
    shape). Raises ``HTTPException(404)`` for an unknown ``skill_id`` (P3-013 AC).

    Canonical wins unconditionally when both shapes are present (P3-013 risk:
    "a client sending both shapes with conflicting values — canonical wins;
    warn in audit"). Returns a list of conflict records (one per legacy field
    that was present but differed from the canonical value) so the caller can
    audit them.
    """
    conflicts: list[dict[str, Any]] = []
    if not req.skill_id:
        return conflicts
    # Validate skill_id exists in the registry (404 with hint). A registered
    # id whose manifest fails to load is a 422 (P7-010: the manifest load is
    # part of start validation, not a deferred runtime concern).
    try:
        default_registry.get(req.skill_id)
    except SkillNotRegisteredError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "skill_not_found",
                "skill_id": req.skill_id,
                "available": exc.available,
                "hint": "Install the skill under skills/<id>/ and reload.",
            },
        ) from exc
    except ManifestValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "skill_config_invalid",
                "skill_id": req.skill_id,
                "message": str(exc),
            },
        ) from exc

    # Canonical → legacy translation. Canonical wins unconditionally — the
    # legacy field is always overwritten from the canonical value so a
    # conflicting legacy value can never silently win (P3-013 risk).
    #
    # ARC-012 P7-006/D1: the discriminator is "is this a known legacy ML
    # alias?", NOT the truthiness of the identity-fallback translation.
    # ``skill_id_to_model_type`` pass-through returns the skill id itself for
    # non-ML skills; those have no legacy alias and must carry
    # ``model_type=""`` (the closed-vocabulary "no alias" value), never the
    # skill id (which the manifest pattern would reject — blocker B1).
    mt = skill_id_to_model_type(req.skill_id)
    if not is_known_model_type(mt):
        if req.model_type and req.model_type != mt:
            conflicts.append(
                {"field": "model_type", "canonical": "", "legacy": req.model_type}
            )
        req.model_type = ""
    else:
        if req.model_type and req.model_type != mt:
            conflicts.append(
                {"field": "model_type", "canonical": mt, "legacy": req.model_type}
            )
        req.model_type = mt

    # Subject/variant defaulting (ARC-012 P7-006): the skill enumerates its
    # own subjects/variants; a canonical request that omits them takes the
    # skill's first static entry rather than arriving downstream blank
    # (blank instrument/timeframe would fail the manifest's non-blank rule).
    if not req.subject_id or not req.variant:
        try:
            skill_manifest = default_registry.get(req.skill_id)
        except SkillNotRegisteredError:  # pragma: no cover — 404 raised above
            skill_manifest = None
        if not req.subject_id:
            static_subjects = getattr(
                getattr(skill_manifest, "subjects", None), "static", None
            ) or []
            req.subject_id = (
                static_subjects[0].id if static_subjects else "default"
            )
        if not req.variant:
            static_variants = getattr(
                getattr(skill_manifest, "variants", None), "static", None
            ) or []
            req.variant = static_variants[0] if static_variants else "default"

    # Path-safety: subject_id/variant become workspace path segments for
    # skill sessions (session_path_template) — reject separators at the
    # boundary instead of failing mid-start.
    from src.core.skill_paths import sanitize_path_segment

    for field_name in ("subject_id", "variant"):
        value = getattr(req, field_name) or ""
        try:
            sanitize_path_segment(value, field=field_name)
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "invalid_subject_or_variant",
                    "field": field_name,
                    "message": str(exc),
                },
            ) from exc

    canonical_instrument = req.subject_id or ""
    if req.instrument and req.instrument != canonical_instrument:
        conflicts.append(
            {
                "field": "instrument",
                "canonical": canonical_instrument,
                "legacy": req.instrument,
            }
        )
    req.instrument = canonical_instrument

    canonical_timeframe = req.variant or ""
    if req.timeframe and req.timeframe != canonical_timeframe:
        conflicts.append(
            {
                "field": "timeframe",
                "canonical": canonical_timeframe,
                "legacy": req.timeframe,
            }
        )
    req.timeframe = canonical_timeframe

    return conflicts


def _validate_skill_params(
    skill_id: str,
    params: Dict[str, Any] | None,
    schema: Any,
) -> Dict[str, Any]:
    """Resolve and validate ``skill_params`` against the skill's ``param_schema``.

    The one canonical resolution path (:mod:`src.core.skill_params`): an
    omitted/null parameter object resolves to ``{}`` (so schemas declaring
    required fields reject it exactly like an empty submission), declared
    defaults are applied deliberately, and the resolved object is validated
    once with the standard JSON Schema validator over the declared dialect
    subset. Returns the resolved parameter object to bind into execution.

    Raises ``HTTPException(422)`` with field addresses on violation — the
    same error contract any UI form validation mirrors.
    """
    from src.core.skill_params import resolve_and_validate

    resolved, violations = resolve_and_validate(skill_id, schema, params)
    if violations:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "skill_params_invalid",
                "skill_id": skill_id,
                "violations": violations,
            },
        )
    return resolved


def _json_hash(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def _run_idempotent(
    *,
    operation: str,
    parent_id: str,
    key: str | None,
    request_payload: Dict[str, Any],
    call: Callable[[], Awaitable[Dict[str, Any]]],
) -> Dict[str, Any]:
    if not key or not key.strip():
        raise HTTPException(status_code=400, detail="Idempotency-Key header is required")
    if _store is None:
        raise HTTPException(status_code=503, detail="Results store is not initialized")

    key_hash = hashlib.sha256(key.strip().encode("utf-8")).hexdigest()
    request_hash = _json_hash(
        {
            "operation": operation,
            "parent_id": parent_id,
            "request": request_payload,
        }
    )
    existing = await _store.begin_idempotency_record(
        operation=operation,
        parent_id=parent_id,
        key_hash=key_hash,
        request_hash=request_hash,
    )
    if existing:
        if existing.get("request_hash") != request_hash:
            raise HTTPException(
                status_code=409,
                detail="Idempotency-Key was already used for a different request",
            )
        if existing.get("status") == "completed" and existing.get("response_json"):
            try:
                return json.loads(existing["response_json"])
            except (json.JSONDecodeError, TypeError) as exc:
                raise HTTPException(
                    status_code=500,
                    detail="Stored idempotency response is invalid",
                ) from exc
        raise HTTPException(
            status_code=409,
            detail="Idempotent request is already in progress",
        )

    try:
        response = await call()
    except Exception:
        await _store.delete_idempotency_record(
            operation=operation,
            parent_id=parent_id,
            key_hash=key_hash,
        )
        raise

    await _store.complete_idempotency_record(
        operation=operation,
        parent_id=parent_id,
        key_hash=key_hash,
        child_id=response.get("id"),
        response=response,
    )
    return response


# ------------------------------------------------------------------
# Request / Response models
# ------------------------------------------------------------------


class StartResearchRequest(BaseModel):
    # Legacy shape (§10 #1: still accepted identically).
    instrument: Optional[str] = Field(default=None, examples=["subject-a"])
    timeframe: Optional[str] = Field(default=None, examples=["v1"])
    model_type: Optional[str] = Field(
        default=None,
        description=(
            "Legacy alias for skill_id. Known legacy short names "
            "(direction/volatility/rl) map to their canonical skill ids; any "
            "other value is used as the skill_id directly. Unknown skills are "
            "rejected with 404 skill_not_found. In responses this is a derived "
            "legacy alias: the trio for ML skills, or \"\" for skills without "
            "one — never a skill id."
        ),
    )
    # Canonical shape (ARC-011 §7.7 / P3-013).
    skill_id: Optional[str] = Field(default=None, examples=["ml-direction"])
    subject_id: Optional[str] = Field(default=None, examples=["DOGE_USDT"])
    variant: Optional[str] = Field(default=None, examples=["15m"])
    skill_params: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "Canonical skill parameters, validated against the skill's "
            "param_schema. Sent alongside skill_id; ignored for legacy shape."
        ),
    )
    tag: Optional[str] = Field(default=None, examples=["doge-apr01"])
    quick_mode: Optional[bool] = Field(
        default=None,
        description="If null, uses server default (standard/full mode)",
    )
    max_iterations: Optional[int] = Field(default=None, ge=1, le=500)
    max_budget_usd: Optional[float] = Field(default=None, ge=0.1, le=500.0)
    timeout_minutes: Optional[int] = Field(
        default=None, ge=30, le=1440,
        description="Session timeout in minutes (default: server setting, typically 120)",
    )
    focus_hint: Optional[str] = Field(
        default=None, max_length=1000,
        description="Optional hint for the agent about what to focus on",
    )
    manifest: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "Optional research-session manifest overrides. Immutable identity "
            "fields must still match the server-generated session."
        ),
    )

    @model_validator(mode="after")
    def _validate_shape_presence(self) -> "StartResearchRequest":
        """P3-013: at least one request shape must be present — either the
        legacy ``{model_type, instrument, timeframe}`` or the canonical
        ``{skill_id, subject_id, variant}``. Sending neither is a 422."""
        if not self.model_type and not self.skill_id:
            raise ValueError(
                "Either legacy {model_type, instrument, timeframe} or "
                "canonical {skill_id, subject_id, variant} must be provided"
            )
        return self


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------


class EstimateCostRequest(BaseModel):
    """Body for ``POST /research/estimate-cost`` — the New-Research preview."""

    max_iterations: int = Field(default=30, ge=1, le=500)
    quick_mode: bool = Field(
        default=False,
        description="Quick mode uses a smaller session-average context proxy.",
    )
    max_budget_usd: Optional[float] = Field(
        default=None,
        ge=0.1,
        le=500.0,
        description=(
            "When set, the response reports whether the estimate would be "
            "capped by this budget."
        ),
    )


@router.post("/research/estimate-cost")
async def estimate_research_cost(req: EstimateCostRequest):
    """Expected-cost preview for a planned session (P2 ops).

    Replaces the UI's ``$0.24 × iterations`` heuristic with the same pricing
    the post-call ledger uses (``llm_provider.estimate_session_cost``) — an
    expected-value estimate, not the orchestrator's worst-case pre-spend gate.
    """
    from src.core.llm_provider import estimate_session_cost

    estimate = estimate_session_cost(
        iterations=req.max_iterations, quick_mode=req.quick_mode,
    )
    total = float(estimate["total_usd"])  # type: ignore[arg-type]
    capped_by_budget = bool(
        req.max_budget_usd is not None and total > req.max_budget_usd
    )
    return {
        "per_iteration_usd": estimate["per_iteration_usd"],
        "total_usd": min(total, req.max_budget_usd) if capped_by_budget else total,
        "uncapped_total_usd": total,
        "capped_by_budget": capped_by_budget,
        "max_budget_usd": req.max_budget_usd,
        "assumptions": estimate["assumptions"],
    }


@router.post("/research/start", status_code=201)
async def start_research(request: Request, req: StartResearchRequest):
    # ARC-012 P7-010 / D3: a legacy model_type-only request is translated to
    # the canonical skill_id shape FIRST (pure alias translation, not policy),
    # then takes the same installed-skill check as a canonical request below.
    if not req.skill_id and req.model_type:
        _translate_legacy_request(req)
    # P3-013: translate canonical {skill_id, subject_id, variant} → legacy
    # {model_type, instrument, timeframe} the session_manager expects.
    # The resolved parameter object (defaults applied deliberately by the
    # canonical path below); legacy non-skill requests pass their raw value.
    resolved_skill_params: Dict[str, Any] | None = req.skill_params
    if req.skill_id:
        conflicts = _translate_canonical_request(req)
        if conflicts:
            await _audit(
                request,
                action="research.shape_conflict",
                outcome="warning",
                metadata={"skill_id": req.skill_id, "conflicts": conflicts},
            )
        # Validate skill_params against the skill's param_schema on the one
        # canonical resolution path — including omitted/null parameter objects
        # (a schema declaring required fields must reject those too).
        manifest = default_registry.get(req.skill_id)
        resolved_skill_params = _validate_skill_params(
            req.skill_id, req.skill_params, manifest.param_schema
        )

    metadata = _start_metadata(req)
    try:
        session = await _session_manager.start_session(
            instrument=req.instrument,
            timeframe=req.timeframe,
            model_type=req.model_type,
            tag=req.tag,
            quick_mode=req.quick_mode,
            max_iterations=req.max_iterations,
            max_budget_usd=req.max_budget_usd,
            timeout_minutes=req.timeout_minutes,
            focus_hint=req.focus_hint,
            manifest=req.manifest,
            # ARC-011 implementation review C1 (2026-08-15): forward the
            # canonical shape instead of dropping it after validation —
            # skill_id routes the manifest runtime; skill_params (already
            # validated against the skill's param_schema above) reach
            # ResearchConfig; subject_id/variant are authoritative aliases.
            skill_id=req.skill_id,
            skill_params=resolved_skill_params,
            subject_id=req.subject_id,
            variant=req.variant,
        )
        await _audit(
            request,
            action="research.start",
            outcome="success",
            research_id=session.get("id"),
            metadata=metadata,
        )
        return _dual_shape_session(session)
    except SkillConfigError as e:
        # ARC-012 P7-010: a session that cannot materialize its skill runtime
        # never started — 4xx, no row, no background task.
        await _audit(
            request,
            action="research.start",
            outcome="failure",
            metadata=metadata,
            error_message=str(e),
        )
        raise _skill_config_http_error(req.skill_id or "", e) from e
    except RuntimeError as e:
        await _audit(
            request,
            action="research.start",
            outcome="failure",
            metadata=metadata,
            error_message=str(e),
        )
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.get("/research")
async def list_research(
    status: Optional[str] = None,
    model_type: Optional[str] = None,
    instrument: Optional[str] = None,
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0, deprecated=True),
    cursor: Optional[str] = None,
):
    """Paginated session listing.

    Opaque cursor pagination is the primary mode: pass the
    ``next_cursor`` from a prior response to fetch the next page — the response
    is then ``{items, limit, next_cursor}`` (no ``total``). The legacy
    ``offset`` parameter is deprecated; omitting ``cursor`` preserves the
    original ``{items, total, limit, offset}`` envelope exactly.
    """

    # Under direct (non-FastAPI) calls used by the test suite, `limit`/`offset`
    # receive the Query() sentinel rather than their defaults; coerce them.
    if not isinstance(limit, int):
        limit = DEFAULT_PAGE_SIZE
    if not isinstance(offset, int):
        offset = 0
    decoded = decode_cursor(cursor)
    if decoded is None and cursor:
        logger.warning("malformed /research cursor token; serving page 1")
    if decoded is not None:
        items = await _store.list_sessions(
            status=status, model_type=model_type, instrument=instrument,
            limit=limit, cursor=decoded,
        )
        items = [_dual_shape_session(s) for s in items]
        return build_cursor_page(items, limit, _started_at_id_cursor)
    if offset > 0:
        logger.warning(
            "offset pagination is deprecated for /research; use cursor "
            "(ARC-011 P0-016)"
        )
    items = await _store.list_sessions(
        status=status, model_type=model_type, instrument=instrument,
        limit=limit, offset=offset,
    )
    total = await _store.count_sessions(
        status=status, model_type=model_type, instrument=instrument,
    )
    # Legacy offset envelope, with an additive ``next_cursor`` so clients can
    # transparently upgrade to cursor pagination on the next request.
    return {
        "items": [_dual_shape_session(s) for s in items],
        "total": total,
        "limit": limit,
        "offset": offset,
        "next_cursor": compute_next_cursor(items, limit, _started_at_id_cursor),
    }


@router.get("/audit-events")
async def list_audit_events(
    limit: int = 100,
    action: Optional[str] = None,
    research_id: Optional[str] = None,
    pipeline_id: Optional[str] = None,
):
    events = await _store.list_audit_events(
        limit=limit,
        action=action,
        research_id=research_id,
        pipeline_id=pipeline_id,
    )
    # Phase 5.3: redact the SHA256 fingerprint suffix in actor_id so the
    # full hash never leaves the service. We keep the prefix so operators
    # can correlate events from the same caller across the audit log,
    # but truncate enough that the full digest cannot be reconstructed.
    for event in events:
        actor_id = event.get("actor_id")
        if (
            isinstance(actor_id, str)
            and actor_id.startswith("token_sha256:")
            and len(actor_id) > len("token_sha256:") + 12
        ):
            prefix = actor_id[: len("token_sha256:") + 8]
            event["actor_id"] = f"{prefix}…"
    return events


@router.get("/research/{research_id}")
async def get_research(research_id: str):
    # ML-63: Check pipelines first if ID starts with pipe_
    if research_id.startswith("pipe_"):
        pipe = await _store.get_pipeline(research_id)
        if pipe:
            payload = dict(pipe)
            payload.setdefault("model_type", "pipeline")
            payload.setdefault("skill_name", "pipeline")
            payload.setdefault("workspace_path", "")
            payload.setdefault("best_iteration", None)
            payload.setdefault("best_metric", None)
            payload.setdefault("resumed_from", None)

            current_phase = pipe.get("current_phase")
            if current_phase in ("direction", "volatility", "rl"):
                session_id = pipe.get(f"{current_phase}_session_id")
                if session_id:
                    session = await _store.get_session(session_id)
                    if session:
                        payload["workspace_path"] = session.get("workspace_path", "")
                        payload["active_phase_session_id"] = session.get("id")
            return _dual_shape_session(payload)
    session = await _store.get_session(research_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return _dual_shape_session(session)


@router.post("/research/{research_id}/stop")
async def stop_research(request: Request, research_id: str):
    ok = await _session_manager.stop_session(research_id)
    if not ok:
        await _audit(
            request,
            action="research.stop",
            outcome="failure",
            research_id=research_id,
            error_message="Session not found or not running",
        )
        raise HTTPException(
            status_code=404, detail="Session not found or not running",
        )
    await _audit(
        request,
        action="research.stop",
        outcome="success",
        research_id=research_id,
    )
    return {"status": "stop_requested", "research_id": research_id}


@router.post("/research/{research_id}/pause")
async def pause_research(request: Request, research_id: str):
    ok = await _session_manager.pause_session(research_id)
    if not ok:
        await _audit(
            request,
            action="research.pause",
            outcome="failure",
            research_id=research_id,
            error_message="Session not found or not running",
        )
        raise HTTPException(
            status_code=404, detail="Session not found or not running",
        )
    await _audit(
        request,
        action="research.pause",
        outcome="success",
        research_id=research_id,
    )
    return {"status": "paused", "research_id": research_id}


@router.post("/research/{research_id}/resume")
async def resume_research(request: Request, research_id: str):
    ok = await _session_manager.resume_session(research_id)
    if not ok:
        await _audit(
            request,
            action="research.resume",
            outcome="failure",
            research_id=research_id,
            error_message="Session not found or not running",
        )
        raise HTTPException(
            status_code=404, detail="Session not found or not running",
        )
    await _audit(
        request,
        action="research.resume",
        outcome="success",
        research_id=research_id,
    )
    return {"status": "running", "research_id": research_id}


class ContinueResearchRequest(BaseModel):
    """Request body for continuing a timed-out/completed session."""
    max_iterations: Optional[int] = Field(default=None, ge=1, le=500)
    max_budget_usd: Optional[float] = Field(default=None, ge=0.1, le=500.0)
    timeout_minutes: Optional[int] = Field(
        default=None, ge=30, le=1440,
        description="Session timeout in minutes",
    )
    focus_hint: Optional[str] = Field(
        default=None, max_length=1000,
        description="Optional hint for what to focus on in the continuation",
    )


class RuntimeResumeRequest(ContinueResearchRequest):
    """Explicit operator action for resuming a restart-recovered session."""

    reason: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Operator reason for resuming the interrupted session.",
    )
    allow_interrupted: bool = Field(
        default=False,
        description="Allow resume from interrupted state when evidence is incomplete.",
    )


@router.post("/research/{research_id}/continue", status_code=201)
async def continue_research(
    request: Request,
    research_id: str,
    req: ContinueResearchRequest = None,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    """Continue a timed-out or completed session as a new chained session.

    Creates a new session that inherits all settings from the parent and
    picks up where it left off — workspace is preserved, no setup/baseline
    re-run.
    """
    if req is None:
        req = ContinueResearchRequest()
    metadata = _continue_metadata(req)
    try:
        session = await _run_idempotent(
            operation="research.continue",
            parent_id=research_id,
            key=idempotency_key,
            request_payload=req.model_dump(),
            call=lambda: _session_manager.continue_session(
                research_id,
                max_iterations=req.max_iterations,
                max_budget_usd=req.max_budget_usd,
                timeout_minutes=req.timeout_minutes,
                focus_hint=req.focus_hint,
            ),
        )
        await _audit(
            request,
            action="research.continue",
            outcome="success",
            research_id=research_id,
            metadata={**metadata, "continued_research_id": session.get("id")},
        )
        return session
    except SkillConfigError as e:
        # ARC-012 P7-010: the parent's skill cannot run (e.g. a pre-skill-era
        # legacy row) — refuse before any row or task exists.
        await _audit(
            request,
            action="research.continue",
            outcome="failure",
            research_id=research_id,
            metadata=metadata,
            error_message=str(e),
        )
        raise HTTPException(status_code=409, detail=str(e)) from e
    except RuntimeError as e:
        await _audit(
            request,
            action="research.continue",
            outcome="failure",
            research_id=research_id,
            metadata=metadata,
            error_message=str(e),
        )
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.post("/research/{research_id}/runtime-resume", status_code=201)
async def runtime_resume_research(
    request: Request,
    research_id: str,
    req: RuntimeResumeRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    """Resume a restart-recovered session only after explicit operator action."""
    metadata = _runtime_resume_metadata(req)
    try:
        session = await _run_idempotent(
            operation="research.runtime_resume",
            parent_id=research_id,
            key=idempotency_key,
            request_payload=req.model_dump(),
            call=lambda: _session_manager.resume_interrupted_session(
                research_id,
                reason=req.reason,
                allow_interrupted=req.allow_interrupted,
                max_iterations=req.max_iterations,
                max_budget_usd=req.max_budget_usd,
                timeout_minutes=req.timeout_minutes,
                focus_hint=req.focus_hint,
            ),
        )
        await _audit(
            request,
            action="research.runtime_resume",
            outcome="success",
            research_id=research_id,
            metadata={**metadata, "continued_research_id": session.get("id")},
        )
        return session
    except SkillConfigError as e:
        # ARC-012 P7-010: same fail-fast rule as continue — the parent's
        # skill cannot run, so no row or task is created.
        await _audit(
            request,
            action="research.runtime_resume",
            outcome="failure",
            research_id=research_id,
            metadata=metadata,
            error_message=str(e),
        )
        raise HTTPException(status_code=409, detail=str(e)) from e
    except RuntimeError as e:
        await _audit(
            request,
            action="research.runtime_resume",
            outcome="failure",
            research_id=research_id,
            metadata=metadata,
            error_message=str(e),
        )
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.delete("/research/{research_id}")
async def delete_research(request: Request, research_id: str):
    if _session_manager.is_running(research_id):
        await _audit(
            request,
            action="research.delete",
            outcome="failure",
            research_id=research_id,
            error_message="Cannot delete a running session — stop it first",
        )
        raise HTTPException(
            status_code=409,
            detail="Cannot delete a running session — stop it first",
        )
    session = await _store.get_session(research_id)
    if session and session.get("pipeline_id"):
        pipeline_id = session["pipeline_id"]
        pipeline = await _store.get_pipeline(pipeline_id)
        if pipeline and pipeline.get("status") == "running":
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Cannot delete a session that belongs to running pipeline "
                    f"{pipeline_id} — stop the pipeline first"
                ),
            )
    ok = await _store.delete_session(research_id)
    if not ok:
        await _audit(
            request,
            action="research.delete",
            outcome="failure",
            research_id=research_id,
            error_message="Session not found",
        )
        raise HTTPException(status_code=404, detail="Session not found")
    await _audit(
        request,
        action="research.delete",
        outcome="success",
        research_id=research_id,
    )
    return {"status": "deleted", "research_id": research_id}


@router.get("/models")
async def list_models():
    """Legacy alias for GET /skills — one entry per installed skill."""
    return [
        {"id": sid, "name": sid, "skill": sid}
        for sid in default_registry.available()
    ]


@router.get("/status")
async def system_status():
    return {
        "active_sessions": _session_manager.active_count,
        "max_concurrent": settings.max_concurrent_sessions,
        "anthropic_model": settings.anthropic_model,
        "default_quick_mode": settings.default_quick_mode,
        "max_iterations": settings.max_iterations,
        "max_budget_usd": settings.max_budget_usd,
        "llm": {
            "mlflow_tracking": settings.mlflow_tracking_uri,
            "mlflow_external": settings.mlflow_external_url,
        },
        "persistence": {
            "db_path": settings.db_path,
            "runs_dir": settings.runs_dir,
            "host_configs_path": settings.host_configs_path,
        },
    }
