"""Bootstrap for code-refactor skill. ABI: JSON stdin -> JSON stdout."""
from __future__ import annotations
import json, sys
from pathlib import Path
_DEFAULT_TARGET = '"""Candidate module — refactor me."""\n\n\nimport os\n\n\ndef compute(items):\n    total = 0\n    for i in items:\n        total = total + i\n    return total\n'
_DEFAULT_TESTS = [{"needle": "def compute", "must_present": True}, {"needle": "import os", "must_present": False}]
def _target_name(payload):
    params = payload.get("skill_params") or {}
    name = params.get("target_file") or "refactor_target.py"
    if (not isinstance(name, str) or not name or "/" in name or "\\" in name
            or ".." in name or not name.endswith(".py")):
        raise ValueError("target_file must be a workspace-relative .py file name")
    return name
def main():
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        json.dump({"error": f"invalid stdin JSON: {exc}"}, sys.stdout); return 2
    ws = Path(payload.get("workspace") or "")
    if not str(ws):
        json.dump({"error": "workspace is required"}, sys.stdout); return 2
    try:
        target = _target_name(payload)
    except ValueError as exc:
        json.dump({"error": str(exc)}, sys.stdout); return 2
    rendered = [target, f"best_{target}", "tests_target.jsonl"]
    if payload.get("mode", "live") == "dry":
        json.dump({"rendered": rendered, "mode": "dry"}, sys.stdout); return 0
    ws.mkdir(parents=True, exist_ok=True)
    (ws / target).write_text(_DEFAULT_TARGET, encoding="utf-8")
    (ws / f"best_{target}").write_text(_DEFAULT_TARGET, encoding="utf-8")
    with open(ws / "tests_target.jsonl", "w", encoding="utf-8") as f:
        for t in _DEFAULT_TESTS:
            f.write(json.dumps(t) + "\n")
    json.dump({"rendered": rendered, "mode": "live", "workspace": str(ws)}, sys.stdout)
    return 0
    return 0
if __name__ == "__main__":
    sys.exit(main())
