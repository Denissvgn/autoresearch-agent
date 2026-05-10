# research Module

**Path:** `src/api/research.py`

## Description

Research session management endpoints.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `collections.abc` | `Awaitable`, `Callable` |
| `fastapi` | `APIRouter`, `Depends`, `Header`, `HTTPException`, `Query`, `Request` |
| `glob` | `glob` |
| `hashlib` | `hashlib` |
| `json` | `json` |
| `os` | `os` |
| `pydantic` | `BaseModel`, `Field`, `field_validator` |
| `src.api.audit` | `record_api_audit_event` |
| `src.api.auth` | `require_api_auth` |
| `src.config` | `settings` |
| `typing` | `Any`, `Dict`, `Optional` |
| `yaml` | `yaml` |

## Classes

| Class | Line | Bases | Description |
|-------|------|-------|-------------|
| [StartResearchRequest](../entities/research_StartResearchRequest.md) | 189 | `BaseModel` | — |
| [ContinueResearchRequest](../entities/ContinueResearchRequest.md) | 502 | `BaseModel` | ML-62: Request body for continuing a timed-out/completed session. |
| [RuntimeResumeRequest](../entities/RuntimeResumeRequest.md) | 516 | `ContinueResearchRequest` | Explicit operator action for resuming a restart-recovered session. |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `init` | `(session_manager, store)` | — | — |
| `_start_metadata` | `(req: 'StartResearchRequest') -> dict[str, Any]` | — | — |
| `_continue_metadata` | `(req: 'ContinueResearchRequest') -> dict[str, Any]` | — | — |
| `_runtime_resume_metadata` | `(req: 'RuntimeResumeRequest') -> dict[str, Any]` | — | — |
| `_audit` | `*(async)* (request: Request)` | — | — |
| `_validate_phase_budgets` | `(value: Optional[Dict[str, int]]) -> Optional[Dict[str, int]]` | — | — |
| `_json_hash` | `(payload: Any) -> str` | — | — |
| `_run_idempotent` | `*(async)* () -> Dict[str, Any]` | — | — |
| `start_research` | `*(async)* (request: Request, req: StartResearchRequest)` | `@router.post('/research/start', status_code=201)` | — |
| `list_research` | `*(async)* (status: Optional[str] = None, model_type: Optional[str] = None, instrument: Optional[str] = None, limit: int = Query(...), offset: int = Query(...))` | `@router.get('/research')` | Phase 5.1: paginated session listing. |
| `list_audit_events` | `*(async)* (limit: int = 100, action: Optional[str] = None, research_id: Optional[str] = None, pipeline_id: Optional[str] = None)` | `@router.get('/audit-events')` | — |
| `get_research` | `*(async)* (research_id: str)` | `@router.get('/research/{research_id}')` | — |
| `stop_research` | `*(async)* (request: Request, research_id: str)` | `@router.post('/research/{research_id}/stop')` | — |
| `pause_research` | `*(async)* (request: Request, research_id: str)` | `@router.post('/research/{research_id}/pause')` | — |
| `resume_research` | `*(async)* (request: Request, research_id: str)` | `@router.post('/research/{research_id}/resume')` | — |
| `continue_research` | `*(async)* (request: Request, research_id: str, req: ContinueResearchRequest = None, idempotency_key: str | None = Header(...))` | `@router.post('/research/{research_id}/continue', status_code=201)` | ML-62: Continue a timed-out or completed session as a new chained session. |
| `runtime_resume_research` | `*(async)* (request: Request, research_id: str, req: RuntimeResumeRequest, idempotency_key: str | None = Header(...))` | `@router.post('/research/{research_id}/runtime-resume', status_code=201)` | Resume a restart-recovered session only after explicit operator action. |
| `delete_research` | `*(async)* (request: Request, research_id: str)` | `@router.delete('/research/{research_id}')` | — |
| `list_instruments` | `*(async)* ()` | `@router.get('/instruments')` | List available instruments from configs/instrument_configs/*.yaml. |
| `list_models` | `*(async)* ()` | `@router.get('/models')` | — |
| `list_pipelines` | `*(async)* (status: Optional[str] = None, instrument: Optional[str] = None, limit: int = Query(...), offset: int = Query(...))` | `@router.get('/pipelines')` | Phase 5.1: paginated pipeline listing. |
| `system_status` | `*(async)* ()` | `@router.get('/status')` | — |
