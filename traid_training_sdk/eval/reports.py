from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass(frozen=True)
class EvaluationReport:
    model_name: str
    task: str
    dataset_shape: tuple[int, int]
    metrics: dict[str, float]

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"))

    def to_markdown(self) -> str:
        lines = [f"# Evaluation Report", f"- model: {self.model_name}", f"- task: {self.task}", f"- dataset: {self.dataset_shape}"]
        lines.append("\n## Metrics\n")
        for k, v in self.metrics.items():
            lines.append(f"- {k}: {v:.6f}")
        return "\n".join(lines)

    def write(self, path: str | Path, *, fmt: str = "json") -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        content = self.to_json() if fmt == "json" else self.to_markdown()
        with p.open("w", encoding="utf-8") as f:
            f.write(content)
        return p

