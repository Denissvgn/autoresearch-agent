# Database Configuration Tuning

You are a **DB config tuning agent** (offline simulation). Edit `db_config.yaml`,
run the bench, and promote the highest-TPS config that meets the p99 SLO.

## How iterations work

1. **Edit** `db_config.yaml` (one knob: `shared_buffers_mb`, `work_mem_mb`,
   `effective_cache_size_mb`, `max_connections`).
2. **Run**: `.venv/bin/python eval/run.py --config db_config.yaml --target-latency-ms 10`
3. Marker carries `primary_metric` (TPS), `p99_latency_ms`, `p99_within_slo`,
   `no_regression`, `server_nonce`.
4. Keep winners in `best_db_config.yaml`.

## Phases

- **baseline_capture** → **memory_tuning** → **validation** → **promotion_proposal**.

## Promotion

`file_path` to `configs/db/<subject>_<variant>.yaml`. Production needs approval.
