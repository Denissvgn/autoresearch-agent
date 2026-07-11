---
name: volatility-autotuner
description: "Autonomous volatility breakout model tuning loop — run overnight experiments to improve AUC, ATR threshold selection, calibration, and class balance for a specific instrument without human intervention. Use this skill whenever the user wants to: start an autonomous or automatic volatility tuning loop, run unattended volatility model experiments, auto-tune volatility hyperparameters while they sleep, launch autoresearch for volatility models, iterate on volatility configs in a loop, or says things like 'tune volatility model overnight', 'automate volatility tuning', 'run volatility experiments in a loop', 'autotune volatility for BTC', 'start volatility autoresearch', 'sweep ATR multipliers automatically'. This skill is specifically for the AUTONOMOUS loop — for guided/manual volatility tuning with human-in-the-loop, use the volatility-model-tuning skill instead. Also trigger when the user asks to 'find the best ATR multiplier overnight', 'fix positive rate / class balance autonomously', 'run volatility breakout experiments unattended', 'keep sweeping ATR values until you find the best one', or wants to iterate on volatility train.yaml in an unattended loop. Even if the user doesn't explicitly say 'autotune' or 'autonomous', trigger this skill if they clearly want the volatility breakout model improved through multiple unattended experiment iterations — phrases like 'I'll check results tomorrow', 'run it while I'm away', 'keep going until the positive rate is in range', 'sweep from 1.5 to 6.0', or 'find the best combination overnight' all indicate this skill. DO NOT trigger for: single one-off volatility training runs, manual step-by-step volatility tuning (use volatility-model-tuning instead), direction or RL model tuning (use direction-autotuner or rl-autotuner), checking current volatility metrics, promoting volatility configs to production, diagnosing false positives in production inference, or adding features to the volatility model."
argument-hint: "Instrument and optional tag (e.g., 'DOGE_USDT 15m', 'BTC_USDT start autotuning', 'ETH_USDT mar28')"
---

# Volatility Model Autotuner Loop

Autonomous experiment loop for improving volatility breakout prediction metrics. You modify `train.yaml` hyperparameters (especially ATR multiplier), run experiments via the fixed `prepare.py` harness, and keep/discard based on the primary metric.

The primary metric is **`auc`** (higher is better). A critical constraint is **`positive_rate`** must be 10–40% for meaningful class balance.

## Critical: Feature Consistency

Both direction and volatility models share the same feature library (v2.1.0, 93 features). They diverge only at selection — volatility excludes `atr_ratio` and `bb_width`. Never change `feature_library_version` without also updating direction.

## Setup

### 1. Initialize workspace

```bash
cd /app/workspace && .venv/bin/python scripts/autotuner/setup.py --instrument <INSTRUMENT> --timeframe <TIMEFRAME> --models volatility
```

Creates `runs/autotuner/<INSTRUMENT>_<TIMEFRAME>/volatility/` with pre-populated `train.yaml`. In autoresearch sessions, run the setup command exactly as supplied by the server prompt.

### 2. Read context files

Use read_file on:

- `scripts/autotuner/volatility/README.md` — Volatility knobs, ranges, strategy
- `runs/autotuner/<INSTRUMENT>_<TIMEFRAME>/volatility/train.yaml` — Current config

### 3. Establish baseline

```bash
cd /app/workspace && .venv/bin/python scripts/autotuner/volatility/prepare.py \
    --config runs/autotuner/<INSTRUMENT>_<TIMEFRAME>/volatility/train.yaml
```

The orchestrator auto-detects results from the `---` block in prepare.py output. You do NOT need to grep, parse metrics, or log to `results.tsv`.

Copy the config as your checkpoint:
```bash
cp runs/autotuner/<INSTRUMENT>_<TIMEFRAME>/volatility/train.yaml \
   runs/autotuner/<INSTRUMENT>_<TIMEFRAME>/volatility/best_train.yaml
```

### 4. Begin the experiment loop

## The Experiment Loop

### LOOP FOREVER:

**Step 1 — Understand the state.**
Read `train.yaml` and (if exists) `results.json`. What ATR multiplier was used? What's the positive rate? What's the best AUC so far?

**Step 2 — Form a hypothesis.**
Pick ONE parameter to change. For volatility, ATR multiplier is typically the most impactful knob — start there.

**Step 3 — Edit `train.yaml`.**
Use write_file. Keep it minimal — one variable at a time.

**Step 4 — Run.**
```bash
cd /app/workspace && .venv/bin/python scripts/autotuner/volatility/prepare.py \
    --config runs/autotuner/<INSTRUMENT>_<TIMEFRAME>/volatility/train.yaml
```

The orchestrator auto-records the iteration from the `---` output block.

**Step 5 — Keep or discard.**

Check the `---` output from prepare.py:

If `primary_metric` improved AND `all_gates_passed: true` AND positive_rate is 10–40%:
- **KEEP**: Copy `train.yaml` → `best_train.yaml`.

If worse or class balance violated:
- **DISCARD**: Restore from `best_train.yaml`.
  ```bash
  cp runs/autotuner/<INSTRUMENT>_<TIMEFRAME>/volatility/best_train.yaml \
     runs/autotuner/<INSTRUMENT>_<TIMEFRAME>/volatility/train.yaml
  ```

**Step 6 — Next hypothesis.** Return to Step 1.

## Strategy Playbook

### Phase 1: ATR Multiplier Discovery (Most Impactful)

The ATR multiplier defines what counts as a "breakout." This is the single most important knob.

| Experiment | Change | Why |
|-----------|--------|-----|
| Disable auto-sweep | `atr_mult_sweep_enabled: false` | Take manual control to isolate the effect |
| Low ATR | `volatility_atr_mult: 1.5` → `2.0` → `2.5` | More breakouts, higher positive rate. Good if current pos_rate < 10%. |
| Medium ATR | `volatility_atr_mult: 3.0` → `3.5` | Balanced. Usually the sweet spot for crypto. |
| High ATR | `volatility_atr_mult: 4.0` → `5.0` → `6.0` | Fewer, larger breakouts. Good if current pos_rate > 40%. |

**Goal**: Find the ATR mult that produces 10–40% positive rate AND the highest AUC. Run each candidate separately in quick mode, then do a full run with the winner.

### Phase 2: Decision Boundary & Calibration

Once ATR is set and AUC is decent:

| Experiment | Change | Why |
|-----------|--------|-----|
| Threshold sweep | Try: `f1`, `f_beta`, `youden_j`, `gmean` | Different balance of precision/recall for breakout detection. |
| Beta for recall | `threshold_beta: 2.0 → 3.0 → 4.0` | Higher beta catches more breakouts (recall-heavy, typical for breakout detection). |
| Beta for precision | `threshold_beta: 1.0 → 0.5` | Lower beta for fewer false alarms. |
| Calibration method | Switch between `isotonic` and `sigmoid` | If `ece_calibrated > 0.05`, calibration is the bottleneck. |

### Phase 3: Temporal & Ensemble

| Experiment | Change | Why |
|-----------|--------|-----|
| Recency weighting | `sample_weight_halflife: 5000 → 3000 → 2000` | Volatility regimes shift — recency bias helps. |
| Prediction horizon | `prediction_horizon: 4 → 6 → 8 → 2` | Shorter = harder but more actionable. Longer = easier but less timely. |
| Ensemble pruning | Remove `lgb_dart`, `lgb_goss` | Sometimes noisier learners hurt volatility more than direction. |

### Combining Improvements

After ATR is locked, combine the winning threshold, calibration, and temporal settings.

## Quick vs. Full Mode

- **Quick** (`--quick`): ~2-5 min. 3 base learners, 3 folds. Good for ATR sweep.
- **Full** (no `--quick`): ~30-60 min. Full ensemble. Required for server promotion review.

## Promotion Handoff

Do not promote directly. Finish with a best validated config and let the server preview/confirm. Ensure `best_train.yaml` points at the winning full-mode config, then stop cleanly. After server-confirmed volatility promotion, the RL agent should be retrained because the `volatility_proba` distribution changed.

## NEVER STOP

Once the loop has begun, do NOT pause to ask for confirmation. The human may be asleep. Continue autonomously until manually interrupted. If you run out of ideas:
- Re-read `scripts/autotuner/volatility/README.md` for new angles.
- Try combining previous near-misses (winning ATR mult + winning threshold strategy + winning calibration method).
- Try radical changes (opposite ATR direction, different threshold strategy, reduce ensemble to 3 learners, very narrow or very wide breakout definition).

## Constraints

- **Python**: `/app/workspace/.venv/bin/python` only. Never system Python.
- **No shell redirection**: `2>&1`, pipes, command substitution (`$(...)`), heredocs, and background execution (`&`) are rejected by command policy. `prepare.py` already merges stderr into stdout, and the orchestrator parses the full `---`-delimited block — invoke it bare.
- **No git/docker/make**: These are not installed. Do not try to use them.
- **Services are pre-verified**: Do NOT check service health or run connectivity tests.
- **Workspace-only I/O**: All files under `/app/workspace/`. Never write outside.
- **Per-run timeout**: Quick ~5 min, Full ~60 min. Kill if 2x over.
- **Simplicity**: Simpler config with same AUC → keep simpler.

## Don't Waste Iterations on No-Op Sweeps

The primary metric is **AUC-based**, not threshold-based. These knobs do NOT move `auc` and should not be primary sweep dimensions:

- `threshold_strategy`, `threshold_beta` (operating-point selection only — affects precision/recall at the cut, but the AUC integral is unchanged)
- `calibration_method` (`isotonic` vs `sigmoid` — affects probability shape, rarely AUC by >1e-3)

High-impact dimensions to prioritize instead: `volatility_atr_mult` (Phase 1 — see the Strategy Playbook), `prediction_horizon`, `purge_multiplier` (walk-forward embargo), `roster_preset` (feature set), `sample_weight_halflife`.

## Time Budget Awareness

The session has a finite wall-clock timeout (user-configurable, typically 2-4h). `prepare.py` prints periodic `[prepare] Training in progress... Xm elapsed` lines during long runs. After each iteration completes, estimate your remaining time budget:

1. Track average iteration duration from training_time_s values.
2. If remaining time < 1.5× average iteration time, **checkpoint the current best and stop** rather than starting a doomed iteration that will be killed by timeout. The server owns promotion preview/confirm after the session.
3. Prefer quick-mode experiments when time is short — they complete in ~5 min vs ~60 min for full.

## Phase Advancement (server-tracked contract)

> **Why volatility has 8 phases (vs. 4 for RL):** supervised breakout classifiers require explicit calibration replay, multi-seed robustness, and inference-parity validation before serving — each is a separate phase so the UI can show per-gate progress. RL doesn't need these because walk-forward economic replay is built into RL training; one validation phase covers it.

The orchestrator tracks your session against an 8-phase plan and refuses to honor `end_turn` while phases remain incomplete and budget is available. Always tag iteration markers with `search_phase: <phase_id>` so the server can attribute work, and emit at least one of the listed evidence keys in `metrics_json` (or its nested `config`) to advance.

| # | Phase ID | Min / Max iters | Evidence keys |
|---|---|---|---|
| 1 | `baseline_capture` | 1 / 3 | (iteration count) |
| 2 | `atr_sweep` | 4 / 20 | `volatility_atr_mult`, `atr_multiplier`, `atr_mult_sweep_enabled` |
| 3 | `threshold_calibration` | 2 / 12 | `threshold_strategy`, `threshold_beta`, `calibration_method` |
| 4 | `temporal_ensemble` | 2 / 10 | `sample_weight_halflife`, `prediction_horizon`, `ensemble_pruning`, `base_model_keys` |
| 5 | `calibration_replay_gates` | 1 / 8 | `calibration_full_validation`, `economic_replay` |
| 6 | `multi_seed_robustness` | 1 / 6 | `seed_trials`, `n_seed_trials`, `seeds_passed_gates` |
| 7 | `inference_parity_replay` | 1 / 4 | `inference_parity`, `inference_reload_validation` |
| 8 | `promotion_proposal` | 0 / 4 | `promotion_scope` (auto-emitted), `development_promotion_metadata`, `promotion_decision`, … |

**Rules:**
- Do not call `end_turn` while any phase is `pending` or `in_progress` and budget remains. The loop guard rejects it and injects a continuation message describing the next action.
- Reaching a phase's `Max iters` ceiling triggers a system nudge to advance. Treat it as a hard signal to emit the evidence key or move on.
- If you believe the plan should terminate early (e.g. baseline is best and further work cannot improve it), reply with a single line beginning `TERMINATE_REQUEST:` followed by structured justification referencing each incomplete phase ID. Do not silently `end_turn`. **An explicit `TERMINATE_REQUEST:` waives incomplete iteration-count phases for promotion** (training/calibration/parity hard gates still run) — silent `end_turn` does not.
- Phase `atr_sweep` no longer auto-completes after any fixed number of iterations — it requires either an explicit `volatility_atr_mult` key in metrics or 4+ iterations tagged with `search_phase: atr_sweep`.

### Phase 5 (`calibration_replay_gates`) — Auto-Evidence from Training Pipeline

`calibration_full_validation` and `economic_replay` are emitted automatically by `prepare.py` after every training run. **No additional action is needed** — the server records both keys in `metrics_json`, and `calibration_replay_gates` advances after the first iteration completes.

If calibration gates fail repeatedly, address the configuration problem in `atr_sweep` or `threshold_calibration` (earlier phases), not by staying in phase 5.

### Phase 6 (`multi_seed_robustness`) — Auto-Evidence from Training Pipeline

`seed_trials`, `n_seed_trials`, and `seeds_passed_gates` are emitted automatically by `prepare.py` after every training run. **No additional action is needed** — the server records a single-seed probe in `metrics_json`, and `multi_seed_robustness` advances after the first iteration completes.

Full multi-seed robustness validation happens at promotion review, not during autotuner iteration.

### Phase 7 (`inference_parity_replay`) — Auto-Evidence from Training Pipeline

`inference_parity` is emitted automatically by `prepare.py` after every training run. **No additional action is needed** — the server records the parity evidence in `metrics_json`, and `inference_parity_replay` advances after the first iteration completes.

### Phase 8 (`promotion_proposal`) — Auto-Evidence from Training Pipeline

`promotion_scope` is emitted automatically by `prepare.py` after every training run. **No additional action is needed** — the server records this key in `metrics_json`, and `promotion_proposal` advances after the first iteration completes.

On session completion, the server runs its own promotion evaluation (`_try_auto_promote`) which validates gates, generates `development_promotion_metadata`, and auto-confirms if all gates pass. The agent does not need to construct or emit promotion metadata manually.

When all phases are complete and the session has exhausted its useful experiments, call `end_turn`. The server handles the rest.
