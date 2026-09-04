"""
Enhanced structured logging for ML training services.
Provides secure, standardized logging with secret masking and MLflow integration.
"""

from datetime import datetime
import json
import logging
import os
import sys
from typing import Any

try:
    from .secret_masking import get_config_summary, mask_sensitive_dict
except ImportError:
    # Fallback for standalone execution
    from secret_masking import get_config_summary, mask_sensitive_dict


class MLServiceJsonFormatter(logging.Formatter):
    """JSON formatter for ML services with secret masking."""
    
    def __init__(self, service_name: str, mask_secrets: bool = True):
        super().__init__()
        self.service_name = service_name
        self.mask_secrets = mask_secrets
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON with secret masking."""
        log_data = {
            "timestamp": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S.%fZ"),
            "level": record.levelname,
            "service": self.service_name,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields with secret masking
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in logging.LogRecord(
                name="", level=0, pathname="", lineno=0, msg="", args=(), exc_info=None
            ).__dict__:
                extra_fields[key] = value
        
        if extra_fields:
            if self.mask_secrets:
                extra_fields = mask_sensitive_dict(extra_fields)
            log_data["extra"] = extra_fields
        
        return json.dumps(log_data, ensure_ascii=False, default=str)


class MLServiceLogger:
    """Enhanced logger for ML services with configuration logging capabilities."""
    
    def __init__(
        self, 
        service_name: str, 
        level: str | int = logging.INFO,
        json_logs: bool | None = None,
        mask_secrets: bool = True
    ):
        self.service_name = service_name
        self.mask_secrets = mask_secrets
        self.logger = logging.getLogger(service_name)
        
        # Determine if we should use JSON logs (default to True in production)
        if json_logs is None:
            json_logs = os.getenv("ENVIRONMENT", "development") == "production"
        
        # Configure logging
        self._setup_logging(level, json_logs)
    
    def _setup_logging(self, level: str | int, json_logs: bool):
        """Setup logging configuration."""
        # Clear existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Create handler
        handler = logging.StreamHandler(sys.stdout)
        
        if json_logs:
            formatter = MLServiceJsonFormatter(self.service_name, self.mask_secrets)
        else:
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(level if isinstance(level, int) else getattr(logging, str(level).upper()))
        
        # Prevent propagation to root logger
        self.logger.propagate = False
        
        # Configure root logger so that child modules using
        # logging.getLogger(__name__) (e.g. training, environment, utils)
        # also have their output routed to stdout instead of being dropped.
        root = logging.getLogger()
        if not root.handlers:
            root_handler = logging.StreamHandler(sys.stdout)
            root_handler.setFormatter(formatter)
            root.addHandler(root_handler)
            root.setLevel(level if isinstance(level, int) else getattr(logging, str(level).upper()))
        
        # Tame noisy libraries
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    def log_service_startup(self, config: Any, vault_status: dict[str, Any]):
        """Log service startup with configuration summary."""
        startup_info = {
            "event": "service_startup",
            "service": self.service_name,
            "environment": getattr(config, "environment", "unknown"),
            "version": getattr(config, "version", "unknown"),
            "vault_status": vault_status,
            "config_summary": get_config_summary(config, include_sensitive=False)
        }
        
        self.logger.info(
            f"{self.service_name} service starting up",
            extra=startup_info
        )
    
    def log_config_loaded(self, config: Any, vault_keys_count: int = 0):
        """Log configuration loading with non-sensitive summary."""
        config_info = {
            "event": "config_loaded",
            "vault_keys_loaded": vault_keys_count,
            "config_summary": get_config_summary(config, include_sensitive=False)
        }
        
        self.logger.info(
            f"Configuration loaded successfully for {self.service_name}",
            extra=config_info
        )
    
    def log_mlflow_run_start(self, run_id: str, experiment_name: str, tags: dict[str, str] | None = None):
        """Log MLflow run start with tags."""
        mlflow_info = {
            "event": "mlflow_run_start",
            "run_id": run_id,
            "experiment_name": experiment_name,
            "tags": tags or {}
        }
        
        self.logger.info(
            f"MLflow run started: {run_id}",
            extra=mlflow_info
        )
    
    def log_training_metrics(self, metrics: dict[str, float], step: int | None = None):
        """Log training metrics."""
        metrics_info = {
            "event": "training_metrics",
            "metrics": metrics,
            "step": step
        }
        
        self.logger.info(
            "Training metrics recorded",
            extra=metrics_info
        )
    
    def log_model_evaluation(self, model_name: str, metrics: dict[str, float]):
        """Log model evaluation results."""
        eval_info = {
            "event": "model_evaluation",
            "model_name": model_name,
            "evaluation_metrics": metrics
        }
        
        self.logger.info(
            f"Model evaluation completed for {model_name}",
            extra=eval_info
        )
    
    def log_health_check(self, status: str, checks: dict[str, Any] | None = None):
        """Log health check results."""
        health_info = {
            "event": "health_check",
            "status": status,
            "checks": checks or {}
        }
        
        self.logger.debug(
            f"Health check: {status}",
            extra=health_info
        )
    
    def log_error(self, error: Exception, context: dict[str, Any] | None = None):
        """Log error with context."""
        error_info = {
            "event": "error",
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context or {}
        }
        
        if self.mask_secrets and context:
            error_info["context"] = mask_sensitive_dict(context)
        
        self.logger.error(
            f"Error occurred: {error}",
            extra=error_info,
            exc_info=True
        )


def setup_ml_service_logging(
    service_name: str,
    level: str | int = logging.INFO,
    json_logs: bool | None = None,
    mask_secrets: bool = True
) -> MLServiceLogger:
    """
    Setup structured logging for ML services.
    
    Args:
        service_name: Name of the ML service
        level: Logging level
        json_logs: Whether to use JSON formatting (auto-detect if None)
        mask_secrets: Whether to mask sensitive information
        
    Returns:
        Configured MLServiceLogger instance
    """
    return MLServiceLogger(
        service_name=service_name,
        level=level,
        json_logs=json_logs,
        mask_secrets=mask_secrets
    )


def log_service_health(
    logger: MLServiceLogger, 
    service_name: str, 
    status: str,
    config_status: dict[str, Any] | None = None,
    additional_checks: dict[str, Any] | None = None
):
    """
    Log comprehensive service health information.
    
    Args:
        logger: MLServiceLogger instance
        service_name: Name of the service
        status: Health status (healthy/unhealthy)
        config_status: Configuration status information
        additional_checks: Additional health checks
    """
    health_data = {
        "service": service_name,
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
        "config_status": config_status or {},
        "additional_checks": additional_checks or {}
    }
    
    logger.log_health_check(status, health_data)
