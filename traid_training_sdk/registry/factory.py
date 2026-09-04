from __future__ import annotations

from ..core.config import IORegistryConfig
from ..core.errors import ConfigurationError
from ..security.secrets import SecretManager
from .base import ModelRegistry
from .filesystem import FilesystemRegistry
from .s3 import S3Registry


def load_registry(config: IORegistryConfig, secrets: SecretManager) -> ModelRegistry:
    backend = (config.backend or "filesystem").lower()
    if backend in {"filesystem", "fs"}:
        root = config.root or "model-registry"
        return FilesystemRegistry(root)
    if backend == "s3":
        if not config.bucket:
            raise ConfigurationError("S3 registry backend requires a bucket")
        prefix = config.prefix or ""
        region = config.region
        endpoint = config.endpoint_url
        return S3Registry(bucket=config.bucket, prefix=prefix, region=region, endpoint_url=endpoint)
    raise ConfigurationError(f"Unsupported registry backend: {config.backend}")
