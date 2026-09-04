"""
Device selection logic for ML services.

Implements REQ-002-ML:
- Auto-detect GPU availability
- Respect GPU_ENABLED and GPU_DEVICE environment variables
- Provide consistent device selection across services
"""
import os
import logging
from typing import Any

logger = logging.getLogger(__name__)

def get_device() -> Any:
    """
    Get the appropriate torch device based on environment configuration.
    
    Returns:
        torch.device: The selected device (cpu or cuda:N)
    """
    try:
        import torch
    except ImportError:
        return "cpu"

    # Check if GPU is explicitly enabled via env var (default: false)
    gpu_enabled = str(os.getenv("GPU_ENABLED", "false")).lower() in ("true", "1", "yes", "on")
    
    if gpu_enabled and torch.cuda.is_available():
        # Check for specific device request
        device_env = os.getenv("GPU_DEVICE")
        
        if device_env:
            # Handle "cuda:0" format
            if device_env.startswith("cuda"):
                device = torch.device(device_env)
            # Handle "0" format
            elif device_env.isdigit():
                device = torch.device(f"cuda:{device_env}")
            else:
                logger.warning(f"Invalid GPU_DEVICE format: {device_env}. Falling back to cuda.")
                device = torch.device("cuda")
        else:
            device = torch.device("cuda")
            
        logger.info(f"ML Service using GPU: {device}")
        return device
        
    if gpu_enabled and not torch.cuda.is_available():
        logger.warning("GPU_ENABLED=true but no CUDA device available. Falling back to CPU.")

    return torch.device("cpu")
