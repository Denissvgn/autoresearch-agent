from __future__ import annotations

import json
import logging
from typing import Any, Mapping, Optional


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        payload: dict[str, Any] = {
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        # Known extra fields
        for key in ("run_id", "experiment", "component", "step"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"))


def get_logger(name: str, *, level: str = "INFO", json_mode: bool = False) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(logger.level)
        handler.setFormatter(
            _JsonFormatter() if json_mode else logging.Formatter("%(levelname)s %(name)s: %(message)s")
        )
        logger.addHandler(handler)
    return logger


def get_contextual_logger(
    name: str,
    *,
    level: str = "INFO",
    json_mode: bool = False,
    run_id: Optional[str] = None,
    experiment: Optional[str] = None,
    component: Optional[str] = None,
) -> logging.LoggerAdapter:
    base = get_logger(name, level=level, json_mode=json_mode)
    extra = {k: v for k, v in {
        "run_id": run_id,
        "experiment": experiment,
        "component": component,
    }.items() if v is not None}
    return logging.LoggerAdapter(base, extra)
