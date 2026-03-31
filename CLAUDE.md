# Autoresearch Agent Workspace

You are running inside the autoresearch-agent Docker container.
Your job is to autonomously tune ML models. Act immediately — do NOT explore the filesystem. The workspace is already set up for you.

## CRITICAL: Act, Don't Explore

You have a LIMITED number of tool calls. **Do not waste them** on `ls`, `find`, `cat`, `docker ps`, or service health checks. The services are pre-verified and working. Jump straight to running experiments.

## Quick Reference

- **Python**: `/app/workspace/.venv/bin/python` (never system python)
- **Working dir**: `/app/workspace/`
- **Setup**: `/app/workspace/.venv/bin/python scripts/autotuner/setup.py --instrument {INSTRUMENT} --timeframe {TIMEFRAME}`
- **Train**: `/app/workspace/.venv/bin/python scripts/autotuner/{MODEL_TYPE}/prepare.py --config {WORKSPACE}/train.yaml`
- **Promote**: `/app/workspace/.venv/bin/python scripts/autotuner/promote.py --config {WORKSPACE}/best_train.yaml`
- ML services reachable (pre-verified): mlflow:5000, data-ingest:8000, ensemble-trainer:8000, rl-trainer:8000, feature-service:8000, minio:9000

## Exact Experiment Loop

**Step 1** — Setup (1 tool call):
```bash
cd /app/workspace && .venv/bin/python scripts/autotuner/setup.py --instrument {INSTRUMENT} --timeframe {TIMEFRAME}
```

**Step 2** — Read the model README and train.yaml (1 tool call):
Use read_file on `scripts/autotuner/{MODEL_TYPE}/README.md` and `{WORKSPACE}/train.yaml`.

**Step 3** — Baseline run (1 tool call):
```bash
cd /app/workspace && .venv/bin/python scripts/autotuner/{MODEL_TYPE}/prepare.py --config {WORKSPACE}/train.yaml 2>&1
```
After this completes, copy `train.yaml` to `best_train.yaml`:
```bash
cp {WORKSPACE}/train.yaml {WORKSPACE}/best_train.yaml
```

**Step 4** — For each subsequent iteration:
1. Edit `train.yaml` (change ONE parameter per the README strategy)
2. Run prepare.py (same command as Step 3)
3. Check the `---` delimited output: if `primary_metric` improved AND `all_gates_passed: true`, keep it (copy yaml to best). Otherwise revert from best.
4. **Fold stability check**: The `---` output includes walk-forward fold metrics:
   - `folds_passed: X/Y` — how many folds passed all 4 anti-overfit gates (higher = more robust)
   - `sharpe_cv` — coefficient of variation of Sharpe across folds (lower = more stable, <0.5 is good)
   - `std_oos_sharpe` — standard deviation of OOS Sharpe across folds
   - `trading_score` — composite score: `1.0×sharpe + 0.5×return - 2.0×drawdown`
   If `primary_metric` improved but `folds_passed` dropped or `sharpe_cv` increased significantly, the improvement is fragile — consider discarding.
5. Output: `ITERATION_RESULT: {"iteration": N, "primary_metric": X.XXXX, "metric_name": "...", "all_gates_passed": true|false, "decision": "keep|discard", "description": "brief description"}`

## Rules

- NEVER write outside `/app/workspace/`
- Do NOT run `docker`, `git`, `make`, or `apt` — they are not installed
- Do NOT check service health — services are verified before you start
- Spend at most 2-3 tool calls on setup/reading, then START TRAINING
- **NEVER pipe prepare.py output** through `| tail`, `| head`, `| grep`, or `timeout`. The full stdout is critical for iteration detection. Just run prepare.py directly — the tool has a 30-minute timeout built in.
- Do NOT set `timeout_s` below 1800 for ANY Python script (prepare.py, enrich_rl_dataset.py, etc.). Data fetching and training take 2-20 minutes. Use the default timeout.
- If training crashes with connection errors (data-ingest, mlflow, feature-service), wait 15 seconds and retry. Do NOT debug the connection — these are transient Docker DNS issues.
