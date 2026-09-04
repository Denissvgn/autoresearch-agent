from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from ..instruments.naming import composite_alias
from .inference_compat import derive_models_uri, validate_composite_manifest


@dataclass(frozen=True)
class ComponentRef:
    model_name: str
    version: int
    fs_uri: Optional[str] = None

    @classmethod
    def from_any(cls, value: Any) -> "ComponentRef":
        if isinstance(value, ComponentRef):
            return value
        if isinstance(value, Mapping):
            if "model_name" in value and "version" in value:
                fs_uri = value.get("fs_uri")
                return cls(
                    model_name=str(value["model_name"]),
                    version=int(value["version"]),
                    fs_uri=str(fs_uri) if fs_uri is not None else None,
                )
        if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
            items = list(value)
            if len(items) >= 2:
                return cls(model_name=str(items[0]), version=int(items[1]))
        raise ValueError("Component reference must provide model_name and version")


@dataclass(frozen=True)
class CompositeManifest:
    instrument: str
    timeframe: str
    initial_balance: int
    components: dict[str, ComponentRef]  # keys: direction, volatility, rl
    min_confidence: Optional[float] = None
    backtest_metrics: Optional[dict[str, Any]] = None
    risk_metrics: Optional[dict[str, Any]] = None
    lineage_ids: Optional[list[str]] = None

    def to_payload(self, *, include_optional: bool = True, include_uris: bool = False) -> dict[str, Any]:
        comps = {
            key: {"model_name": ref.model_name, "version": int(ref.version)}
            for key, ref in sorted(self.components.items())
        }
        if include_uris:
            for key, item in comps.items():
                item["model_uri"] = derive_models_uri(item["model_name"], item["version"])
                ref = self.components[key]
                if ref.fs_uri:
                    item["fs_uri"] = ref.fs_uri

        payload: dict[str, Any] = {
            "instrument": self.instrument,
            "timeframe": self.timeframe,
            "initial_balance": int(self.initial_balance),
            "components": comps,
        }
        if include_optional:
            if self.min_confidence is not None:
                payload["min_confidence"] = self.min_confidence
            if self.backtest_metrics is not None:
                payload["backtest_metrics"] = self.backtest_metrics
            if self.risk_metrics is not None:
                payload["risk_metrics"] = self.risk_metrics
            if self.lineage_ids is not None:
                payload["lineage_ids"] = list(self.lineage_ids)
        return payload

    def to_json(self, *, include_optional: bool = True, include_uris: bool = False) -> str:
        payload = self.to_payload(include_optional=include_optional, include_uris=include_uris)
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)

    def stable_hash(self) -> str:
        canonical = self.to_json(include_optional=True, include_uris=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def filename(self) -> str:
        alias = composite_alias(self.instrument, self.timeframe, self.initial_balance)
        return f"{alias}__{self.stable_hash()[:10]}.json"


def assemble_composite_manifest(
    *,
    instrument: str,
    timeframe: str,
    initial_balance: int,
    components: Mapping[str, Any],
    min_confidence: Optional[float] = None,
    backtest_metrics: Optional[dict[str, Any]] = None,
    risk_metrics: Optional[dict[str, Any]] = None,
    lineage_ids: Optional[Iterable[str]] = None,
) -> CompositeManifest:
    comp_refs = {key: ComponentRef.from_any(value) for key, value in components.items()}
    manifest = CompositeManifest(
        instrument=instrument,
        timeframe=timeframe,
        initial_balance=int(initial_balance),
        components=comp_refs,
        min_confidence=min_confidence,
        backtest_metrics=backtest_metrics,
        risk_metrics=risk_metrics,
        lineage_ids=list(lineage_ids) if lineage_ids is not None else None,
    )
    validate_composite_manifest(manifest.to_payload(include_optional=True, include_uris=False))
    return manifest


def persist_composite_manifest(
    manifest: CompositeManifest,
    *,
    directory: str | Path,
    filename: Optional[str] = None,
    include_uris: bool = True,
) -> Path:
    directory_path = Path(directory)
    directory_path.mkdir(parents=True, exist_ok=True)
    file_name = filename or manifest.filename()
    target = directory_path / file_name
    payload = manifest.to_payload(include_optional=True, include_uris=include_uris)
    validate_composite_manifest(payload)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return target


__all__ = [
    "ComponentRef",
    "CompositeManifest",
    "assemble_composite_manifest",
    "persist_composite_manifest",
]
