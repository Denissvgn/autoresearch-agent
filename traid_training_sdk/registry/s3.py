from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from ..core.errors import NotAvailableSDK
from ..models.base import joblib_save
from .base import ModelRegistry, RegistryEntry


@dataclass
class S3Registry(ModelRegistry):
    bucket: str
    prefix: str = ""
    region: str | None = None
    endpoint_url: str | None = None

    def __post_init__(self) -> None:
        try:
            import boto3  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency guard
            raise NotAvailableSDK("Install traid-training-sdk[s3] to use the S3 registry") from exc
        self._boto3 = boto3
        self._client = boto3.client("s3", region_name=self.region, endpoint_url=self.endpoint_url)

    def _base_prefix(self, name: str) -> str:
        cleaned = self.prefix.strip("/")
        if cleaned:
            return f"{cleaned}/{name}"
        return name

    def _version_prefix(self, name: str, version: int) -> str:
        return f"{self._base_prefix(name)}/{version}"

    def _existing_versions(self, name: str) -> list[int]:
        prefix = self._base_prefix(name)
        token = None
        versions: set[int] = set()
        while True:
            kwargs = {"Bucket": self.bucket, "Prefix": prefix}
            if token:
                kwargs["ContinuationToken"] = token
            resp = self._client.list_objects_v2(**kwargs)
            for obj in resp.get("Contents", []):
                key = obj.get("Key", "")
                suffix = key[len(prefix) :].lstrip("/")
                if not suffix:
                    continue
                part = suffix.split("/", 1)[0]
                if part.isdigit():
                    versions.add(int(part))
            if not resp.get("IsTruncated"):
                break
            token = resp.get("NextContinuationToken")
            if not token:
                break
        return sorted(versions)

    def register(self, *, model, name: str, metadata: dict | None = None) -> int:
        versions = self._existing_versions(name)
        version = versions[-1] + 1 if versions else 1
        prefix = self._version_prefix(name, version)
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            model_path = tmp_path / "model.bin"
            if hasattr(model, "save"):
                model.save(str(model_path))
            else:  # pragma: no cover - fallback for plain estimators
                joblib_save(model, model_path)
            meta = metadata or {}
            meta_path = tmp_path / "meta.json"
            meta_path.write_text(json.dumps(meta, separators=(",", ":")), encoding="utf-8")
            self._client.upload_file(str(model_path), self.bucket, f"{prefix}/model.bin")
            self._client.upload_file(str(meta_path), self.bucket, f"{prefix}/meta.json")
        return version

    def list(self, name: str) -> Sequence[int]:
        return self._existing_versions(name)

    def get(self, name: str, version: int) -> RegistryEntry:
        prefix = self._version_prefix(name, version)
        path = f"s3://{self.bucket}/{prefix}/model.bin"
        meta_path = f"s3://{self.bucket}/{prefix}/meta.json"
        return RegistryEntry(name=name, version=version, path=path, meta_path=meta_path)

    def promote(self, name: str, version: int, stage: str) -> None:
        stage_key = f"{self._base_prefix(name)}/stages/{stage}.json"
        body = json.dumps({"version": version}).encode("utf-8")
        self._client.put_object(Bucket=self.bucket, Key=stage_key, Body=body)

