from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, TYPE_CHECKING

import numpy as np

from ..core.errors import NotAvailableSDK
from .base import joblib_load, joblib_save

try:  # pragma: no cover - optional dependency
    import torch
except ImportError:  # pragma: no cover - torch may be missing
    torch = None  # type: ignore[assignment]

if TYPE_CHECKING:
    from torch import Tensor


@dataclass
class UnifiedInstrumentModel:
    model: Any  # underlying protocol-compatible model
    features: list[str] | None
    instrument: str
    timeframe: str
    objective: str
    metrics: dict[str, float]

    def predict(self, df) -> np.ndarray:
        if hasattr(self.model, "feature_gen"):
            return self.model.predict(df)
        if not self.features:
            raise ValueError("Unified model missing feature definitions for non-pipeline model")
        X = df[self.features].to_numpy()
        return self.model.predict(X)

    def save(self, path: str | Path) -> None:
        payload = {
            "features": list(self.features or []),
            "instrument": self.instrument,
            "timeframe": self.timeframe,
            "objective": self.objective,
            "metrics": self.metrics,
            "model": self.model,
        }
        joblib_save(payload, path)

    @classmethod
    def load(cls, path: str | Path) -> "UnifiedInstrumentModel":
        payload = joblib_load(path)
        return cls(
            model=payload["model"],
            features=list(payload.get("features") or []),
            instrument=str(payload["instrument"]),
            timeframe=str(payload["timeframe"]),
            objective=str(payload["objective"]),
            metrics=dict(payload["metrics"]),
        )

    def _unwrap_torch_module(self, candidate: Any) -> Any:
        """Recursively unwrap nested models until a torch.nn.Module is found."""
        current = candidate
        seen_ids: set[int] = set()

        while True:
            if torch is not None and isinstance(current, torch.nn.Module):
                return current

            current_id = id(current)
            if current_id in seen_ids:
                return current
            seen_ids.add(current_id)

            for attr in ("_model", "model"):
                if hasattr(current, attr):
                    nested = getattr(current, attr)
                    if nested is not None and nested is not current:
                        current = nested
                        break
            else:
                return current

    def export_onnx(self, path: str | Path, input_sample: "Tensor") -> Path:
        """Export the wrapped PyTorch model to an ONNX graph with dynamic batch axes.

        This method preserves the module's training/eval state after export completes.

        **Note**: ONNX export is officially supported for **unquantized PyTorch models only**.
        When ``SdkConfig.enable_quantization`` is set, saved models may be quantized and
        ``export_onnx()`` can fail depending on PyTorch and ONNX versions. Quantized modules
        (e.g., from ``torch.nn.quantized``) may not be compatible with ONNX export.

        Args:
            path: Destination path for the exported ONNX model.
            input_sample: Representative torch.Tensor that matches the model's expected input shape.

        Raises:
            NotAvailableSDK: If PyTorch or torch.onnx is not available, or if the model contains
                quantized layers that are incompatible with ONNX export.
            ValueError: If the wrapped model is not backed by a torch.nn.Module instance.
            TypeError: If ``input_sample`` is not a torch.Tensor.

        Example:
            >>> unified_model.export_onnx("artifacts/model.onnx", torch.randn(1, 16))
        """

        if torch is None:
            raise NotAvailableSDK("PyTorch is required for ONNX export. Install with: pip install torch")
        if not hasattr(torch, "onnx") or not hasattr(torch.onnx, "export"):
            raise NotAvailableSDK("torch.onnx.export is required for ONNX export support")
        if not isinstance(input_sample, torch.Tensor):
            raise TypeError("input_sample must be a torch.Tensor")

        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        module = self._unwrap_torch_module(self.model)
        if not isinstance(module, torch.nn.Module):
            raise ValueError(
                "UnifiedInstrumentModel.export_onnx is only supported for PyTorch models"
            )

        # Check for quantized modules
        quantized_modules = [
            m for m in module.modules()
            if m.__class__.__module__.startswith("torch.nn.quantized")
        ]
        if quantized_modules:
            raise NotAvailableSDK(
                "ONNX export is not supported for quantized PyTorch models. "
                "To export to ONNX, train the model with SdkConfig.enable_quantization=False. "
                "Quantized modules are designed for inference optimization and may not be "
                "compatible with ONNX export depending on PyTorch and ONNX versions."
            )

        original_training = module.training
        module.eval()

        try:
            torch.onnx.export(
                module,
                input_sample,
                str(output_path),
                export_params=True,
                opset_version=14,
                do_constant_folding=True,
                input_names=["input"],
                output_names=["output"],
                dynamic_axes={
                    "input": {0: "batch_size"},
                    "output": {0: "batch_size"},
                },
            )
        finally:
            module.train(original_training)

        return output_path

