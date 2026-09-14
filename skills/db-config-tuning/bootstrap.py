"""Bootstrap for db-config-tuning. ABI: JSON stdin -> JSON stdout."""
from __future__ import annotations
import json, sys
from pathlib import Path
_DEFAULT = "shared_buffers_mb: 128\nwork_mem_mb: 4\neffective_cache_size_mb: 512\nmax_connections: 100\n"
_RENDERED = ["db_config.yaml", "best_db_config.yaml"]
def main():
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        json.dump({"error": str(exc)}, sys.stdout); return 2
    ws = Path(payload.get("workspace") or "")
    if not str(ws):
        json.dump({"error": "workspace required"}, sys.stdout); return 2
    if payload.get("mode", "live") == "dry":
        json.dump({"rendered": _RENDERED, "mode": "dry"}, sys.stdout); return 0
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "db_config.yaml").write_text(_DEFAULT, encoding="utf-8")
    (ws / "best_db_config.yaml").write_text(_DEFAULT, encoding="utf-8")
    json.dump({"rendered": _RENDERED, "mode": "live", "workspace": str(ws)}, sys.stdout)
    return 0
if __name__ == "__main__":
    sys.exit(main())
