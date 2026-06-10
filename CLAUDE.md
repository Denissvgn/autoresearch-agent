# Autoresearch Agent Workspace

You are running inside the autoresearch-agent Docker container.
Your job is to autonomously tune ML models. Act immediately — do NOT explore the filesystem. The workspace is already set up for you.

## CRITICAL: Fully Autonomous — Never Ask Questions

You are running **unattended**. There is NO human monitoring this session. You MUST:
- **NEVER ask questions** — there is nobody to answer them.
- **NEVER say "should I…?" or "would you like…?"** — make the decision yourself.
- **NEVER wait for confirmation** — act on your best judgment immediately.
- When facing ambiguity, **always choose the approach most likely to improve metrics**.
- When a parameter change fails, **immediately revert and try a different dimension** — do not dwell or re-run the same thing.
- When you encounter an error, diagnose it yourself using the README/SKILL context and retry with an alternative approach.

## CRITICAL: Act, Don't Explore

You have a LIMITED number of tool calls. **Do not waste them** on `ls`, `find`, `cat`, or `docker ps`. Dependency readiness is handled by the server before your session starts. Jump straight to running experiments.

## Quick Reference

- **Python**: `/app/workspace/.venv/bin/python` (never system python)
- **Working dir**: `/app/workspace/`
- **Setup**: Run the server-provided setup command exactly as shown for this session. Fresh sessions use a server-prepared clean workspace; continuation sessions reuse the existing workspace and do not reset it.
- **Train**: `/app/workspace/.venv/bin/python scripts/autotuner/{MODEL_TYPE}/prepare.py --config {WORKSPACE}/train.yaml`
- **Promotion handoff**: Do not promote directly. Finish with a best validated config and let the server preview/confirm.
- ML dependency readiness is recorded in the server-owned research manifest.

## Exact Experiment Loop

**Step 1** — Setup (1 tool call):
```bash
cd /app/workspace && .venv/bin/python scripts/autotuner/setup.py --instrument {INSTRUMENT} --timeframe {TIMEFRAME} --models {MODEL_TYPE}
```

Use the setup command supplied by the server/orchestrator for the current session. Do not add reset flags manually; fresh-session cleanup and continuation behavior are server-owned.

**Step 2** — Read the model README and train.yaml (1 tool call):
Use read_file on `scripts/autotuner/{MODEL_TYPE}/README.md` and `{WORKSPACE}/train.yaml`.

If `train.yaml` already contains tuned sections such as `reward_curriculum` or `vdmc_params`, treat them as part of the production baseline. Do not overwrite them with generic defaults before you have reproduced the baseline once.

**Step 3** — Baseline run (1 tool call):
```bash
cd /app/workspace && .venv/bin/python scripts/autotuner/{MODEL_TYPE}/prepare.py --config {WORKSPACE}/train.yaml
```
Do NOT append `2>&1`, `| tail`, `| head`, or any other shell redirection or pipe — command policy rejects them. `prepare.py` already merges stderr into stdout.
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
   - `seeds=X/Y` (per fold) — when `n_seed_trials > 1`, how many seed trials passed gates. Low ratios indicate seed sensitivity.
   Sharpe is annualized with √252 (daily convention). Typical good OOS Sharpe: 0.05–0.30. Values >1.0 are exceptional.
   If `primary_metric` improved but `folds_passed` dropped or `sharpe_cv` increased significantly, the improvement is fragile — consider discarding.
5. Output: `ITERATION_RESULT: {"iteration": N, "primary_metric": X.XXXX, "metric_name": "...", "all_gates_passed": true|false, "decision": "keep|discard", "description": "brief description"}`

   **IMPORTANT:** Emit `ITERATION_RESULT` ONLY immediately after a `prepare.py` (or `run_phase1c_*` / `run_phase1b_*`) run that produced a `---` block in the same turn. Do NOT emit a marker on turns where you only ran `cp`, `read_file`, or `write_file` — the server will discard those markers. Revert/restore turns are bookkeeping, not iterations.

## Rules

- NEVER write outside `/app/workspace/`
- Do NOT run `docker`, `git`, `make`, or `apt` — they are not installed
- Spend at most 2-3 tool calls on setup/reading, then START TRAINING
- **NEVER pipe prepare.py output** through `| tail`, `| head`, `| grep`, or `timeout`. The full stdout is critical for iteration detection. Just run prepare.py directly — the bash tool defaults to a 2-hour timeout, which already covers a full trial.
- **Do NOT set `timeout_s` for prepare.py** — rely on the 2-hour default. Walk-forward training runs every fold across multiple seed trials sequentially, so a single trial can take 30–40 minutes (longer than a naive "one training run"). If you ever do set `timeout_s`, keep it at or above the trial's own auto-calculated GPU timeout (printed as `[prepare] Auto-calculated timeout: …`); never set it below that, or the bash tool will kill the trial before it can finish and the iteration records no metric.
- If training crashes with connection errors (data-ingest, mlflow, feature-service), wait 15 seconds and retry. Do NOT debug the connection — these are transient Docker DNS issues.

## Anti-Waste Rules (MANDATORY)

These rules prevent common failure patterns observed in research sessions:

1. **Never re-run the exact same config+seed** — training is deterministic. Same config+seed = same result. Always change at least one meaningful parameter.
2. **Never change ONLY the seed** — if a config only works with one specific seed, it is not robust and will never pass multi-seed validation. Changing seed is not a valid optimization strategy.
3. **Make meaningful changes** — do not nudge parameters by tiny amounts (e.g., changing trade penalty from 0.025 to 0.022). Change by at least 2× or 0.5× for multiplicative params, or jump to a qualitatively different value.
4. **Never "restore best and re-run unchanged"** — if you already ran that config, re-running it gives the same result. Always vary at least one parameter when restoring from best.
5. **Diversify search dimensions** — if 3+ consecutive iterations tuned the same parameter (e.g., reward weights), switch to a completely different dimension (architecture, learning rate, VDMC, timesteps).
6. **Quick mode trap**: Quick mode (2 folds, 50k steps) is for rapid screening only. If you've found a good config in quick mode, validate it in full mode EARLY (don't wait until the last iteration). Quick-mode winners often fail in full mode — expect this and plan for it.
