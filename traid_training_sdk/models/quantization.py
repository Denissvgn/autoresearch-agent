from __future__ import annotations

import io
from typing import Any, TYPE_CHECKING

from ..core.errors import NotAvailableSDK, TrainingError
from ..core.logging import get_logger

try:  # pragma: no cover - optional dependency
    import torch
except ImportError:  # pragma: no cover - torch may be missing
    torch = None  # type: ignore[assignment]

if TYPE_CHECKING:  # pragma: no cover - typing helpers only
    import torch as torch_typing

    TorchModule = torch_typing.nn.Module
    TorchDType = torch_typing.dtype
else:
    TorchModule = Any
    TorchDType = Any

_LOGGER = get_logger("traid_training_sdk.quantization")


def _estimate_state_dict_size_bytes(module: TorchModule) -> int:
    buffer = io.BytesIO()
    torch.save(module.state_dict(), buffer)
    return buffer.getbuffer().nbytes


def quantize_model(
    model: TorchModule,
    dtype: TorchDType = torch.qint8 if torch is not None else None,
) -> TorchModule:
    """Apply dynamic quantization to a PyTorch model.

    Args:
        model: The initialized ``torch.nn.Module`` to quantize.
        dtype: Target dtype for quantized weights. Defaults to ``torch.qint8`` when available.

    Returns:
        The quantized model in evaluation mode.

    Raises:
        NotAvailableSDK: If PyTorch or ``torch.quantization.quantize_dynamic`` is unavailable.
        TypeError: If ``model`` is not a ``torch.nn.Module`` instance.
        TrainingError: If quantization fails for any reason.

    Example:
        >>> import torch
        >>> from traid_training_sdk.models.quantization import quantize_model
        >>> mlp = torch.nn.Sequential(torch.nn.Linear(16, 32), torch.nn.ReLU(), torch.nn.Linear(32, 1))
        >>> q_mlp = quantize_model(mlp)
        >>> q_mlp.eval()
    """

    if torch is None:
        raise NotAvailableSDK("PyTorch is required for quantization. Install with: pip install torch")
    if not hasattr(torch, "quantization") or not hasattr(torch.quantization, "quantize_dynamic"):
        raise NotAvailableSDK("torch.quantization.quantize_dynamic is required for model quantization")
    if not isinstance(model, torch.nn.Module):
        raise TypeError("quantize_model expects a torch.nn.Module instance")

    target_dtype = dtype or torch.qint8
    target_layers = {torch.nn.Linear, torch.nn.LSTM}

    original_training = model.training
    model.eval()
    try:
        original_size = _estimate_state_dict_size_bytes(model)
        quantized = torch.quantization.quantize_dynamic(
            model,
            target_layers,
            dtype=target_dtype,
        )
        quantized.eval()
        quantized_size = _estimate_state_dict_size_bytes(quantized)
        compression_ratio = (quantized_size / original_size) if original_size else 0.0
        _LOGGER.info(
            {
                "event": "quantization.stats",
                "original_bytes": original_size,
                "quantized_bytes": quantized_size,
                "compression_ratio": compression_ratio,
                "dtype": str(target_dtype),
            }
        )
        return quantized
    except Exception as exc:  # pragma: no cover - torch error paths vary
        raise TrainingError(f"Dynamic quantization failed: {exc}") from exc
    finally:
        model.train(original_training)
