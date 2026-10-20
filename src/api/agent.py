"""Scoped research operations for attached agents.

Attached agents authenticate with run-scoped credentials (never the global
operator token) and can only touch their own run. They may submit
candidates, request evaluations, inspect verified results, control their
run's lifecycle, and preview promotion eligibility — they can never declare
their own results verified nor approve production promotion. Storage paths
are derived server-side; submissions are digest-validated, idempotent, and
rate/size-limited.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

from src.core import scoped_credentials as scoped
from src.core.scoped_credentials import (
    PERM_EVALUATE,
    PERM_LIFECYCLE,
    PERM_READ,
    PERM_SUBMIT,
    ScopedAuthError,
    ScopedPrincipal,
)

_router_auth = HTTPBearer(auto_error=False)

router = APIRouter(tags=["attached-agent"])

_store = None
_orchestrator = None
_credential_key: Optional[str] = None

MAX_CANDIDATE_BYTES = 64 * 1024
RATE_LIMIT_PER_MINUTE = 120

_rate_buckets: dict[str, list[float]] = {}


def init(store, orchestrator=None, credential_key: Optional[str] = None):
    """Wire the agent routes to the store and lifecycle controls."""
    global _store, _orchestrator, _credential_key
    _store = store
    _orchestrator = orchestrator
    _credential_key = credential_key


def _key() -> str:
    if _credential_key:
        return _credential_key
    from src.config import secret_value, settings

    fallback = secret_value(settings.autoresearch_api_token) or "dev-key"
    return f"agent-credential:{fallback}"


def _check_rate_limit(token_id: str) -> None:
    now = time.time()
    window = _rate_buckets.setdefault(token_id, [])
    window[:] = [stamp for stamp in window if now - stamp < 60.0]
    if len(window) >= RATE_LIMIT_PER_MINUTE:
        raise HTTPException(
            status_code=429,
            detail="rate limit exceeded for this credential",
        )
    window.append(now)


async def _require_agent(
    request: Request,
    run_id: Optional[str],
    permission: str,
) -> ScopedPrincipal:
    credentials: HTTPAuthorizationCredentials | None = await _router_auth(
        request
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="a run-scoped credential is required",
        )
    try:
        principal = scoped.verify_scoped_credential(
            credentials.credentials,
            key=_key(),
            run_id=run_id,
            required_permissions=(permission,),
        )
    except ScopedAuthError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    _check_rate_limit(principal.token_id)
    return principal


class AgentRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str = Field("create", description="create or attach")
    instrument: str = "EURUSD"
    timeframe: str = "1h"
    tag: str = ""
    max_iterations: int = 3
    max_budget_usd: float = 7.5


@router.post("/agent/runs", status_code=201)
async def create_or_attach_run(
    request: Request, body: AgentRunRequest
) -> dict[str, Any]:
    """Create (or attach to) this credential's run. Paths are server-side."""
    principal = await _require_agent(request, None, PERM_SUBMIT)
    if _store is None:
        raise HTTPException(status_code=503, detail="store is not initialized")
    run_id = principal.run_id
    from src.config import settings

    workspace = f"{settings.runs_dir}/agent/{principal.tenant_id}/{run_id}"
    existing = await _store.get_session(run_id)
    if body.mode == "create" and existing is not None:
        raise HTTPException(
            status_code=409, detail="run already exists; use attach"
        )
    if existing is None:
        await _store.create_session(
            session_id=run_id,
            instrument=body.instrument,
            timeframe=body.timeframe,
            model_type="",
            skill_id="",
            subject_id=body.instrument,
            variant=body.timeframe,
            tag=body.tag,
            quick_mode=True,
            max_iterations=body.max_iterations,
            max_budget_usd=body.max_budget_usd,
            focus_hint=None,
            workspace_path=workspace,
            manifest_json=json.dumps(
                {"research_id": run_id, "agent": principal.subject}
            ),
            manifest_hash=hashlib.sha256(
                run_id.encode("utf-8")
            ).hexdigest(),
        )
    return {
        "run_id": run_id,
        "mode": body.mode,
        "workspace": workspace,
        "subject": principal.subject,
        "permissions": sorted(principal.permissions),
    }


@router.get("/agent/runs/{run_id}/constraints")
async def run_constraints(run_id: str, request: Request) -> dict[str, Any]:
    """The run's declared budgets and the submission limits."""
    await _require_agent(request, run_id, PERM_READ)
    if _store is None:
        raise HTTPException(status_code=503, detail="store is not initialized")
    session = await _store.get_session(run_id)
    if session is None:
        raise HTTPException(status_code=404, detail="run not found")
    return {
        "run_id": run_id,
        "max_iterations": session.get("max_iterations"),
        "max_budget_usd": session.get("max_budget_usd"),
        "max_candidate_bytes": MAX_CANDIDATE_BYTES,
        "rate_limit_per_minute": RATE_LIMIT_PER_MINUTE,
    }


class CandidateSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    digest: str = Field(..., description="sha256 of the submitted content")
    content: str = ""


@router.post("/agent/runs/{run_id}/candidates", status_code=201)
async def submit_candidate(
    run_id: str,
    body: CandidateSubmission,
    request: Request,
    idempotency_key: Optional[str] = Header(
        None, alias="Idempotency-Key"
    ),
) -> dict[str, Any]:
    """Submit one candidate. Digest-validated, idempotent, size-limited."""
    principal = await _require_agent(request, run_id, PERM_SUBMIT)
    if _store is None:
        raise HTTPException(status_code=503, detail="store is not initialized")
    raw = body.content.encode("utf-8")
    if len(raw) > MAX_CANDIDATE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"candidate exceeds {MAX_CANDIDATE_BYTES} bytes",
        )
    actual = hashlib.sha256(raw).hexdigest()
    if body.digest != actual:
        raise HTTPException(
            status_code=422,
            detail="candidate digest does not match the submitted content",
        )
    key = (idempotency_key or "").strip()
    if not key:
        raise HTTPException(
            status_code=400, detail="Idempotency-Key header is required"
        )
    event_id = (
        f"agent-candidate:{run_id}:"
        f"{hashlib.sha256(key.encode()).hexdigest()}"
    )
    existing = next(
        (
            event
            for event in (await _store.list_events(stream_key=run_id))
            if event.get("event_id") == event_id
        ),
        None,
    )
    if existing is not None:
        if existing.get("payload", {}).get("digest") != body.digest:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Idempotency-Key was already used for a different request"
                ),
            )
        return dict(existing.get("payload") or {})
    result = {
        "run_id": run_id,
        "digest": body.digest,
        "bytes": len(raw),
        "authority": "model_proposed",
        "event_id": event_id,
        "subject": principal.subject,
    }
    await _store.append_event(
        event_id=event_id,
        stream_key=run_id,
        event_type="agent.candidate.submitted",
        payload=result,
        producer=f"agent:{principal.subject}",
    )
    return result


@router.post("/agent/runs/{run_id}/evaluations", status_code=202)
async def request_evaluation(run_id: str, request: Request) -> dict[str, Any]:
    """Request evaluation. The trusted channel produces verified results."""
    principal = await _require_agent(request, run_id, PERM_EVALUATE)
    if _store is None:
        raise HTTPException(status_code=503, detail="store is not initialized")
    event_id = f"agent-eval:{run_id}:{int(time.time() * 1000)}"
    await _store.append_event(
        event_id=event_id,
        stream_key=run_id,
        event_type="agent.evaluation.requested",
        payload={"run_id": run_id, "status": "requested"},
        producer=f"agent:{principal.subject}",
    )
    return {"run_id": run_id, "status": "requested", "event_id": event_id}


@router.get("/agent/runs/{run_id}/results")
async def inspect_results(run_id: str, request: Request) -> dict[str, Any]:
    """Inspect results with their recorded authority labels.

    An attached agent can never declare its own results verified: the
    authority label is recorded at ingestion from the channel a result
    arrived on.
    """
    await _require_agent(request, run_id, PERM_READ)
    if _store is None:
        raise HTTPException(status_code=503, detail="store is not initialized")
    rows = await _store.get_iterations(run_id)

    def _authority(row: dict) -> str:
        label = row.get("result_authority")
        if not label:
            try:
                marker = json.loads(row.get("metrics_json") or "{}")
            except Exception:
                marker = {}
            label = marker.get("result_authority")
        return label or "model_proposed"

    return {
        "run_id": run_id,
        "results": [
            {
                "iteration": row.get("iteration"),
                "metrics": row.get("metrics_json"),
                "authority": _authority(row),
            }
            for row in rows
        ],
    }


class LifecycleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = Field(..., description="pause, resume, or stop")


@router.post("/agent/runs/{run_id}/lifecycle")
async def lifecycle_control(
    run_id: str, body: LifecycleRequest, request: Request
) -> dict[str, Any]:
    """Control this run's lifecycle through the bound harness."""
    await _require_agent(request, run_id, PERM_LIFECYCLE)
    if body.action not in {"pause", "resume", "stop"}:
        raise HTTPException(
            status_code=400, detail="action must be pause, resume, or stop"
        )
    if _orchestrator is None:
        raise HTTPException(
            status_code=503, detail="lifecycle control is not initialized"
        )
    handler = {
        "pause": _orchestrator.request_pause,
        "resume": _orchestrator.request_resume,
        "stop": _orchestrator.request_stop,
    }[body.action]
    handler(run_id)
    return {"run_id": run_id, "action": body.action, "status": "accepted"}


@router.get("/agent/runs/{run_id}/promotion-preview")
async def promotion_preview(run_id: str, request: Request) -> dict[str, Any]:
    """Preview promotion eligibility. Approval is never available here."""
    await _require_agent(request, run_id, PERM_READ)
    if _store is None:
        raise HTTPException(status_code=503, detail="store is not initialized")
    from src.core.research_kernel import decide_promotion

    rows = await _store.get_iterations(run_id)
    samples = []
    for row in rows:
        try:
            value = json.loads(row.get("metrics_json") or "{}").get(
                "primary_metric"
            )
        except (json.JSONDecodeError, TypeError):
            value = None
        if value is not None:
            samples.append(float(value))
    decision = decide_promotion(candidate=samples)
    return {
        "run_id": run_id,
        "preview_only": True,
        "eligible": decision.eligible,
        "status": decision.status,
        "reasons": list(decision.reasons),
    }


@router.get("/agent/runs/{run_id}/events")
async def run_events(
    run_id: str,
    request: Request,
    cursor: int = 0,
    limit: int = 100,
) -> dict[str, Any]:
    """Bounded event replay from a cursor (for reconnect)."""
    await _require_agent(request, run_id, PERM_READ)
    if _store is None:
        raise HTTPException(status_code=503, detail="store is not initialized")
    from src.ws.events import poll_events

    batch = max(1, min(limit, 500))
    events = await poll_events(
        _store, stream_key=run_id, cursor=cursor, limit=batch
    )
    next_cursor = (
        int(events[-1].get("sequence") or cursor) if events else int(cursor)
    )
    return {
        "run_id": run_id,
        "events": [
            {
                "event_id": event.get("event_id"),
                "type": event.get("event_type"),
                "sequence": event.get("sequence"),
                "payload": event.get("payload"),
            }
            for event in events
        ],
        "cursor": next_cursor,
    }