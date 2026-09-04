from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any


def write_text(path: str | Path, content: str) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def write_bytes(path: str | Path, content: bytes) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    return p


def write_json(path: str | Path, data: Any) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return p


def copy_file(src: str | Path, dst: str | Path) -> Path:
    dst_p = Path(dst)
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst_p)
    return dst_p


def run_dir(runs_root: str | Path, run_id: str) -> Path:
    return Path(runs_root) / run_id


def artifacts_dir(runs_root: str | Path, run_id: str) -> Path:
    return run_dir(runs_root, run_id) / "artifacts"


def save_evaluation_report(report, path: str | Path, *, fmt: str = "json") -> Path:
    return report.write(path, fmt=fmt)

