"""Persistence helpers for honest TS-FM probability artifacts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

import numpy as np
import pandas as pd

from .tsfm_adapter import TSFM_DIRECTION_OUTPUT_NAME, TsfmAdapterConfig

TSFM_PROBABILITY_ARTIFACT_VERSION = "tsfm_probability_artifact.v1"
TSFM_PROVENANCE_OOF = "oof"
TSFM_PROVENANCE_HOLDOUT = "holdout"
TSFM_PROVENANCE_PRODUCTION_REFIT = "production_refit"
TSFM_PROVENANCE_VALUES = frozenset(
    {
        TSFM_PROVENANCE_OOF,
        TSFM_PROVENANCE_HOLDOUT,
        TSFM_PROVENANCE_PRODUCTION_REFIT,
    }
)

TSFM_PROVENANCE_COLUMN = "tsfm_provenance"
TSFM_IS_OOF_COLUMN = "tsfm_is_oof"
TSFM_PROBABILITY_COLUMN = "tsfm_probability"
TSFM_FOLD_ID_COLUMN = "fold_id"
TSFM_SPLIT_ID_COLUMN = "split_id"
TSFM_SOURCE_MODEL_COLUMN = "source_model_key"

_PROBABILITY_COLUMNS = (
    "oof_proba",
    TSFM_DIRECTION_OUTPUT_NAME,
    TSFM_PROBABILITY_COLUMN,
)


class TsfmProbabilityArtifactError(ValueError):
    """Raised when a TS-FM probability artifact is malformed."""


class NonOofTsfmProbabilityArtifactError(TsfmProbabilityArtifactError):
    """Raised when non-OOF TS-FM probabilities are used for RL training."""


@dataclass
class TsfmProbabilityArtifactMetadata:
    """Serializable metadata for a persisted TS-FM probability artifact."""

    model_family: str
    context_length: int
    horizon: int
    normalization_mode: str
    provenance: str
    forecast_type: Optional[str] = None
    quantile_levels: Optional[tuple[float, ...]] = None
    weight_metadata: dict[str, Any] = field(default_factory=dict)
    license_metadata: dict[str, Any] = field(default_factory=dict)
    runtime_profile: dict[str, Any] = field(default_factory=dict)
    source_adapter_config: dict[str, Any] = field(default_factory=dict)
    split_id: Optional[str] = None
    artifact_version: str = TSFM_PROBABILITY_ARTIFACT_VERSION
    artifact_hash: Optional[str] = None
    created_at_utc: str = field(default_factory=lambda: _utc_now_iso())

    def __post_init__(self) -> None:
        self.provenance = normalize_tsfm_provenance(self.provenance)
        self.context_length = int(self.context_length)
        self.horizon = int(self.horizon)
        if self.context_length < 1:
            raise ValueError("context_length must be >= 1")
        if self.horizon < 1:
            raise ValueError("horizon must be >= 1")
        if self.artifact_version != TSFM_PROBABILITY_ARTIFACT_VERSION:
            raise TsfmProbabilityArtifactError(
                f"Unsupported TS-FM probability artifact version {self.artifact_version!r}; "
                f"expected {TSFM_PROBABILITY_ARTIFACT_VERSION!r}"
            )
        if self.quantile_levels is not None:
            self.quantile_levels = tuple(float(q) for q in self.quantile_levels)

    @classmethod
    def from_adapter_config(
        cls,
        config: TsfmAdapterConfig | Mapping[str, Any],
        *,
        provenance: str,
        weight_metadata: Optional[Mapping[str, Any]] = None,
        license_metadata: Optional[Mapping[str, Any]] = None,
        runtime_profile: Optional[Mapping[str, Any]] = None,
        split_id: Optional[str] = None,
    ) -> "TsfmProbabilityArtifactMetadata":
        if isinstance(config, TsfmAdapterConfig):
            adapter_config = config
        elif hasattr(config, "to_dict"):
            adapter_config = TsfmAdapterConfig.from_dict(config.to_dict())
        else:
            adapter_config = TsfmAdapterConfig.from_dict(config)
        return cls(
            model_family=adapter_config.model_family,
            forecast_type=adapter_config.forecast_type,
            context_length=adapter_config.context_length,
            horizon=adapter_config.horizon,
            normalization_mode=adapter_config.normalization_mode,
            quantile_levels=adapter_config.quantile_levels,
            provenance=provenance,
            weight_metadata=dict(weight_metadata or {}),
            license_metadata=dict(license_metadata or {}),
            runtime_profile=dict(runtime_profile or {}),
            source_adapter_config=adapter_config.to_dict(),
            split_id=split_id,
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.quantile_levels is not None:
            payload["quantile_levels"] = list(self.quantile_levels)
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TsfmProbabilityArtifactMetadata":
        payload = dict(data)
        if payload.get("quantile_levels") is not None:
            payload["quantile_levels"] = tuple(float(q) for q in payload["quantile_levels"])
        return cls(**payload)

    def with_artifact_hash(self, artifact_hash: str) -> "TsfmProbabilityArtifactMetadata":
        return replace(self, artifact_hash=artifact_hash)


@dataclass
class TsfmProbabilityArtifactBundle:
    """Loaded TS-FM probability artifact with its frame and metadata."""

    frame: pd.DataFrame
    metadata: dict[str, Any]
    probability_column: str


def normalize_tsfm_provenance(value: Any) -> str:
    provenance = str(value).strip().lower().replace("-", "_")
    if provenance not in TSFM_PROVENANCE_VALUES:
        raise TsfmProbabilityArtifactError(
            "TS-FM probability provenance must be one of "
            f"{sorted(TSFM_PROVENANCE_VALUES)}; got {value!r}"
        )
    return provenance


def build_tsfm_probability_artifact_frame(
    *,
    probabilities: Sequence[float] | np.ndarray | pd.Series,
    provenance: str | Sequence[str],
    index: Optional[Sequence[Any] | pd.Index] = None,
    fold_ids: Optional[Sequence[Any]] = None,
    split_id: Optional[str] = None,
    source_model_key: Optional[str] = None,
    timestamps: Optional[Sequence[Any]] = None,
) -> pd.DataFrame:
    """Build a row-provenanced TS-FM probability artifact frame."""

    proba = _coerce_probability_array(probabilities)
    provenance_values = _normalize_provenance_values(provenance, len(proba))
    artifact_index = pd.Index(index) if index is not None else pd.RangeIndex(len(proba))
    if len(artifact_index) != len(proba):
        raise ValueError("index length must match probabilities length")

    frame = pd.DataFrame(
        {
            TSFM_DIRECTION_OUTPUT_NAME: proba,
            TSFM_PROBABILITY_COLUMN: proba,
            TSFM_PROVENANCE_COLUMN: provenance_values,
            TSFM_IS_OOF_COLUMN: provenance_values == TSFM_PROVENANCE_OOF,
            TSFM_SPLIT_ID_COLUMN: split_id,
            TSFM_SOURCE_MODEL_COLUMN: source_model_key,
        },
        index=artifact_index,
    )
    if fold_ids is not None:
        if len(fold_ids) != len(proba):
            raise ValueError("fold_ids length must match probabilities length")
        frame[TSFM_FOLD_ID_COLUMN] = list(fold_ids)
    else:
        frame[TSFM_FOLD_ID_COLUMN] = pd.NA
    if timestamps is not None:
        if len(timestamps) != len(proba):
            raise ValueError("timestamps length must match probabilities length")
        frame["timestamp"] = list(timestamps)

    if bool(frame[TSFM_IS_OOF_COLUMN].all()):
        frame.insert(0, "oof_proba", proba)

    validate_tsfm_probability_frame(frame)
    return frame


def write_tsfm_probability_artifact(
    frame: pd.DataFrame,
    output_path: str | Path,
    metadata: TsfmProbabilityArtifactMetadata | Mapping[str, Any],
) -> Path:
    """Persist a TS-FM probability parquet plus a JSON metadata sidecar."""

    validate_tsfm_probability_frame(frame)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path)
    artifact_hash = _sha256_file(path)

    metadata_obj = (
        metadata
        if isinstance(metadata, TsfmProbabilityArtifactMetadata)
        else TsfmProbabilityArtifactMetadata.from_dict(metadata)
    )
    metadata_payload = metadata_obj.with_artifact_hash(artifact_hash).to_dict()
    metadata_payload["row_count"] = int(len(frame))
    metadata_payload["provenance_counts"] = {
        str(key): int(value)
        for key, value in frame[TSFM_PROVENANCE_COLUMN].value_counts().to_dict().items()
    }
    metadata_payload["probability_column"] = select_tsfm_probability_column(frame)

    sidecar = tsfm_metadata_sidecar_path(path)
    sidecar.write_text(json.dumps(metadata_payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def read_tsfm_probability_artifact(
    artifact_path: str | Path,
    *,
    require_oof_for_training: bool = False,
) -> TsfmProbabilityArtifactBundle:
    """Load and validate a persisted TS-FM probability artifact."""

    path = Path(artifact_path)
    frame = pd.read_parquet(path)
    validate_tsfm_probability_frame(
        frame,
        require_oof_for_training=require_oof_for_training,
        artifact_path=path,
    )
    sidecar = tsfm_metadata_sidecar_path(path)
    metadata = json.loads(sidecar.read_text(encoding="utf-8")) if sidecar.exists() else {}
    return TsfmProbabilityArtifactBundle(
        frame=frame,
        metadata=metadata,
        probability_column=select_tsfm_probability_column(frame),
    )


def load_oof_probability_series(artifact_path: str | Path) -> pd.Series:
    """Load a legacy or TS-FM OOF parquet for RL enrichment."""

    path = Path(artifact_path)
    frame = pd.read_parquet(path)
    if is_tsfm_probability_frame(frame):
        validate_tsfm_probability_frame(
            frame,
            require_oof_for_training=True,
            artifact_path=path,
        )
        column = select_tsfm_probability_column(frame)
    else:
        if "oof_proba" not in frame.columns:
            raise TsfmProbabilityArtifactError(
                f"OOF parquet {path} is missing required 'oof_proba' column"
            )
        column = "oof_proba"
    return frame[column].astype(float)


def validate_tsfm_probability_frame(
    frame: pd.DataFrame,
    *,
    require_oof_for_training: bool = False,
    artifact_path: Optional[str | Path] = None,
) -> None:
    """Validate row-level TS-FM probability provenance."""

    if TSFM_PROVENANCE_COLUMN not in frame.columns:
        raise TsfmProbabilityArtifactError(
            "TS-FM probability artifact is missing required row-level "
            f"{TSFM_PROVENANCE_COLUMN!r}"
        )
    if TSFM_IS_OOF_COLUMN not in frame.columns:
        raise TsfmProbabilityArtifactError(
            "TS-FM probability artifact is missing required row-level "
            f"{TSFM_IS_OOF_COLUMN!r}"
        )

    provenance = frame[TSFM_PROVENANCE_COLUMN].map(normalize_tsfm_provenance)
    expected_is_oof = provenance.eq(TSFM_PROVENANCE_OOF)
    actual_is_oof = frame[TSFM_IS_OOF_COLUMN].astype(bool)
    if not expected_is_oof.equals(actual_is_oof):
        raise TsfmProbabilityArtifactError(
            f"{TSFM_IS_OOF_COLUMN!r} must match {TSFM_PROVENANCE_COLUMN!r} == "
            f"{TSFM_PROVENANCE_OOF!r}"
        )

    column = select_tsfm_probability_column(frame)
    proba = pd.to_numeric(frame[column], errors="coerce")
    if proba.isna().any() or not np.isfinite(proba.to_numpy(dtype=np.float64)).all():
        raise TsfmProbabilityArtifactError(
            f"TS-FM probability column {column!r} contains non-finite values"
        )
    if ((proba < 0.0) | (proba > 1.0)).any():
        raise TsfmProbabilityArtifactError(
            f"TS-FM probability column {column!r} must stay within [0, 1]"
        )

    if require_oof_for_training and not expected_is_oof.all():
        counts = provenance.value_counts().to_dict()
        location = f" at {artifact_path}" if artifact_path is not None else ""
        raise NonOofTsfmProbabilityArtifactError(
            "RL enrichment training requires TS-FM OOF probabilities"
            f"{location}; found non-OOF provenance counts {counts}"
        )


def is_tsfm_probability_frame(frame: pd.DataFrame) -> bool:
    return (
        TSFM_PROVENANCE_COLUMN in frame.columns
        or TSFM_IS_OOF_COLUMN in frame.columns
        or TSFM_PROBABILITY_COLUMN in frame.columns
    )


def select_tsfm_probability_column(frame: pd.DataFrame) -> str:
    for column in _PROBABILITY_COLUMNS:
        if column in frame.columns:
            return column
    raise TsfmProbabilityArtifactError(
        "TS-FM probability artifact is missing a probability column; expected one of "
        f"{list(_PROBABILITY_COLUMNS)}"
    )


def tsfm_metadata_sidecar_path(artifact_path: str | Path) -> Path:
    path = Path(artifact_path)
    return path.with_suffix(path.suffix + ".metadata.json")


def _coerce_probability_array(values: Sequence[float] | np.ndarray | pd.Series) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError("probabilities must be a 1D array")
    if not np.isfinite(arr).all():
        raise ValueError("probabilities must be finite")
    if np.any((arr < 0.0) | (arr > 1.0)):
        raise ValueError("probabilities must stay within [0, 1]")
    return arr


def _normalize_provenance_values(
    provenance: str | Sequence[str],
    n_rows: int,
) -> np.ndarray:
    if isinstance(provenance, str):
        values = [provenance] * n_rows
    else:
        values = list(provenance)
    if len(values) != n_rows:
        raise ValueError("provenance length must match probabilities length")
    return np.asarray([normalize_tsfm_provenance(value) for value in values], dtype=object)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = [
    "NonOofTsfmProbabilityArtifactError",
    "TSFM_IS_OOF_COLUMN",
    "TSFM_PROBABILITY_ARTIFACT_VERSION",
    "TSFM_PROBABILITY_COLUMN",
    "TSFM_PROVENANCE_COLUMN",
    "TSFM_PROVENANCE_HOLDOUT",
    "TSFM_PROVENANCE_OOF",
    "TSFM_PROVENANCE_PRODUCTION_REFIT",
    "TSFM_PROVENANCE_VALUES",
    "TsfmProbabilityArtifactBundle",
    "TsfmProbabilityArtifactError",
    "TsfmProbabilityArtifactMetadata",
    "build_tsfm_probability_artifact_frame",
    "is_tsfm_probability_frame",
    "load_oof_probability_series",
    "normalize_tsfm_provenance",
    "read_tsfm_probability_artifact",
    "select_tsfm_probability_column",
    "tsfm_metadata_sidecar_path",
    "validate_tsfm_probability_frame",
    "write_tsfm_probability_artifact",
]
