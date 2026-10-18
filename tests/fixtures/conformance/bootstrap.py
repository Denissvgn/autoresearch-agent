"""Bootstrap for the conformance probe skill. ABI: JSON stdin -> JSON stdout."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main():
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        json.dump({"error": f"invalid stdin JSON: {exc}"}, sys.stdout)
        return 2
    ws = Path(payload.get("workspace") or "")
    if not str(ws):
        json.dump({"error": "workspace is required"}, sys.stdout)
        return 2
    params = payload.get("skill_params") or {}
    name = params.get("input_file") or "sample_input.txt"
    if not isinstance(name, str) or not name or "/" in name or "\\" in name or ".." in name:
        json.dump({"error": "input_file must be a workspace-relative file name"}, sys.stdout)
        return 2
    if payload.get("mode", "live") == "dry":
        json.dump({"rendered": [name, "candidate.yaml"], "mode": "dry"},
                  sys.stdout)
        return 0
    ws.mkdir(parents=True, exist_ok=True)
    (ws / name).write_text("conformance input\n", encoding="utf-8")
    (ws / "candidate.yaml").write_text("metric: 0.0\n", encoding="utf-8")
    json.dump({"rendered": [name, "candidate.yaml"], "mode": "live",
               "workspace": str(ws)}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
