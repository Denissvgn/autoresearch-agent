"""Service dependency preflight checks for autoresearch sessions."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

from src.config import settings

SCHEMA_VERSION = "autoresearch_service_preflight.v1"


@dataclass(frozen=True)
class ServicePreflightTarget:
    name: str
    url: str | None
    health_paths: tuple[str, ...] = ("/health",)
    required: bool = True


class ServicePreflightError(RuntimeError):
    """Raised when required service dependencies are not ready."""

    def __init__(self, result: dict[str, Any]) -> None:
        self.result = result
        super().__init__(format_preflight_error(result))


def sanitize_service_url(raw: str | None) -> str:
    """Return a URL safe for manifests by removing credentials and query data."""
    if not raw:
        return ""
    parsed = urlsplit(raw)
    if not parsed.scheme or not parsed.netloc:
        return raw.split("?", 1)[0].split("#", 1)[0]
    host = parsed.hostname or ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    netloc = f"{host}:{parsed.port}" if parsed.port else host
    return urlunsplit((parsed.scheme, netloc, parsed.path.rstrip("/"), "", ""))


def build_service_preflight_targets(settings_obj=settings) -> list[ServicePreflightTarget]:
    """Build the service dependency list from current server settings."""
    targets = [
        ServicePreflightTarget(
            "mlflow_tracking",
            settings_obj.mlflow_tracking_uri,
            health_paths=("/health", "/"),
        ),
        ServicePreflightTarget("mlflow_service", settings_obj.mlflow_service_url),
        ServicePreflightTarget(
            "data_ingest",
            settings_obj.data_ingest_url,
            health_paths=("/readiness", "/health"),
        ),
        ServicePreflightTarget(
            "ensemble_trainer",
            settings_obj.ensemble_trainer_url,
            health_paths=("/health/ready", "/health"),
        ),
        ServicePreflightTarget(
            "rl_trainer",
            settings_obj.rl_trainer_url,
            health_paths=("/health/ready", "/health"),
        ),
        ServicePreflightTarget("feature_service", settings_obj.feature_service_url),
    ]
    if settings_obj.artifact_logging_required:
        targets.append(
            ServicePreflightTarget(
                "artifact_store",
                settings_obj.artifact_store_endpoint_url,
                health_paths=("/minio/health/ready", "/health"),
            )
        )
    return targets


def build_not_run_preflight(settings_obj=settings) -> dict[str, Any]:
    """Build a manifest-safe dependency snapshot when checks have not run."""
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "not_run",
        "checked_at": None,
        "required_ready": False,
        "override_allowed_unready": False,
        "timeout_s": settings_obj.preflight_timeout_s,
        "services": {
            target.name: {
                "url": sanitize_service_url(target.url),
                "required": target.required,
                "status": "not_run",
                "health_paths": list(target.health_paths),
            }
            for target in build_service_preflight_targets(settings_obj)
        },
        "required_failures": [],
    }


async def run_service_preflight(
    *,
    model_type: str,
    settings_obj=settings,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Check required ML dependencies before launching a research session."""
    targets = build_service_preflight_targets(settings_obj)
    base = {
        "schema_version": SCHEMA_VERSION,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "model_type": model_type,
        "required_ready": True,
        "override_allowed_unready": bool(settings_obj.allow_unready_services),
        "timeout_s": settings_obj.preflight_timeout_s,
        "services": {},
        "required_failures": [],
    }

    if not settings_obj.preflight_enabled:
        base.update(
            {
                "status": "skipped",
                "required_ready": False,
                "services": {
                    target.name: {
                        "url": sanitize_service_url(target.url),
                        "required": target.required,
                        "status": "skipped",
                        "health_paths": list(target.health_paths),
                    }
                    for target in targets
                },
            }
        )
        return base

    timeout = httpx.Timeout(
        settings_obj.preflight_timeout_s,
        connect=min(settings_obj.preflight_timeout_s, 2.0),
    )
    owns_client = client is None
    active_client = client or httpx.AsyncClient(timeout=timeout, follow_redirects=True)
    try:
        checks = await asyncio.gather(
            *(_check_target(active_client, target) for target in targets)
        )
    finally:
        if owns_client:
            await active_client.aclose()

    services = {check["name"]: check for check in checks}
    failures = [
        name
        for name, check in services.items()
        if check.get("required") and check.get("status") != "ready"
    ]
    base["services"] = services
    base["required_failures"] = failures
    if failures and settings_obj.allow_unready_services:
        base["status"] = "degraded"
        base["required_ready"] = False
    elif failures:
        base["status"] = "failed"
    else:
        base["status"] = "ready"
    return base


def require_preflight_ready(result: dict[str, Any]) -> None:
    """Raise when a preflight result should block session creation."""
    if result.get("status") == "failed" and result.get("required_ready", True):
        raise ServicePreflightError(result)


def format_preflight_error(result: dict[str, Any]) -> str:
    failures = result.get("required_failures") or []
    services = result.get("services") or {}
    if not failures:
        return "Service preflight failed"
    details = []
    for name in failures:
        check = services.get(name) or {}
        reason = check.get("error") or f"HTTP {check.get('status_code')}"
        url = check.get("url") or "unconfigured"
        details.append(f"{name} at {url}: {reason}")
    return "Service preflight failed: " + "; ".join(details)


async def _check_target(
    client: httpx.AsyncClient,
    target: ServicePreflightTarget,
) -> dict[str, Any]:
    started = time.monotonic()
    url = sanitize_service_url(target.url)
    result = {
        "name": target.name,
        "url": url,
        "required": target.required,
        "status": "failed",
        "health_paths": list(target.health_paths),
        "checked_url": None,
        "status_code": None,
        "latency_ms": None,
        "error": None,
    }
    if not target.url:
        result["error"] = "service URL is not configured"
        return result

    last_error = None
    last_status = None
    for path in target.health_paths:
        checked_url = _join_health_path(target.url, path)
        result["checked_url"] = sanitize_service_url(checked_url)
        try:
            response = await client.get(checked_url)
            last_status = response.status_code
            result["status_code"] = response.status_code
            if 200 <= response.status_code < 400:
                result["status"] = "ready"
                result["error"] = None
                break
            last_error = f"HTTP {response.status_code}"
        except httpx.HTTPError as exc:
            last_error = f"{type(exc).__name__}: {exc}"

    result["latency_ms"] = round((time.monotonic() - started) * 1000, 2)
    if result["status"] != "ready":
        result["status_code"] = last_status
        result["error"] = last_error or "service did not return a ready status"
    return result


def _join_health_path(base_url: str, path: str) -> str:
    base = sanitize_service_url(base_url).rstrip("/")
    if not path or path == "/":
        return f"{base}/"
    return f"{base}/{path.lstrip('/')}"
