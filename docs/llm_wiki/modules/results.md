# results Module

**Path:** `src/api/results.py`

## Description

Experiment results query endpoints.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `fastapi` | `APIRouter`, `Depends`, `HTTPException`, `Query` |
| `fastapi.responses` | `FileResponse`, `Response` |
| `json` | `json` |
| `os` | `os` |
| `pathlib` | `Path` |
| `src.api.auth` | `require_api_auth` |
| `src.core.consistency_validator` | `build_consistency_report`, `parse_consistency_report` |
| `src.core.log_writer` | `AgentLogWriter`, `_format_entry` |
| `src.core.research_state` | `build_research_state` |
| `typing` | `Any`, `Dict`, `List`, `Optional` |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `init` | `(store)` | — | — |
| `_decode_pipeline_payload` | `(pipeline: Dict[str, Any]) -> Dict[str, Any]` | — | — |
| `_enrich_iteration` | `(row: Dict[str, Any], model_type: str) -> Dict[str, Any]` | — | Add parsed metrics, MLflow link, and secondary metrics to an iteration dict. |
| `_enrich_iterations` | `(rows: List[Dict[str, Any]], model_type: str) -> List[Dict[str, Any]]` | — | — |
| `_rl_economic_replay` | `(metrics: Dict[str, Any]) -> Dict[str, Any]` | — | — |
| `_rl_economic_replay_summary` | `(metrics: Dict[str, Any], attempt_snapshot: Dict[str, Any]) -> Optional[Dict[str, Any]]` | — | — |
| `_feature_readiness_metrics` | `(metrics: Dict[str, Any]) -> Dict[str, Any]` | — | — |
| `_first_number` | `() -> Optional[float]` | — | — |
| `_resolve_result_context` | `*(async)* (research_id: str) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], List[Dict[str, Any]]]` | — | Resolve a research or pipeline ID to the most relevant session context. |
| `_collect_log_entries` | `(sessions: List[Dict[str, Any]]) -> List[Dict[str, Any]]` | — | Read and flatten agent log entries across one or more sessions. |
| `_build_log_text` | `(entries: List[Dict[str, Any]]) -> str` | — | — |
| `get_results` | `*(async)* (research_id: str)` | `@router.get('/research/{research_id}/results')` | Full experiment history for a research session. |
| `get_iterations` | `*(async)* (research_id: str)` | `@router.get('/research/{research_id}/iterations')` | All iterations with metrics and config snapshots. |
| `get_iteration` | `*(async)* (research_id: str, iteration_num: int)` | `@router.get('/research/{research_id}/iterations/{iteration_num}')` | Single iteration detail. |
| `get_best_iteration` | `*(async)* (research_id: str)` | `@router.get('/research/{research_id}/best')` | Best iteration (highest primary metric with gates passed). |
| `get_agent_log` | `*(async)* (research_id: str, after: Optional[int] = Query(...), format: Optional[str] = Query(...))` | `@router.get('/research/{research_id}/agent-log')` | Agent conversation log — full Claude transcript captured during execution. |
| `get_hpo_studies` | `*(async)* (research_id: str)` | `@router.get('/research/{research_id}/hpo-studies')` | HPO study results for a research session (ML-59). |
| `get_research_state` | `*(async)* (research_id: str)` | `@router.get('/research/{research_id}/state')` | Operator-facing session state, reconstructable from DB rows only. |
| `_collect_audit_events` | `*(async)* () -> List[Dict[str, Any]]` | — | — |
| `_resolve_workspace_file` | `(workspace: str, filename: str) -> Path` | — | Resolve a file within the workspace, guarding against path traversal. |
| `download_config` | `*(async)* (research_id: str)` | `@router.get('/research/{research_id}/download/config')` | Download the best_train.yaml config as a YAML file. |
| `download_agent_log` | `*(async)* (research_id: str)` | `@router.get('/research/{research_id}/download/agent-log')` | Download the agent_log.jsonl transcript as a file. |
| `download_results` | `*(async)* (research_id: str)` | `@router.get('/research/{research_id}/download/results')` | Download the full session + iterations as a JSON file. |
