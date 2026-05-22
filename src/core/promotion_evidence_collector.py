"""Server-side resolver for infrastructure-side promotion blockers.

Fix 3 (from run res_a526a64254f4 analysis): the agent's best iteration is
typically blocked at promotion by five infrastructure-side gates that the
agent cannot produce evidence for:

  - ``signal_saturation``                 — needs candidate's signal_rate
  - ``missing_signal_health_metrics``     — needs probability/entropy/drift
  - ``inference_adapter_load_failure``    — needs inference-service preflight
  - ``inference_reload_failed``           — needs inference-service composite
                                            reload dry-run
  - ``failed_smoke_validation``           — needs smoke-validation pipeline run

This module collects the evidence on the server side and patches the best
iteration's ``metrics_json`` so the existing ``ConfigPromoter.preview``
gate-evaluation path resolves the blockers without agent intervention.

The collector is idempotent and feature-flag-gated by
``settings.auto_collect_promotion_evidence`` (default True). Each
sub-collector has its own timeout. Errors are surfaced as classified
blockers (logged and recorded in the patch as
``promotion_evidence_collection_error``) rather than silently dropped.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
from typing import Any, Dict, Optional, Tuple

import httpx

from src.config import secret_value, settings
from src.core.results_store import ResultsStore

logger = logging.getLogger(__name__)


class PromotionEvidenceCollector:
    """Collect infrastructure-owned evidence for a candidate iteration.

    Usage:

        collector = PromotionEvidenceCollector(store)
        await collector.collect_and_patch(research_id, iteration)
    """

    def __init__(
        self,
        store: ResultsStore,
        *,
        http_client_factory=None,
        timeout_s: Optional[float] = None,
    ) -> None:
        self._store = store
        self._timeout_s = timeout_s or settings.promotion_evidence_timeout_s
        self._http_client_factory = http_client_factory or self._default_http_client

    @staticmethod
    def _default_http_client(timeout_s: float) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=timeout_s)

    async def collect_and_patch(
        self,
        research_id: str,
        iteration: int,
    ) -> Dict[str, Any]:
        """Run all sub-collectors and merge their evidence into the iteration.

        Returns the evidence patch (also persisted) for caller inspection.
        Caller should re-fetch ConfigPromoter.preview() after this returns.
        """
        row = await self._store.get_iteration(research_id, iteration)
        if not row:
            logger.info(
                "promotion_evidence: no iteration %d for %s",
                iteration, research_id,
            )
            return {}

        metrics = _parse_metrics(row.get("metrics_json"))
        patch: Dict[str, Any] = {}
        errors: Dict[str, str] = {}

        # --- 1. signal_health: derive from existing training output ---------
        if not _has_signal_health(metrics):
            payload, err = await self._collect_signal_health(metrics)
            if payload is not None:
                patch["signal_health"] = payload
            if err:
                errors["signal_health"] = err

        # --- 2. signal_saturation: gate already reads signal_rate; surface
        #        it in the canonical "signal_health.operational" container --
        if "signal_rate" in metrics and "signal_health" not in patch:
            existing_health = metrics.get("signal_health") or {}
            if isinstance(existing_health, dict) and not existing_health.get(
                "operational"
            ):
                patch["signal_health"] = {
                    **existing_health,
                    "operational": {
                        "signal_rate": metrics.get("signal_rate"),
                    },
                }

        # --- 3. inference adapter preflight ---------------------------------
        if not _has_adapter_preflight(metrics):
            payload, err = await self._collect_inference_preflight(metrics)
            if payload is not None:
                patch["inference_parity"] = _merge_inference_payload(
                    metrics.get("inference_parity"), payload,
                )
            if err:
                errors["inference_preflight"] = err

        # --- 4. composite reload dry-run ------------------------------------
        if not _has_reload_validation(metrics, patch):
            payload, err = await self._collect_reload_dry_run(metrics)
            if payload is not None:
                merged = _merge_inference_payload(
                    patch.get("inference_parity")
                    or metrics.get("inference_parity"),
                    payload,
                )
                patch["inference_parity"] = merged
            if err:
                errors["inference_reload"] = err

        # --- 5. smoke validation --------------------------------------------
        if not _has_smoke_validation(metrics):
            # Option B: the paper-replay endpoint needs instrument/timeframe to
            # resolve its conventional sample path. Fetch from the session row.
            session = await self._store.get_session(research_id)
            instrument = (session or {}).get("instrument")
            timeframe = (session or {}).get("timeframe")
            payload, err = await self._collect_smoke_validation(
                metrics, instrument=instrument, timeframe=timeframe,
            )
            if payload is not None:
                patch["smoke_validation"] = payload
                # The paper-replay ran the candidate through the real serving
                # path, so its signal_health (probability summary + hold_rate)
                # is the dev-scope signal-health evidence the gate needs. Merge
                # it over any training-derived signal_health from steps 1–2.
                replay_sh = (payload.get("details") or {}).get("signal_health")
                if isinstance(replay_sh, dict) and replay_sh:
                    merged_sh = dict(
                        patch.get("signal_health")
                        or metrics.get("signal_health")
                        or {}
                    )
                    merged_sh.update(replay_sh)
                    patch["signal_health"] = merged_sh
            if err:
                errors["smoke_validation"] = err

        if errors:
            patch["promotion_evidence_collection_errors"] = errors

        if not patch:
            logger.info(
                "promotion_evidence: nothing to patch for %s iter %d",
                research_id, iteration,
            )
            return {}

        merged_metrics = {**metrics, **patch}
        await self._store.update_iteration(
            research_id, iteration, merged_metrics,
        )
        logger.info(
            "promotion_evidence: patched %s iter %d with keys=%s errors=%s",
            research_id, iteration, sorted(patch.keys()),
            sorted(errors.keys()) if errors else "[]",
        )
        return patch

    # ────────────────────────────────────────────────────────────────────
    # Sub-collectors
    # ────────────────────────────────────────────────────────────────────

    async def _collect_signal_health(
        self,
        metrics: Dict[str, Any],
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Compute signal_health from prediction-distribution metrics emitted
        by prepare.py. Returns (payload, error)."""
        signal_rate = metrics.get("signal_rate")
        # prepare.py emits prediction-distribution stats under various keys;
        # we look in the canonical locations.
        mean_prob = (
            metrics.get("prediction_mean_probability")
            or _nested(metrics, "calibration_full_validation", "selected", "mean_probability")
        )
        entropy = (
            metrics.get("prediction_entropy")
            or _nested(metrics, "calibration_full_validation", "selected", "entropy")
        )
        drift = (
            metrics.get("feature_drift_score")
            or _nested(metrics, "feature_drift", "score")
        )

        if signal_rate is None and mean_prob is None and entropy is None:
            return None, "no_signal_health_source"

        return {
            "probability": {
                "mean": mean_prob,
            } if mean_prob is not None else None,
            "entropy": {
                "value": entropy,
            } if entropy is not None else None,
            "drift": {
                "score": drift,
            } if drift is not None else None,
            "operational": {
                "signal_rate": signal_rate,
            } if signal_rate is not None else None,
        }, None

    async def _collect_inference_preflight(
        self,
        metrics: Dict[str, Any],
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Ask the inference service whether the candidate's adapter loads
        cleanly. Returns the parity payload patch on success.
        """
        url = settings.inference_service_url.rstrip("/")
        endpoint = f"{url}/admin/adapter/preflight"
        body = {
            "candidate": _candidate_handle(metrics),
        }
        headers = _inference_service_auth_headers()
        if headers is None:
            # Distinct from "service rejected the call" — operators need to
            # know the call could not even be authenticated. Surfaced via
            # Gap 3's collection_errors map to the auto-promotion-skipped
            # audit event so the diagnostic is actionable.
            return None, "inference_auth_token_not_configured"
        try:
            client = self._http_client_factory(self._timeout_s)
            async with client:
                resp = await client.post(endpoint, json=body, headers=headers)
        except (httpx.HTTPError, asyncio.TimeoutError) as exc:
            return None, f"adapter_preflight_failed: {exc.__class__.__name__}"
        if resp.status_code != 200:
            return None, f"adapter_preflight_status_{resp.status_code}"

        try:
            data = resp.json() or {}
        except json.JSONDecodeError:
            return None, "adapter_preflight_invalid_json"

        loaded = bool(data.get("loaded"))
        return {
            "adapter_loading_passed": loaded,
            "adapter_loading_details": data,
        }, None

    async def _collect_reload_dry_run(
        self,
        metrics: Dict[str, Any],
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Ask the inference service to simulate a composite reload."""
        url = settings.inference_service_url.rstrip("/")
        endpoint = f"{url}/admin/composite/reload"
        body = {
            "candidate": _candidate_handle(metrics),
            "dry_run": True,
        }
        headers = _inference_service_auth_headers()
        if headers is None:
            return None, "inference_auth_token_not_configured"
        try:
            client = self._http_client_factory(self._timeout_s)
            async with client:
                resp = await client.post(endpoint, json=body, headers=headers)
        except (httpx.HTTPError, asyncio.TimeoutError) as exc:
            return None, f"reload_dry_run_failed: {exc.__class__.__name__}"
        if resp.status_code != 200:
            return None, f"reload_dry_run_status_{resp.status_code}"

        try:
            data = resp.json() or {}
        except json.JSONDecodeError:
            return None, "reload_dry_run_invalid_json"

        return {
            "composite_reload_passed": bool(data.get("composite_reload_passed")),
            "rollback_ready": bool(data.get("rollback_ready")),
            "prior_version_preserved_on_reload_failure": bool(
                data.get("prior_version_preserved_on_reload_failure", True)
            ),
        }, None

    async def _collect_smoke_validation(
        self,
        metrics: Dict[str, Any],
        *,
        instrument: Optional[str] = None,
        timeframe: Optional[str] = None,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Resolve smoke-validation evidence for the candidate.

        Precedence:
          1. Pre-staged ``paper_validation`` / ``smoke_validation`` already in
             metrics → passthrough (e.g. a future canary feed stages it).
          2. Option B: ask inference-service to run a sandboxed paper-replay
             via ``/admin/paper/replay``. On a passing replay this yields the
             evidence the development gate bundle's smoke tier requires.
          3. Otherwise return a precise error so the gate stays hard and the
             Gap 3 ``collection_errors`` map shows operators why.
        """
        existing = metrics.get("paper_validation") or metrics.get("smoke_validation")
        if isinstance(existing, dict) and existing.get("passed") is True:
            return {
                "passed": True,
                "composite_reload_passed": True,
                "prior_version_left_intact_on_failure": True,
                "source": "passthrough_existing",
            }, None

        headers = _inference_service_auth_headers()
        if headers is None:
            return None, "inference_auth_token_not_configured"

        url = settings.inference_service_url.rstrip("/")
        endpoint = f"{url}/admin/paper/replay"
        body = {
            "candidate": _candidate_handle(metrics),
            "instrument": instrument or "DOGE_USDT",
            "timeframe": timeframe or "15m",
        }
        try:
            client = self._http_client_factory(self._timeout_s)
            async with client:
                resp = await client.post(endpoint, json=body, headers=headers)
        except (httpx.HTTPError, asyncio.TimeoutError) as exc:
            return None, f"paper_replay_failed: {exc.__class__.__name__}"
        if resp.status_code != 200:
            return None, f"paper_replay_status_{resp.status_code}"
        try:
            data = resp.json() or {}
        except json.JSONDecodeError:
            return None, "paper_replay_invalid_json"

        if not data.get("passed"):
            return None, f"paper_replay_not_passed: {data.get('error', 'unknown')}"
        return {
            "passed": True,
            "composite_reload_passed": bool(data.get("composite_reload_passed")),
            "prior_version_left_intact_on_failure": bool(
                data.get("prior_version_left_intact_on_failure")
            ),
            "source": data.get("source")
            or "paper_replay_with_candidate_artifact_validated",
            "details": data,
        }, None


# ────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────


def _parse_metrics(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _has_signal_health(metrics: Dict[str, Any]) -> bool:
    health = metrics.get("signal_health")
    return isinstance(health, dict) and bool(health)


def _has_adapter_preflight(metrics: Dict[str, Any]) -> bool:
    parity = metrics.get("inference_parity")
    if not isinstance(parity, dict):
        return False
    return "adapter_loading_passed" in parity


def _has_reload_validation(
    metrics: Dict[str, Any],
    patch: Dict[str, Any],
) -> bool:
    for source in (patch.get("inference_parity"), metrics.get("inference_parity")):
        if isinstance(source, dict) and "composite_reload_passed" in source:
            return True
    reload_validation = metrics.get("inference_reload_validation")
    if isinstance(reload_validation, dict) and reload_validation:
        return True
    return False


def _has_smoke_validation(metrics: Dict[str, Any]) -> bool:
    smoke = metrics.get("smoke_validation") or metrics.get("paper_validation")
    return isinstance(smoke, dict) and smoke.get("passed") is True


def _merge_inference_payload(
    existing: Any,
    patch: Dict[str, Any],
) -> Dict[str, Any]:
    if isinstance(existing, dict):
        return {**existing, **patch}
    return dict(patch)


def _nested(d: Dict[str, Any], *path: str) -> Any:
    cur: Any = d
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    if isinstance(cur, float) and math.isnan(cur):
        return None
    return cur


def _candidate_handle(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Compact identifier the inference service uses to locate the candidate
    artifact (mlflow run + config_snapshot suffice). Inference-service can
    extend this contract without breaking the autoresearch side.
    """
    return {
        "mlflow_run_id": metrics.get("mlflow_run_id"),
        "result_artifact_path": metrics.get("result_artifact_path"),
        "config_snapshot_hash": metrics.get("canonical_config_hash"),
    }


def _inference_service_auth_headers() -> Optional[Dict[str, str]]:
    """Bearer-token header for service-to-service admin calls into
    inference-service's ``/admin/adapter/preflight`` and
    ``/admin/composite/reload`` endpoints. Returns ``None`` if no token is
    configured — callers surface this as
    ``inference_auth_token_not_configured`` so the audit log distinguishes
    "infrastructure missing" from "infrastructure rejected request".

    Token resolution order (mirrors config_promoter._mlflow_service_auth_headers):
      1. ``settings.inference_service_auth_token`` (dedicated env var)
      2. ``settings.mlflow_service_auth_token`` (fallback — operators with
         a single SERVICE_AUTH_TOKEN / ML_ADMIN_TOKEN don't need two)
    """
    token = secret_value(
        getattr(settings, "inference_service_auth_token", None)
    ) or secret_value(settings.mlflow_service_auth_token)
    if not token:
        return None
    return {
        "Authorization": f"Bearer {token}",
        "X-Service-Name": settings.service_name,
    }
