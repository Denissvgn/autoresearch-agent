"""Bootstrap for code-refactor skill. ABI: JSON stdin -> JSON stdout."""
from __future__ import annotations
import json, sys
from pathlib import Path
_DEFAULT_TARGET = '"""Candidate module — refactor me."""\n\n\nimport os\n\n\ndef compute(items):\n    total = 0\n    for i in items:\n        total = total + i\n    return total\n'
_RENDERED = ["refactor_target.py", "best_refactor_target.py", "tests_target.jsonl"]
_DEFAULT_TESTS = [{"needle": "def compute", "must_present": True}, {"needle": "import os", "must_present": False}]
def main():
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        json.dump({"error": f"invalid stdin JSON: {exc}"}, sys.stdout); return 2
    ws = Path(payload.get("workspace") or "")
    if not str(ws):
        json.dump({"error": "workspace is required"}, sys.stdout); return 2
    if payload.get("mode", "live") == "dry":
        json.dump({"rendered": _RENDERED, "mode": "dry"}, sys.stdout); return 0
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "refactor_target.py").write_text(_DEFAULT_TARGET, encoding="utf-8")
    (ws / "best_refactor_target.py").write_text(_DEFAULT_TARGET, encoding="utf-8")
    with open(ws / "tests_target.jsonl", "w", encoding="utf-8") as f:
        for t in _DEFAULT_TESTS:
            f.write(json.dumps(t) + "\n")
    json.dump({"rendered": _RENDERED, "mode": "live", "workspace": str(ws)}, sys.stdout)
    return 0
if __name__ == "__main__":
    sys.exit(main())
