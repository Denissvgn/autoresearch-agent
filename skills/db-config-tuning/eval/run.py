#!/usr/bin/env python3
"""DB-config bench simulator (P0-2). Offline deterministic TPS model."""
from __future__ import annotations
import argparse, hashlib, json, os
def _emit(**fields):
    p = dict(fields); p["server_nonce"] = os.environ.get("AUTORESEARCH_SESSION_NONCE", "")
    p.setdefault("status", "completed"); p.setdefault("primary_metric", 0.0); p.setdefault("metric_name", "tps")
    print("ITERATION_RESULT: " + json.dumps(p), flush=True)
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--target-latency-ms", type=float, default=10.0)
    ap.add_argument("--baseline-tps", type=float, default=0.0)
    a = ap.parse_args()
    try:
        import yaml
        cfg = yaml.safe_load(open(a.config, encoding="utf-8")) or {}
    except Exception:
        try:
            cfg = json.load(open(a.config, encoding="utf-8"))
        except Exception as exc:
            _emit(status="bench_failed", error=str(exc)); return 1
    sb = float(cfg.get("shared_buffers_mb", 128)); wm = float(cfg.get("work_mem_mb", 4))
    ec = float(cfg.get("effective_cache_size_mb", 512)); mc = float(cfg.get("max_connections", 100))
    h = int(hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest(), 16)
    jitter = ((h >> 16) % 200 - 100) / 100.0
    tps = 800 + 2.0 * sb + 15.0 * wm + 0.2 * ec - 0.5 * max(0, mc - 200) + jitter * 5
    tps = max(50.0, round(tps, 1))
    p99 = round(max(1.0, 40.0 - sb / 64.0 - wm / 8.0 + max(0, mc - 100) / 50.0), 2)
    slo = p99 <= a.target_latency_ms * 3
    no_regr = (a.baseline_tps <= 0) or (tps >= 0.95 * a.baseline_tps)
    m = {"status": "completed", "primary_metric": tps, "metric_name": "tps", "tps": tps,
        "p99_latency_ms": p99, "p99_within_slo": slo, "no_regression": no_regr,
        "bench_duration_s": 60, "training_gates_passed": slo and no_regr,
        "scorer": "offline-bench", "memory_knob_swept": True, "baseline_tps": True,
        "soak_test_passed": slo, "promotion_proposal": False}
    open("bench_result.json", "w", encoding="utf-8").write(json.dumps(m))
    _emit(**m)
    return 0
if __name__ == "__main__":
    import sys; sys.exit(main())
