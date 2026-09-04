from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from ..core.errors import NotAvailableSDK, RegistryError


def _require_mlflow():
    try:
        import mlflow  # type: ignore  # noqa: F401
    except Exception as exc:  # pragma: no cover
        raise NotAvailableSDK("MLflow is not available. Install mlflow or configure tracking URI.") from exc


def register_model(
    *,
    model_uri: str,
    model_name: str,
    tags: Optional[dict[str, str]] = None,
    await_registration: bool = True,
) -> int:
    """
    Register a model in MLflow Model Registry.

    model_uri can be a runs URI (runs:/<run_id>/artifact_path) or a local path. For local
    paths, the caller should have already logged the artifact into a run and pass the runs URI.
    """
    _require_mlflow()
    import mlflow  # type: ignore

    try:
        res = mlflow.register_model(model_uri=model_uri, name=model_name, tags=tags or {})
        if await_registration:
            client = mlflow.tracking.MlflowClient()
            client.transition_model_version_stage(model_name, res.version, stage="Staging")
        return int(res.version)
    except Exception as exc:  # pragma: no cover
        raise RegistryError(f"Failed to register model {model_name} from {model_uri}: {exc}") from exc


def get_model_version(model_name: str, version: int) -> dict[str, Any]:
    _require_mlflow()
    import mlflow  # type: ignore

    client = mlflow.tracking.MlflowClient()
    mv = client.get_model_version(model_name, str(version))
    return {"name": mv.name, "version": int(mv.version), "current_stage": mv.current_stage}


def get_latest(model_name: str, stage: str = "Production") -> Optional[dict[str, Any]]:
    _require_mlflow()
    import mlflow  # type: ignore

    client = mlflow.tracking.MlflowClient()
    mvs = client.get_latest_versions(model_name, stages=[stage])
    if not mvs:
        return None
    mv = mvs[0]
    return {"name": mv.name, "version": int(mv.version), "current_stage": mv.current_stage}


def transition_stage(model_name: str, version: int, stage: str) -> None:
    _require_mlflow()
    import mlflow  # type: ignore

    client = mlflow.tracking.MlflowClient()
    client.transition_model_version_stage(model_name, str(version), stage=stage)


def log_artifact_to_run(run_id: str, local_path: str | Path, artifact_subdir: Optional[str] = None) -> str:
    _require_mlflow()
    import mlflow  # type: ignore

    client = mlflow.tracking.MlflowClient()
    local = Path(local_path)
    client.log_artifact(run_id, str(local), artifact_path=artifact_subdir)
    parts = [p for p in [artifact_subdir, local.name] if p]
    artifact_rel = "/".join(parts)
    return f"runs:/{run_id}/{artifact_rel}" if artifact_rel else f"runs:/{run_id}"


def set_model_version_tags(model_name: str, version: int, tags: dict[str, str]) -> None:
    if not tags:
        return
    _require_mlflow()
    import mlflow  # type: ignore

    client = mlflow.tracking.MlflowClient()
    for key, value in tags.items():
        client.set_model_version_tag(model_name, str(version), key, str(value))

