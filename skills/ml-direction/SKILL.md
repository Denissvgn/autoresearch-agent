---
name: direction-autotuner
description: "Autonomous direction model tuning loop — run overnight experiments to improve walk-forward AUC, calibration, and threshold settings for a specific instrument without human intervention. Use this skill whenever the user wants to: start an autonomous or automatic direction tuning loop, run unattended direction model experiments, auto-tune direction hyperparameters while they sleep, launch autoresearch for direction models, iterate on direction configs in a loop, or says things like 'tune direction model overnight', 'automate direction tuning', 'run direction experiments in a loop', 'autotune direction for DOGE', 'start direction autoresearch'. This skill is specifically for the AUTONOMOUS loop — for guided/manual direction tuning with human-in-the-loop, use the direction-model-tuning skill instead. Also trigger when the user asks to 'kick off overnight direction hyperparameter optimization', 'keep iterating on direction configs until morning', 'sweep deadzone widths and thresholds automatically', 'run direction experiments unattended', or wants to set up an autoresearch branch and iterate on direction train.yaml in a loop. Even if the user doesn't explicitly say 'autotune' or 'autonomous', trigger this skill if they clearly want the direction model improved through multiple unattended experiment iterations — phrases like 'don't stop until morning', 'I'll check results tomorrow', 'run it while I'm away', or 'keep going until diminishing returns' all indicate this skill. DO NOT trigger for: single one-off direction training runs, manual step-by-step direction tuning (use direction-model-tuning instead), volatility or RL model tuning (use volatility-autotuner or rl-autotuner), diagnosing direction model regressions, promoting configs to production, or adding features to the direction model."
argument-hint: "Instrument and optional tag (e.g., 'DOGE_USDT 15m', 'BTC_USDT start autotuning', 'DOGE_USDT mar28')"
---

# Direction Model Autotuner Loop

Autonomous experiment loop for improving direction model (up/down classification) metrics. You modify `train.yaml` hyperparameters, run experiments via the fixed `prepare.py` harness, and keep/discard based on the primary metric — all without human intervention.

This is the direction-specific variant. The primary metric is **`composite_direction_score`** (higher is better). It is a **three-term blend** — discrimination is necessary but NOT sufficient; probability quality and post-cost economics count too:

- **AUC discrimination (40%)** — `0.6·walkforward_mean_auc + 0.4·stacking_holdout_auc`. How well the signal ranks outcomes across time and on a held-out split. Moved by `direction_pct_threshold`, `prediction_horizon`, `horizon_candidates`, `sample_weight_halflife`, `purge_multiplier`, `base_model_keys`, `cv_folds`, and the **feature lanes** (see `feature_config` below). **Serving is Option A — the single best base learner is shipped and scored**, so `meta_model` and the `stacking_calibration_*` knobs tune a meta-stacker that is *not* served and do not move this term; leave them at their defaults and tune the levers below instead.
- **Probability quality (30%)** — `1 − normalized_brier` (Brier vs the 0.25 random ceiling). Rewards well-calibrated, confident probabilities. **A high-AUC model with weak, compressed probabilities (Brier ≈ 0.25) scores near zero on this term.** It reads the served model's Brier, so it is moved by what sharpens the base learner's probabilities: **richer features** (the `feature_config` lanes below), **cleaner labels** (`label_mode`, `direction_pct_threshold`), and the served model's calibrator (`calibration_method`). Weak base discrimination caps this term regardless of calibration — improve the signal first.
- **Post-cost economics (30%)** — squashed post-cost Sharpe from a real fee+slippage replay on the OOF probabilities, **scaled down by a drawdown penalty**: a config with a catastrophic max-drawdown cannot score ≥ 0.5 on Sharpe alone. Rewards configs that actually make money after costs *without* blowing up. A candidate that loses money post-cost, or suffers a deep drawdown, scores below 0.5 here.

**Implication:** widening the dead-zone to inflate AUC no longer maximizes the score — it shrinks the labeled set and worsens Brier/economics. Optimize all three terms. The `---` output shows `composite_auc_term` / `composite_brier_term` / `composite_econ_term` (plus `drawdown_factor` and `max_drawdown`) so you can see which term is limiting.

**Diagnostics (do not feed the score, but inform strategy):** `regime_breakdown` shows per-regime AUC and `economic_replay_regime_gated` shows a post-cost replay that abstains (holds flat) outside CHOP/TREND — if the regime-gated Sharpe/drawdown are markedly better than the ungated economics, the model's edge is concentrated in those regimes. The per-iteration `config_snapshot` records the actual `label_mode`/`direction_pct_threshold` used, and the iteration context lists configs already tried this session — **do not re-propose an identical canonical config; it is dedup-rejected and wastes a turn.**

> **Judge improvement only against THIS session's baseline.** `composite_direction_score` is re-measured fresh during `baseline_capture` (iteration 1) at the start of every session. Compare every candidate against that value — never against a remembered, historical, or externally-recorded score (a prior run, a report, or a promoted config's `achieved_metric_value`). Metric definitions evolve, so a number from another context may be on a different scale; treating it as a target — or reading a lower current score as a "regression" — sends you chasing a phantom. The only valid comparison is candidate vs. this session's baseline.

### Parameter → Metric Impact Map

| Parameter | Moves walkforward? | Moves stacking AUC? | Notes |
|-----------|:------------------:|:-------------------:|-------|
| `direction_pct_threshold` | **YES** | **YES** | Changes labels → affects everything |
| `prediction_horizon` / `horizon_candidates` | **YES** | **YES** | Changes labels → affects everything |
| `feature_config` lanes (DC / VDMC / spectral / funding) | **YES** | **YES** | Richer features → better base discrimination + Brier (see below) |
| `sample_weight_halflife` | **YES** | **YES** | Changes sample weights |
| `purge_multiplier` | **YES** | **YES** | Changes walk-forward embargo |
| `base_model_keys` | no | **YES** | Different learner pool → different **served** best base model |
| `cv_folds` | no | **YES** | Different fold structure → different OOF |
| `calibration_method` | no | no (AUC is calibration-invariant) | Calibrates the **served** best-base model → moves the Brier term |
| `threshold_strategy` / `threshold_beta` | no | no (AUC is threshold-independent) | Changes precision/recall/F1/signal_rate only |
| `max_signal_rate` | no | no | Changes optimal_threshold selection |
| `hpo_n_trials` / `enable_model_hpo` | no | **YES** | Better hyperparameters → better base models |

> **`meta_model` and `stacking_calibration_*` are not in the tunable set.** Serving is Option A (ship the single
> best base learner), so the meta-stacker these knobs control is never deployed or scored. Tuning them wastes
> iterations — focus on the levers above.

### Feature lanes (`feature_config`)

The richest untapped lever is the **feature set**. The `feature_config` block in `train.yaml` toggles independent
feature lanes; enabling more lanes gives the base learners more signal, lifting both AUC and Brier. All lanes are
causal and OHLCV-only→auto-parity safe (train==serve).

| Flag | Adds |
|------|------|
| `funding_features_enabled` | Perp funding-rate features (derivatives lane) |
| `open_interest_features_enabled` | Open-interest features (derivatives lane) |
| `directional_change_features_enabled` | Causal multi-scale Directional-Change event features |
| `vdmc_enabled` | VDMC directional-momentum features |
| `spectral_features_enabled` | Causal rolling-FFT spectral features (DPU-050 evidence-gated) |

Enable lanes one at a time (so you can attribute the change), keep a lane only if `composite_direction_score`
improves and gates still pass, and prefer lanes that lift the **limiting** term shown in the `---` output.
The `spectral_features_enabled` lane is DPU-050 evidence-gated: it **requires** the two companion keys
(`spectral_features_version`, `spectral_evidence_report_path`) set verbatim as documented in `train.yaml`, or the
run fails fast. `directional_change` and `vdmc` need no companion keys.

## Setup

### 1. Initialize workspace

```bash
cd /app/workspace && .venv/bin/python scripts/autotuner/setup.py --instrument <INSTRUMENT> --timeframe <TIMEFRAME> --models direction
```

Creates `runs/autotuner/<INSTRUMENT>_<TIMEFRAME>/direction/` with a `train.yaml` pre-populated from the current server-approved baseline (or defaults). In autoresearch sessions, run the setup command exactly as supplied by the server prompt, including any `--models direction` argument.

### 2. Read context files

Use read_file on:

- `scripts/autotuner/direction/README.md` — Direction knobs, ranges, strategy
- `runs/autotuner/<INSTRUMENT>_<TIMEFRAME>/direction/train.yaml` — Current config

### 3. Establish baseline

Run the current `train.yaml` as-is:

```bash
cd /app/workspace && .venv/bin/python scripts/autotuner/direction/prepare.py \
    --config runs/autotuner/<INSTRUMENT>_<TIMEFRAME>/direction/train.yaml 2>&1
```

The orchestrator auto-detects results from the `---` block in prepare.py output. You do NOT need to grep, parse metrics, or log to `results.tsv` — this is handled automatically.

After the baseline, copy the config as your checkpoint:
```bash
cp runs/autotuner/<INSTRUMENT>_<TIMEFRAME>/direction/train.yaml \
   runs/autotuner/<INSTRUMENT>_<TIMEFRAME>/direction/best_train.yaml
```

### 4. Begin the experiment loop

## The Experiment Loop

### LOOP FOREVER:

**Step 1 — Understand the state.**
Read `train.yaml` and (if exists) `results.json`. What's been tried? What's the current best metric? What bottleneck needs addressing?

**Step 2 — Form a hypothesis.**
Pick ONE parameter to change and explain why, based on the strategy guide below. Small, targeted changes produce clearer signal about what works.

**Step 3 — Edit `train.yaml`.**
Use write_file to make the change. Keep it minimal — one variable at a time for clean attribution.

**Step 4 — Run the experiment.**
```bash
cd /app/workspace && .venv/bin/python scripts/autotuner/direction/prepare.py \
    --config runs/autotuner/<INSTRUMENT>_<TIMEFRAME>/direction/train.yaml 2>&1
```

The orchestrator auto-records the iteration from the `---` output block.

**Step 5 — Keep or discard.**

Check the `---` output from prepare.py:

If `primary_metric` improved (higher `composite_direction_score`) AND `all_gates_passed: true`:
- **KEEP**: Copy `train.yaml` to `best_train.yaml`.

If `primary_metric` is equal or worse, or gates failed:
- **DISCARD**: Restore `train.yaml` from `best_train.yaml`.

**TIP**: After discarding, check which component moved:
- If `walkforward_auc` moved but `auc` didn't → the change only affected data/labels, ensemble was unaffected.
- If `auc` moved but `walkforward_auc` didn't → the change only affected ensemble composition.
- If neither moved → the parameter had no effect (check for a bug in the config).
- If both moved → the change was fundamental (label/data change). Preferred.
  ```bash
  cp runs/autotuner/<INSTRUMENT>_<TIMEFRAME>/direction/best_train.yaml \
     runs/autotuner/<INSTRUMENT>_<TIMEFRAME>/direction/train.yaml
  ```

**Step 6 — Next hypothesis.** Return to Step 1.

## Strategy Playbook

The knobs are ordered by typical impact. Start with high-impact levers and progress to fine-tuning once the fundamentals are solid.

### Priority 1: Label Quality (if AUC < 0.52)

The model can't distinguish up from down — the labels are too noisy.

| Experiment | Change | Why |
|-----------|--------|-----|
| Widen deadzone | `direction_pct_threshold: 0.015 → 0.025 → 0.030` | Removes ambiguous near-zero moves from training. Most impactful single knob for noisy instruments. |
| Enable a feature lane | `feature_config: directional_change_features_enabled: true` (then `vdmc_enabled`, then `spectral_features_enabled`) | Adds causal multi-scale features so the base learners have more signal. Enable one lane per iteration; keep if the score improves. |
| Expand horizons | Add more `horizon_candidates` (e.g., `[4,8,12,24,48,64,96]`) | The instrument may be predictable at longer or shorter horizons than the current set covers. |
| Increase HPO budget | `hpo_n_trials: 100 → 150` | More Optuna trials to find better LightGBM/XGBoost hyperparameters. |

### Priority 2: Decision Boundary (if AUC > 0.54 but precision/recall is poor)

The ranking is useful but the cutoff converts good probabilities into bad decisions.

| Experiment | Change | Why |
|-----------|--------|-----|
| Threshold strategy sweep | Try each: `f1`, `f_beta`, `youden_j`, `gmean` | Different strategies balance precision/recall differently. |
| Beta sweep | `threshold_beta: 0.3 → 0.5 → 1.0 → 2.0 → 3.0` | Lower beta = precision. Higher = recall. |
| Signal rate cap | `max_signal_rate: 0.35 → 0.25 → 0.15` | Forces higher confidence signals. |

### Priority 3: Temporal Stability (if walk-forward CV > 0.25)

The model works in some time periods but fails in others.

| Experiment | Change | Why |
|-----------|--------|-----|
| Recency weighting | `sample_weight_halflife: 5000 → 3000 → 2000` | Gives more weight to recent data, adapts faster. |
| Calibration method | Switch between `isotonic` and `platt` | Different calibrators suit different data distributions. |
| Wider purge | `purge_multiplier: 3.0 → 4.0 → 5.0` | Prevents label leakage across walk-forward folds. |

### Priority 4: Ensemble Composition

| Experiment | Change | Why |
|-----------|--------|-----|
| Remove noisy learners | Drop `lgb_dart`, `lgb_goss` | DART/GOSS add noise in some instruments. |
| RF-only ensemble | `base_model_keys: [rf, rf_deep, rf_shallow]` | Random forests may be more stable for this instrument. |

### Combining Improvements

After individual knob experiments, try combining the top 2-3 winners. E.g., if `deadzone=0.025` and `threshold_beta=0.3` both improved, try them together.

## Quick vs. Full Mode

- **Quick mode** (`--quick`): ~2-5 min. Uses 3 base learners, 3 CV folds, minimal HPO. Good for rapid exploration.
- **Full mode** (no `--quick`): ~30-60 min. Full 11 learners, 7 folds, 100 HPO trials. Required for promotion.

Start with quick mode. Once you find a promising config, validate it with a full run before server promotion review.

## Promotion Handoff

When satisfied (all gates passed on a full run, metric exceeds baseline meaningfully), stop for server promotion review. Do not promote directly. Finish with a best validated config and let the server preview/confirm. Ensure `best_train.yaml` points at the winning full-mode config, then stop cleanly.

## NEVER STOP

Once the loop has begun, do NOT pause to ask for confirmation. The human may be asleep. Continue autonomously until manually interrupted. If you run out of ideas:
- Re-read `scripts/autotuner/direction/README.md` for new angles.
- Try combining previous near-misses.
- Try radical changes (different threshold strategy, reduce ensemble to 3 learners, very wide deadzone).

## Constraints

- **Python**: `/app/workspace/.venv/bin/python` only. Never system Python.
- **No shell redirection**: `2>&1`, `| tail`, `| head`, `| grep`, command substitution (`$(...)`), heredocs, and background execution (`&`) are rejected by command policy. `prepare.py` already merges stderr into stdout, and the orchestrator parses the full `---`-delimited block — running it bare is sufficient.
- **No git/docker/make**: These are not installed. Do not try to use them.
- **Services are pre-verified**: Do NOT check service health or run connectivity tests.
- **Workspace-only I/O**: All files under `/app/workspace/`. Never write outside.
- **Per-run timeout**: Quick ~5 min, Full ~60 min. Kill if 2x over.
- **Simplicity**: Equal metrics with simpler config → keep simpler.

## Don't Waste Iterations on No-Op Sweeps

`composite_direction_score` is a three-term blend `W_auc·auc_term + W_brier·brier_term + W_econ·econ_term` whose weights come from a **per-asset profile** (`standard` = 0.40/0.30/0.30; `rl_feature` = 0.60/0.30/0.10 for assets where direction feeds the RL approval model — discrimination dominates, economics is a guardrail). The active profile is in `composite_weights_profile`; compare candidates only against this session's baseline (same profile). The `brier_term` is the **served best-base model's own calibrated Brier** (not the meta-stacker's). The `econ_term` scores the **regime-gated replay** (the deployed policy: trade BREAKOUT, gate TREND by rolling AUC, never CHOP) with a per-asset drawdown penalty — so it rewards a signal that is profitable *in the regimes you actually trade*, not one propped up by choppy-regime noise. The terms that matter are discrimination, probability quality, and post-cost economics — **operating-point-only** parameters move none of them and should NOT be your primary optimization dimensions:

- `threshold_strategy` and `threshold_beta` (operating-point selection only — AUC and Brier are threshold-independent; the economic replay sweeps its own threshold)
- `max_signal_rate` (operating-point only — changes the selected cut, not the score terms)
- `meta_model`, `walkforward_n_folds`, and `stacking_calibration_method` *aliases that don't change the candidate set* — the served model is the best base, so these are inert. Sweeping them produces identical scores and wastes iterations.
- `hpo_n_trials` — **no-op in stacking mode** (the default). Optuna HPO is only wired for the single-model path; the stacking base learners train with fixed defaults. Changing it will not move the score.

By contrast, these DO move the score and are worth sweeping: `direction_pct_threshold` and `label_mode` (change the LABELS → AUC, Brier, and economics all shift), the **feature lanes** (`feature_config.*`), `base_model_keys`, `sample_weight_halflife`, and the calibration knobs (`stacking_calibration_methods` / `stacking_calibration_auc_floor`) which move the probability-quality term.

**When you cannot beat baseline, stop — don't spin.** If you have swept the productive levers above and nothing beats this session's baseline, do NOT keep running training to "re-validate" the late phases (`calibration_replay_gates`, `multi_seed_robustness`, `inference_parity_replay`) — their evidence is emitted automatically by any single finalist run and the phases auto-advance (see Phase Advancement below). Re-running the finalist, or perturbing an inert knob to manufacture a "new" iteration, only burns budget. Reply with `TERMINATE_REQUEST:` and justify (baseline is best; productive levers exhausted) — this waives the remaining iteration-count phases while the training/calibration/parity hard gates still run on your best config.

`label_mode` options: `fixed_pct` (±`direction_pct_threshold`), `vol_scaled` (per-bar ATR dead-zone), and `dc_cascade` (label = direction toward the next confirmed Directional-Change pivot at the finest ATR multiple in `dc_theta_atr_mults`). For `dc_cascade`, the **finest ATR multiple controls label difficulty** — too fine labels micro-noise (near-random AUC); coarser marks meaningful swings. The multi-scale Directional-Change *signal* is most reliably exploited as **features** (the DC feature lane) rather than as the label; treat `dc_cascade`-as-label as experimental and compare it against `fixed_pct` before keeping it.

High-impact dimensions to prioritize: `horizon`, `purge_multiplier` (walk-forward embargo), `roster_preset` (feature set), `sample_weight_halflife`, ensemble composition, calibration method selection, and TS-FM adapter selection. Read the README for parameter-impact details before sweeping.

## Time Budget Awareness

The session has a finite wall-clock timeout (user-configurable, typically 2-4h). `prepare.py` prints periodic `[prepare] Training in progress... Xm elapsed` lines during long runs. After each iteration completes, estimate your remaining time budget:

1. Track average iteration duration from training_time_s values.
2. If remaining time < 1.5× average iteration time, **checkpoint the current best and stop** rather than starting a doomed iteration that will be killed by timeout. The server owns promotion preview/confirm after the session.
3. Prefer quick-mode experiments when time is short — they complete in ~5 min vs ~60 min for full.

## Phase Advancement (server-tracked contract)

> **Why direction has 8 phases (vs. 4 for RL):** supervised classifiers require explicit calibration replay, multi-seed robustness, and inference-parity validation before serving — each is a separate phase so the UI can show per-gate progress. RL doesn't need these because walk-forward economic replay is built into RL training; one validation phase covers it.

The orchestrator tracks your session against an 8-phase plan and refuses to honor `end_turn` while phases remain incomplete and budget is available. Always tag iteration markers with `search_phase: <phase_id>` so the server can attribute work, and emit at least one of the listed evidence keys in `metrics_json` (or its nested `config`) to advance.

| # | Phase ID | Min / Max iters | Evidence keys |
|---|---|---|---|
| 1 | `baseline_capture` | 1 / 3 | (iteration count) |
| 2 | `tabular_sweeps` | 6 / 40 | `tabular_sweep_variant`, `roster_preset`, `direction_pct_threshold`, `deadzone_width`, `calibration_method` |
| 3 | `adaptive_feature_sweeps` | 4 / 30 | `adaptive_features`, `adaptive_feature_version` |
| 4 | `tsfm_sweeps` | 2 / 15 | `tsfm`, `tsfm_adapter`, `tsfm_fallback_validation` |
| 5 | `calibration_replay_gates` | 1 / 8 | `calibration_full_validation`, `economic_replay` |
| 6 | `multi_seed_robustness` | 1 / 6 | `seed_trials`, `n_seed_trials`, `seeds_passed_gates` |
| 7 | `inference_parity_replay` | 1 / 4 | `inference_parity`, `inference_reload_validation` |
| 8 | `promotion_proposal` | 0 / 4 | `promotion_scope` (auto-emitted), `development_promotion_metadata`, `promotion_decision`, … |

`rl_finalist_retraining` is intentionally NOT part of direction research. Direction sessions own direction-only artifacts; downstream RL retraining is the RL autotuner's responsibility.

**Rules:**
- Do not call `end_turn` while any phase is `pending` or `in_progress` and budget remains. The loop guard rejects it and injects a continuation message describing the next action.
- Reaching a phase's `Max iters` ceiling triggers a system nudge to advance. Treat it as a hard signal to emit the evidence key or move on.
- If you believe the plan should terminate early (e.g. baseline is best and further work cannot improve it), reply with a single line beginning `TERMINATE_REQUEST:` followed by structured justification referencing each incomplete phase ID. Do not silently `end_turn`. **An explicit `TERMINATE_REQUEST:` waives incomplete iteration-count phases for promotion** (training/calibration/parity hard gates still run) — silent `end_turn` does not.
- Phase `tabular_sweeps` no longer auto-completes after 2 iterations — it requires either an explicit `tabular_sweep_variant` key or 6+ iterations tagged with `search_phase: tabular_sweeps`.

### Phase 3 (`adaptive_feature_sweeps`) — Accepted-Noop Auto-Inheritance

When adaptive support/resistance and cycle features do not apply to this
instrument/timeframe, `prepare.py` emits
`adaptive_feature_noop_reason: adaptive_features_unavailable` (an **accepted**
noop). The phase advances as soon as **one recorded, completed iteration
tagged `search_phase: adaptive_feature_sweeps`** carries that key — there is
no dwell requirement. **No additional action is needed.**

This noop is **config-invariant**: every config produces the same reason, and
only the already-recorded config produces it. Therefore:
- **Do NOT** re-run the best/baseline config to "re-capture" the evidence — it
  dedups. The server now **auto-inherits** the accepted noop from the prior
  completed iteration on a dedup hit and records a real, phase-tagged
  iteration, so the phase advances on its own.
- **Do NOT** perturb a research-irrelevant knob (e.g. `walkforward_n_folds`)
  solely to escape dedup — that violates the Anti-Waste rules and is
  unnecessary now that inheritance is automatic.

If the phase-cap nudge fires here, it means the evidence is already inherited
on the next recorded iteration; continue with genuine work or move on.

### Phase 4 (`tsfm_sweeps`) — Tabular-Fallback Environments

When `is_tsfm_candidate: False` appears in `prepare.py` output, the training infrastructure has confirmed the tabular fallback path is active. The server automatically records `tsfm_fallback_validation: True` in `metrics_json` for that iteration, which is sufficient to advance the phase. **No additional action is needed** — after the current iteration is recorded, `tsfm_sweeps` advances automatically and the session moves to `calibration_replay_gates`.

If `is_tsfm_candidate: True` appears, a TSFM adapter is available. Set `candidate_family: tsfm` in `train.yaml` and run `prepare.py`; the output will contain `tsfm_adapter` evidence, which also advances the phase.

### Phase 5 (`calibration_replay_gates`) — Auto-Evidence from Training Pipeline

`calibration_full_validation` and `economic_replay` are emitted automatically by `prepare.py` after every training run. **No additional action is needed** — the server records both keys in `metrics_json`, and `calibration_replay_gates` advances after the first iteration completes.

If calibration gates fail repeatedly, the configuration problem should be addressed in `tabular_sweeps` (earlier phase), not by staying in phase 5. Move on; promotion review will surface the calibration issue.

### Phase 6 (`multi_seed_robustness`) — Auto-Evidence from Training Pipeline

`seed_trials`, `n_seed_trials`, and `seeds_passed_gates` are emitted automatically by `prepare.py` after every training run. **No additional action is needed** — the server records a single-seed probe in `metrics_json`, and `multi_seed_robustness` advances after the first iteration completes.

Full multi-seed robustness validation (running N seeds) happens at promotion review, not during autotuner iteration. The autotuner's role here is to confirm the pipeline ran and gates were evaluated.

### Phase 7 (`inference_parity_replay`) — Auto-Evidence from Training Pipeline

`inference_parity` is emitted automatically by `prepare.py` after every training run. **No additional action is needed** — the server records the parity evidence in `metrics_json`, and `inference_parity_replay` advances after the first iteration completes.

The evidence confirms that the training pipeline produced a parity manifest (`parity_metadata`) that aligns feature counts, feature names, and model roster between training and serving. Full inference reload validation happens at promotion review.

### Phase 8 (`promotion_proposal`) — Auto-Evidence from Training Pipeline

`promotion_scope` is emitted automatically by `prepare.py` after every training run. **No additional action is needed** — the server records this key in `metrics_json`, and `promotion_proposal` advances after the first iteration completes.

On session completion, the server runs its own promotion evaluation (`_try_auto_promote`) which validates gates, generates `development_promotion_metadata`, and auto-confirms if all gates pass. The agent does not need to construct or emit promotion metadata manually. `development_promotion_metadata` is built **server-side at promotion time**, not per iteration — do not try to construct it, promote it manually, or re-run the terminal phase to "produce" it.

**STOP when the phase plan is complete.** When the phase state shows every phase `completed` (or you receive an `ALL RESEARCH PHASES ARE COMPLETE` system message), do NOT run another experiment in `promotion_proposal` — it advances after the first completed iteration and further runs only waste budget. Reply with a single line beginning `TERMINATE_REQUEST:` and a one-line justification.

**Act on promotion-readiness warnings.** If the iteration digest shows a `PROMOTION GATE would BLOCK` warning, the listed blockers are model-quality issues your best candidate must fix BEFORE the terminal phase — they are not resolved by re-running `promotion_proposal`. Address each in the relevant earlier phase, e.g.:
- `signal_saturation` — the per-fold signal rate exceeds `max_signal_rate`; lower `max_signal_rate` (e.g. `0.35 → 0.25`) or raise the operating threshold in `tabular_sweeps`, then re-validate.
- `weak_calibration` / `unstable_fold_thresholds` — revisit calibration/threshold settings in `tabular_sweeps`.
Infrastructure blockers (inference reload, smoke validation, signal-health telemetry) are resolved by the server at promotion time — do not try to fix those yourself.
