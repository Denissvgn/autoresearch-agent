# Database Configuration Tuning

Offline (simulated) Postgres config tuning: edit `db_config.yaml`, run the
bench model, and promote the highest-TPS config that meets the p99 SLO. No
external services — the bench is a deterministic simulation.

## Session flow

1. The service's start path runs this skill's `bootstrap.py`, rendering the
   session workspace: `db_config.yaml` and `best_db_config.yaml`.
2. Each iteration edits one knob (`shared_buffers_mb`, `work_mem_mb`,
   `effective_cache_size_mb`, `max_connections`), then runs the evaluator:

   ```bash
   .venv/bin/python eval/run.py --config <session_ws>/db_config.yaml \
     --target-latency-ms 10
   ```

3. The evaluator emits an `ITERATION_RESULT:` marker (TPS primary metric,
   `p99_latency_ms`, `p99_within_slo`, `no_regression`, the anti-forgery
   nonce); the server verifies the nonce and records the iteration. Keep
   winners in `best_db_config.yaml`.

## Contract details

- **Config artifact flag**: the ML-style `--config` default — the pre-run
  snapshot keys on `db_config.yaml` (a declared copyable file confined to
  the session workspace).
- **Gates**: `p99_within_slo` and `no_regression`.
- **Phases**: `baseline_capture` → `memory_tuning` → `validation` →
  `promotion_proposal`.
- **Promotion**: `file_path` to the declared
  `configs/db/{subject_id}_{variant}.yaml` template under
  `AUTORESEARCH_HOST_CONFIGS_PATH` (development scope; production requires
  the HMAC-signed approval). Rollback restores the previous content at the
  recorded path.
