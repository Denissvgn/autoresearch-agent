---
name: rl-autotuner
description: "Autonomous RL agent (PPO) tuning loop — run overnight experiments to improve Sharpe ratio, reduce drawdown, and optimize reward shaping for a specific instrument without human intervention. Use this skill whenever the user wants to: start an autonomous or automatic RL tuning loop, run unattended RL/PPO experiments, auto-tune RL hyperparameters while they sleep, launch autoresearch for RL agents, iterate on RL configs in a loop, optimize reward weights automatically, or says things like 'tune RL agent overnight', 'automate PPO tuning', 'run RL experiments in a loop', 'autotune RL for DOGE', 'start RL autoresearch', 'optimize reward shaping automatically'. IMPORTANT: RL tuning depends on direction + volatility models being already trained — the RL agent consumes their predictions as observation features. Also trigger when the user asks to 'fix the agent that barely trades', 'get the agent to actually trade overnight', 'sweep entropy coefficients and clip ranges automatically', 'reduce drawdown through automated PPO experiments', 'find stable RL training parameters in a loop', or wants to iterate on RL train.yaml unattended to fix overtrading, undertrading, or negative Sharpe. Even if the user doesn't explicitly say 'autotune' or 'autonomous', trigger this skill if they clearly want the RL/PPO agent improved through multiple unattended experiment iterations — phrases like 'I'll check results tomorrow', 'keep iterating on PPO configs', 'don't stop until morning', 'sweep ent_coef from X to Y', or 'run it while I'm away' all indicate this skill. DO NOT trigger for: single one-off RL training runs, manual step-by-step RL tuning with human-in-the-loop, direction or volatility model tuning (use direction-autotuner or volatility-autotuner), explaining how the PPO reward function works, diagnosing specific bad trades in production, promoting RL configs to production, deploying RL models to containers, or adding new observation features to the agent."
argument-hint: "Instrument and optional tag (e.g., 'DOGE_USDT 15m', 'BTC_USDT start RL autotuning', 'DOGE_USDT rl-mar28')"
---

# RL Agent Autotuner Loop

Autonomous experiment loop for improving PPO-based RL agent metrics. You modify `train.yaml` hyperparameters (PPO settings, reward weights, environment config), run experiments via the fixed `prepare.py` harness, and keep/discard based on the primary metric.

## Understanding Walk-Forward Folds

RL training uses **rolling walk-forward validation** to prevent overfitting. Instead of a single train/test split, the data is divided into multiple chronological **folds**. Each fold trains a fresh PPO agent on a window of past data, skips an embargo gap (to prevent data leakage), and evaluates on the next window of unseen data.

- **Why folds matter**: A config that works on one market regime may fail on another. Folds test across multiple regimes. The aggregate OOS metrics (mean_oos_sharpe, mean_oos_drawdown, etc.) are averages across all folds.
- **`folds_passed` (e.g. `3/5`)**: How many individual folds passed per-fold anti-overfit gates. If only 1/5 folds pass, the config is unreliable even if the mean Sharpe looks acceptable.
- **`sharpe_cv`**: Coefficient of variation of Sharpe across folds. High CV (>1.5) means the agent is unstable — it works in some regimes but fails in others.
- **`trading_score`**: Per-fold composite metric (pnl×weight + sharpe×weight - dd×weight) used internally by the RL trainer for model checkpoint selection. Reported in prepare.py output as an additional signal.
- **Quick mode**: 2 folds, 50k timesteps per fold. Good for rapid hypothesis testing.
- **Full mode**: 5 folds, full timesteps. Required for promotion decisions.

### Gate Thresholds (4 gates)

> **ML-56:** Sharpe is annualized with √252 (daily convention). Typical good OOS Sharpe: 0.05–0.30. Per-fold gates use `min_oos_sharpe: 0.05`.

All 4 gates must pass for `all_gates_passed: true`:
1. `min_mean_oos_sharpe: 0.0` — Mean OOS Sharpe must be non-negative
2. `max_sharpe_cv: 2.0` — Cross-fold Sharpe stability
3. `min_folds_passed_ratio: 0.5` — At least 50% of folds must individually pass per-fold gates
4. `max_mean_oos_drawdown: 0.25` — Mean drawdown must be below 25%

The primary metric is **`composite_rl_score`** (higher is better), a weighted combination of:

- **mean_oos_sharpe (×1.0)**: Risk-adjusted return quality across walk-forward folds. The core signal.
- **mean_oos_return (×0.5)**: Absolute PnL. Prevents degenerate configs with good ratio but negligible profit.
- **mean_oos_drawdown (×2.0, penalty)**: Max drawdown severity. Strongly penalizes risky strategies that achieved Sharpe through luck during calm periods.
- **sharpe_cv (×0.1, penalty)**: Cross-fold Sharpe coefficient of variation. Penalizes configs that are unstable across market regimes — a model with high mean Sharpe but wildly different per-fold performance gets discounted.

Formula: `composite = 1.0×sharpe + 0.5×return - 2.0×drawdown - 0.1×sharpe_cv`

This ensures the composite ranking naturally aligns with fold gate pass rates: a config that passes all folds (stable) is preferred over one that has a slightly better mean but fails half its folds (unstable).

### Per-Fold Anti-Overfit Gates

Each fold runs 7 independent gates. ALL must pass for that fold to count as "passed":
1. **position_diversity**: mean |position| < 0.90
2. **flip_minimum**: ≥ 3 direction flips (**auto-passed in stock mode** — long-only agents cannot flip)
3. **max_drawdown**: < 25%
4. **trade_count**: ≥ 20 trades (raw episode total)
5. **trades_per_day**: between 2 and 50% of bars/day (ML-64: physically bounded, timeframe-invariant)
6. **oos_sharpe**: ≥ 0.05 (daily annualization)
7. **is_oos_ratio**: IS/OOS return ratio < 3.0 (overfitting check)

The prepare.py output now includes per-fold gate details showing WHICH gates failed in WHICH fold, so you can diagnose whether a fold failure is structural (e.g. flip gate in stock mode) or performance-related.

### Parameter → Metric Impact Map

| Parameter | Sharpe | PnL | Drawdown | Notes |
|-----------|:------:|:---:|:--------:|-------|
| `learning_rate` | **YES** | **YES** | **YES** | Affects convergence quality — all metrics move |
| `total_timesteps` | **YES** | **YES** | **YES** | More training → potentially better policy |
| `reward_weights.pnl` | moderate | **YES** | moderate | Directly shapes PnL-seeking behavior |
| `reward_weights.sharpe` | **YES** | moderate | **YES** | Risk-adjusted objective → improves ratio AND drawdown |
| `reward_weights.dd_increment` | moderate | moderate | **YES** | Directly shapes drawdown avoidance |
| `ent_coef` | moderate | **YES** | moderate | Exploration → more trades → more PnL (or more risk) |
| `clip_range` | **YES** | moderate | **YES** | Conservative updates → more stable policy |
| `reward_weights.flip/trade` | moderate | **YES** | moderate | Controls turnover → affects fee drag on PnL |
| `gamma` | **YES** | moderate | moderate | Discount factor → how far ahead agent looks |
| `vdmc_params.alpha` | **YES** | moderate | moderate | Trend coefficient → affects signal quality, triggers re-enrichment |
| `vdmc_params.beta` | moderate | **YES** | moderate | Amplitude/momentum coefficient → affects entry timing |
| `vdmc_params.kernel_sigma` | moderate | moderate | **YES** | Smoothing → noisier vs smoother signal, triggers re-enrichment |
| `vdmc_params.lookback_period` | **YES** | moderate | moderate | Window size → short-term vs long-term signal, triggers re-enrichment |

## Prerequisite: Direction + Volatility Models

The RL agent uses `direction_proba` and `volatility_proba` as observation features. If those models are poor (random AUC), the RL agent has no useful signal to work with. Always tune direction and volatility first.

Verify predictive models exist:
```bash
cat /app/workspace/configs/instrument_configs/<INSTRUMENT>_<TIMEFRAME>.yaml
# direction_overrides should be non-empty
# volatility_overrides should be non-empty (or at minimum, direction should be tuned)
```

## Setup

### 1. Initialize workspace

```bash
cd /app/workspace && .venv/bin/python scripts/autotuner/setup.py --instrument <INSTRUMENT> --timeframe <TIMEFRAME> --models rl
```

Creates `runs/autotuner/<INSTRUMENT>_<TIMEFRAME>/rl/` with pre-populated `train.yaml` from the existing RL production config (or defaults).

In autoresearch sessions, run the setup command exactly as supplied by the server prompt. Do not add reset flags manually; fresh-session cleanup and continuation behavior are server-owned.

### 2. Enrich RL dataset (Step 0)

**CRITICAL**: Before any RL training, enrich the dataset with real direction/volatility model predictions. Without this, the RL agent trains on synthetic price-momentum proxies instead of real model signals — a train/serve parity gap.

```bash
cd /app/workspace && .venv/bin/python scripts/autotuner/enrich_rl_dataset.py \
    --instrument <INSTRUMENT> --timeframe <TIMEFRAME> --data-source data-ingest \
    --config runs/autotuner/<INSTRUMENT>_<TIMEFRAME>/rl/train.yaml
```

This scores raw OHLCV data using the promoted direction and volatility models (or their OOF predictions) and writes an enriched parquet to `runs/autotuner/<INSTRUMENT>_<TIMEFRAME>/rl/enriched_<INSTRUMENT>_<TIMEFRAME>.parquet`. VDMC params are read from `train.yaml`'s `vdmc_params:` section.

A `vdmc_params_used.json` marker is written alongside the parquet. When you later change `vdmc_params` in `train.yaml`, `prepare.py` compares the marker to detect changes and **auto-re-enriches** before training. You do NOT need to manually re-run enrichment after VDMC param changes.

### 3. Read context files

Use read_file on:

- `scripts/autotuner/rl/README.md` — RL knobs, ranges, strategy
- `runs/autotuner/<INSTRUMENT>_<TIMEFRAME>/rl/train.yaml` — Current config

If the loaded `train.yaml` already includes `reward_curriculum` or `vdmc_params`, preserve them for the initial reproduction run. They are part of the tuned production baseline, not boilerplate to replace.

### 4. Enable reward curriculum (RECOMMENDED DEFAULT)

**Always enable reward curriculum before the baseline run** unless it's already enabled in the loaded config. If the promoted baseline already contains a curriculum, keep that exact curriculum for the baseline reproduction run. Do NOT overwrite a tuned production curriculum with the generic default below. The curriculum automates the explore→shape→harden progression that produces better-converged agents than static reward weights:

- **Explore** (0–50k steps): High PnL weight, near-zero penalties → agent learns to trade actively
- **Shape** (50k–100k steps): Moderate penalties introduced → agent learns fee/risk awareness
- **Harden** (100k–end): Full production reward weights → agent optimizes for final objective

The curriculum uses **absolute step boundaries** (`until_step`) for explore and shape so these phases get identical training regardless of whether you run quick (100k) or full (500k) mode. Only harden stretches with `total_timesteps`.

Add this to `train.yaml` using write_file if not already present:

```yaml
reward_curriculum:
  enabled: true
  interpolation: linear
  stages:
    - name: explore
      until_step: 50000
      weights: {pnl: 2.0, risk: 0.0001, dd_increment: 0.005, leverage: 0.0001, flip: 0.0002, trade: 0.0005, hold: 0.0002, sharpe: 0.0}
    - name: shape
      until_step: 100000
      weights: {pnl: 1.5, risk: 0.0003, dd_increment: 0.02, leverage: 0.0003, flip: 0.0008, trade: 0.0015, hold: 0.0008, sharpe: 0.3}
    - name: harden
      until_pct: 1.0
      weights: null
```

The `harden` stage's `weights: null` means it falls back to the top-level `reward_weights:` section — so tuning `reward_weights` in the experiment loop still controls the final policy objective.

> **Why curriculum by default?** Without it, the agent must simultaneously learn to trade AND manage risk from step 1 — often converging to "do nothing" as the safe policy. Curriculum gives a structured ramp that avoids this local minimum.

> **Why `until_step` instead of `until_pct`?** Percentage-based boundaries scale with `total_timesteps`, so quick mode (100k) gets only 10k harden steps while full mode (500k) gets 100k — a 10× difference that causes full-mode agents to overtrain on penalties. Absolute steps keep explore and shape fixed at 50k each regardless of total budget.

### 5. Establish baseline

```bash
cd /app/workspace && .venv/bin/python scripts/autotuner/rl/prepare.py \
    --config runs/autotuner/<INSTRUMENT>_<TIMEFRAME>/rl/train.yaml --quick
```

If this workspace was seeded from a promoted production config, do one **full-mode reproduction run** before discarding that baseline. Quick mode can invert the ranking of good full-mode configs, so a negative quick baseline is not enough evidence to abandon the promoted starting point.

The orchestrator auto-detects results from the `---` block in prepare.py output. You do NOT need to grep, parse metrics, or log to `results.tsv`.

Copy the config as your checkpoint:
```bash
cp runs/autotuner/<INSTRUMENT>_<TIMEFRAME>/rl/train.yaml \
   runs/autotuner/<INSTRUMENT>_<TIMEFRAME>/rl/best_train.yaml
```

### 6. Architecture Sweep (MANDATORY before reward tuning)

**Before fine-tuning reward weights, you MUST try at least 3 different architecture configurations.** Architecture has the highest impact on RL agent quality but is almost never searched. Run each config in quick mode:

**Sweep configs** (try these IN ORDER, each as a separate iteration):

| Config | `net_arch_pi` | `net_arch_vf` | `n_envs` | `n_steps` | Notes |
|--------|---------------|---------------|----------|-----------|-------|
| A (small) | `[64, 64]` | `[64, 64]` | 2 | 2048 | Fast training, often sufficient |
| B (medium) | `[128, 128]` | `[128, 128]` | 4 | 2048 | Good capacity, moderate cost |
| C (large) | `[256, 128]` | `[256, 128]` | 4 | 4096 | Higher capacity, more stable gradients |
| D (deep) | `[256, 128, 64]` | `[256, 128, 64]` | 4 | 4096 | Deep network, most capacity |

For each architecture config:
1. Write the architecture params + `n_envs` + `n_steps` to `train.yaml` (keep reward weights from baseline)
2. Run `prepare.py --quick`
3. Record the composite score

After the sweep, **pick the architecture that scored best** and use it for all subsequent reward tuning. Copy the winning architecture to `best_train.yaml`.

> **Why architecture first?** Reward weight tuning is meaningless if the network can't represent a good policy. A [64,64] network with perfect reward weights beats a [256,128] network with bad rewards — but a [256,128] with tuned rewards beats both. You need to find the right capacity first.

> **n_envs matters**: Use at least `n_envs: 2` (preferably `n_envs: 4`). More parallel envs = more diverse experience per rollout = more stable gradients. The production config uses `n_envs: 4` — training with `n_envs: 1` creates a train/serve behavior gap.

### 7. Begin the reward tuning loop

## HPO-Accelerated Workflow (ML-59)

When the research session is started with `enable_hpo: true`, use a **3-phase approach** that combines Optuna Bayesian HPO screening with LLM-guided refinement for faster convergence.

### Phase 1: Optuna HPO Screening

Run a broad hyperparameter search using Optuna's TPE sampler with MedianPruner early stopping:

```bash
cd /app/workspace && .venv/bin/python scripts/autotuner/rl/prepare.py \
    --config runs/autotuner/<INSTRUMENT>_<TIMEFRAME>/rl/train.yaml \
    --hpo --hpo-trials 20 --hpo-timesteps 50000
```

Key flags:
- `--hpo`: Enables HPO mode — calls the rl-trainer's admin tuning API
- `--hpo-trials N`: Number of Optuna trials (default 20). More trials = better coverage but longer runtime.
- `--hpo-timesteps N`: Training timesteps per trial (default 50000). Lower = faster screening but noisier signal.

The output includes a `---` block with `mode: hpo_study` containing the top-3 trial configs ranked by composite_rl_score. A `hpo_results.json` file is also written to the workspace with full trial details.

**Expected runtime**: 60-120 minutes for 20 trials with 50k timesteps each.

### Phase 2: Validate Top-K Configs

The HPO screening used short timesteps for speed. Now validate the best configs with full walk-forward evaluation:

1. Read `hpo_results.json` to get the top-3 parameter configs
2. For each config:
   a. Write the trial's params into `train.yaml` (learning_rate, ent_coef, clip_range, etc.)
   b. Run full walk-forward: `python prepare.py --config train.yaml`
   c. If `all_gates_passed` and composite is best → copy to `best_train.yaml`
3. After validating all top-K, refine the winner using the diagnostic playbook below (especially reward_weights, which HPO doesn't search by default)

### Phase 3: Robustness Validation

The preferred method is to set `n_seed_trials: 3` in `train.yaml` (ML-65). This trains 3 seeds per fold automatically and selects the median-Sharpe result. The prepare.py output includes `seeds=X/Y` per fold showing how many seed trials passed gates.

```yaml
# Add to train.yaml for automatic multi-seed validation
n_seed_trials: 3
```

Then run normally:
```bash
cd /app/workspace && .venv/bin/python scripts/autotuner/rl/prepare.py \
    --config runs/autotuner/<INSTRUMENT>_<TIMEFRAME>/rl/best_train.yaml
```

The per-fold output will show seed trial details:
```
fold_1:          PASS sharpe=0.1200 ... seeds=3/3 trial_sharpes=['0.0800', '0.1200', '0.1500']
```

If `seeds_passed_gates < 2/3` on most folds, the config is seed-sensitive. Fix the gradient dynamics (see "Seed Sensitivity" section below) rather than picking winning seeds.

> **Note**: `n_seed_trials: 3` triples training time per fold. Use it for validation/promotion runs, not rapid exploration iterations. For quick-mode screening, keep `n_seed_trials: 1` (the default).

Alternatively, you can manually validate with different seeds:
```bash
cd /app/workspace && .venv/bin/python scripts/autotuner/rl/prepare.py \
    --config runs/autotuner/<INSTRUMENT>_<TIMEFRAME>/rl/best_train.yaml --seed 43
cd /app/workspace && .venv/bin/python scripts/autotuner/rl/prepare.py \
    --config runs/autotuner/<INSTRUMENT>_<TIMEFRAME>/rl/best_train.yaml --seed 44
```

If composite_rl_score varies >30% across seeds, the config is probably overfitting to training noise. Consider:
- Lower learning rate + more timesteps
- Tighter clip_range for more conservative updates
- More n_steps for better gradient estimates

### When to Use HPO vs. Manual Loop

| Scenario | Approach |
|----------|----------|
| Starting from scratch, no baseline | HPO Phase 1 → validate → refine |
| Have a working config, want marginal gains | Manual loop with diagnostic playbook |
| Stuck after 5+ manual iterations | HPO to explore different regions |
| Time budget > 3 hours | HPO is worth the upfront cost |
| Time budget < 2 hours | Manual loop with quick mode |

## The Experiment Loop

### LOOP FOREVER:

**Step 1 — Understand the state.**
Read `train.yaml` and (if exists) `results.json`. What's the current Sharpe? How many trades? What's the drawdown? Is the agent trading or sitting flat?

**Step 2 — Form a hypothesis.**
Pick ONE parameter to change based on the diagnostic below.

**Step 3 — Edit `train.yaml`.**
Use write_file. Change the parameter under the appropriate section (`training:`, `reward_weights:`, `environment:`).

**Step 4 — Run.**
```bash
cd /app/workspace && .venv/bin/python scripts/autotuner/rl/prepare.py \
    --config runs/autotuner/<INSTRUMENT>_<TIMEFRAME>/rl/train.yaml
```

The orchestrator auto-records the iteration from the `---` output block.

**Step 5 — Keep or discard.**

Check the `---` output from prepare.py:

If `primary_metric` (composite_rl_score) improved AND `all_gates_passed: true`:
- **KEEP**: Copy `train.yaml` → `best_train.yaml`.

If worse:
- **DISCARD**: Restore from `best_train.yaml`.

**TIP**: After discarding, check which component moved:
- If `mean_oos_sharpe` improved but `mean_oos_drawdown` got worse → the config is riskier, not better.
- If `mean_oos_return` improved but `mean_oos_sharpe` dropped → more PnL through more risk, not more edge.
- If `mean_oos_drawdown` improved but `mean_oos_sharpe` dropped → agent became too conservative.
- If `folds_passed` dropped (e.g. `3/5 → 2/5`) even though mean Sharpe improved → the improvement came from fewer folds performing well (less robust).
- Ideal: `mean_oos_sharpe` AND `mean_oos_return` improve, `mean_oos_drawdown` stays stable or decreases, and `folds_passed` stays same or improves.
  ```bash
  cp runs/autotuner/<INSTRUMENT>_<TIMEFRAME>/rl/best_train.yaml \
     runs/autotuner/<INSTRUMENT>_<TIMEFRAME>/rl/train.yaml
  ```

**Step 6 — Next hypothesis.** Return to Step 1.

### Full Mode Validation Checkpoints

**After every 8-10 quick-mode iterations** (or when you find a config with `composite > -0.05` and `folds_passed ≥ 1/2`), run a **full mode validation** of the current `best_train.yaml`:

```bash
cd /app/workspace && .venv/bin/python scripts/autotuner/rl/prepare.py \
    --config runs/autotuner/<INSTRUMENT>_<TIMEFRAME>/rl/best_train.yaml
```

If full mode fails (composite drops significantly vs quick mode), the config is overfitting to the 2-fold quick setup. In that case:
1. **Increase n_steps** (2048 → 4096) — more stable gradient estimates
2. **Lower n_epochs** (10 → 5) — less overfitting per rollout
3. **Lower learning_rate** by 2× — calmer policy updates
4. **Keep n_envs ≥ 4** — more diverse experience
5. Resume quick-mode tuning with these adjusted stability params

Do NOT wait until the last few iterations to try full mode — it should be an early diagnostic, not a final gate.

## Strategy Playbook

RL tuning is different from supervised models — the agent's behavior emerges from the interaction between reward signal, exploration, and policy capacity. Changes can have non-linear and sometimes counterintuitive effects.

### Diagnostic: What's Wrong?

| Symptom | Root Cause | Go To |
|---------|-----------|-------|
| Agent barely trades (< 5 trades) | Under-exploration or over-penalized trading | Phase 1 |
| Agent overtrades (> 200 trades) | Over-exploration or under-penalized flipping | Phase 2 |
| Negative Sharpe | Bad signal, wrong reward balance, or too aggressive | Phase 3 |
| Good Sharpe but huge drawdown | Missing risk controls | Phase 4 |
| Unstable across folds (sharpe_cv > 1.5) | Policy instability or overfitting | Phase 5 |
| PPO/rewards tuned but plateaued | VDMC indicator params may be suboptimal | Phase 6 |

### Phase 1: Agent Not Trading

The agent has learned that doing nothing is safest. Since curriculum should already be enabled (see Setup step 4), the explore stage should prevent this. If the agent still isn't trading with curriculum enabled, the explore-stage weights need adjustment:

| Experiment | Change | Why |
|-----------|--------|-----|
| Extend explore phase | `explore.until_step: 50000 → 75000 → 100000` | Give the agent more time in pure-PnL mode before penalties kick in. |
| Boost explore PnL | `explore.weights.pnl: 2.0 → 3.0 → 5.0` | Stronger profit motive in explore phase. |
| Reduce shape penalties | `shape.weights.trade: 0.0015 → 0.0005` | Softer penalty transition so agent doesn't revert to inaction. |

If curriculum adjustments don't help, try these PPO-level overrides:

| Experiment | Change | Why |
|-----------|--------|-----|
| More entropy | `ent_coef: 0.02 → 0.03 → 0.05` | Forces more random exploration, prevents convergence to inaction. |
| Less trading penalty | `reward_weights.trade: 0.002 → 0.001 → 0.0005` | Removes the disincentive to trade. |
| Less flip penalty | `reward_weights.flip: 0.001 → 0.0005 → 0.0` | Allows position changes without penalty. |
| Stronger PnL signal | `reward_weights.pnl: 1.0 → 2.0 → 3.0` | Makes profit motive louder than penalties. |
| More SDE noise | `delta_max: 0.08 → 0.12 → 0.15` | Larger exploration noise in state-dependent exploration. |

### Phase 2: Agent Overtrading

The agent flips positions too often, getting destroyed by fees and slippage.

| Experiment | Change | Why |
|-----------|--------|-----|
| Higher flip penalty | `reward_weights.flip: 0.001 → 0.003 → 0.005` | Directly penalizes position changes. |
| Higher trade penalty | `reward_weights.trade: 0.002 → 0.005 → 0.01` | Penalizes every trade action. |
| Less entropy | `ent_coef: 0.02 → 0.01 → 0.005` | Less random exploration → more deliberate actions. |
| Less SDE noise | `delta_max: 0.08 → 0.05 → 0.03` | Quieter exploration. |

### Phase 3: Negative Sharpe

The agent trades but loses money. First check if direction/volatility models are good enough.

| Experiment | Change | Why |
|-----------|--------|-----|
| More training budget | `total_timesteps: 500000 → 750000 → 1000000` | Agent may not have converged yet. **Full mode only — capped at 50k in quick mode.** |
| Lower learning rate | `learning_rate: 0.0005 → 0.0003 → 0.0001` | Calmer updates, less overshooting. |
| Sharpe reward boost | `reward_weights.sharpe: 0.5 → 1.0 → 1.5` | Explicit risk-adjusted objective signal. |
| Drawdown penalty | `reward_weights.dd_increment: 0.03 → 0.05 → 0.08` | Penalizes losing streaks more heavily. |
| Tighter KL | `target_kl: 0.02 → 0.01 → 0.005` | Prevents large policy jumps that destroy learned behavior. |

### Phase 4: Good Sharpe, Bad Drawdown

The agent is profitable on average but has dangerous losing streaks.

| Experiment | Change | Why |
|-----------|--------|-----|
| Heavier drawdown penalty | `reward_weights.dd_increment: 0.03 → 0.06 → 0.10` | Directly penalizes drawdown increments. |
| Position risk penalty | `reward_weights.risk: 0.0005 → 0.001 → 0.002` | Penalizes large position sizes. |
| Leverage penalty | `reward_weights.leverage: 0.0005 → 0.001` | Reduces leverage tendency. |
| Tighter clip range | `clip_range: 0.20 → 0.15 → 0.10` | More conservative policy updates. |

### Phase 5: Unstable Across Folds

High variance in Sharpe across walk-forward folds means the policy isn't robust. Diagnose by reading `folds_passed: X/Y` and `sharpe_cv` from the `---` output:

- `folds_passed: 1/5` with positive mean Sharpe → one lucky fold is masking four bad ones. The config is unreliable.
- `folds_passed: 4/5` with `sharpe_cv > 1.5` → most folds work but one outlier fold dominates variance. Usually a regime mismatch.
- `sharpe_cv < 0.5` → very stable across folds. Good sign.
- `std_oos_sharpe` > `mean_oos_sharpe` → the mean is noise, not signal.

| Experiment | Change | Why |
|-----------|--------|-----|
| More timesteps | `total_timesteps: 500000 → 1000000` | More data per fold for convergence. **Full mode only — capped at 50k in quick mode.** |
| Larger rollout | `n_steps: 2048 → 4096` | More stable gradient estimates per update. |
| Linear LR decay | `lr_schedule: linear`, `lr_end: 0.0001` | Gradual LR reduction stabilizes late training. |
| Tighter KL | `target_kl: 0.02 → 0.01` | Prevents destructive policy updates. |
| Fewer epochs | `n_epochs: 10 → 5` | Less data reuse → less overfitting per rollout. |

### Phase 6: VDMC Indicator Tuning

The VDMC wave-function indicator generates 9 observation features. Default params may not be optimal for every instrument. `prepare.py` auto-detects parameter changes and re-enriches the dataset before training.

| Experiment | Change | Why |
|-----------|--------|-----|
| Sharper trend signal | `vdmc_params.alpha: 1.2 → 2.0 → 3.0` | Higher trend sensitivity. May help dull-range instruments. |
| Lower trend sensitivity | `vdmc_params.alpha: 1.2 → 0.6 → 0.3` | Less trend noise for choppy markets. |
| Stronger momentum | `vdmc_params.beta: 0.8 → 1.5 → 2.5` | Amplifies amplitude/momentum component. |
| Smoother signal | `vdmc_params.kernel_sigma: 5 → 9 → 15` | Wider Gaussian → smoother VDMC signal, less HF noise. |
| Longer memory | `vdmc_params.lookback_period: 120 → 360 → 720` | Longer smoothing window. Better for slower instruments. |
| More/less amplitude | `vdmc_params.amplitude_scaling: 1.0 → 2.0` or `→ 0.5` | Amplifies or dampens overall VDMC signal magnitude. |

> **Cost**: Changing VDMC params forces re-enrichment (~30-60s). Tune PPO/reward params first, then sweep VDMC.

### Combining Improvements

After finding individual winners, combine them. Common winning combos:
- Lower LR + higher timesteps + linear schedule (stability)
- Moderate entropy + moderate flip penalty (balanced exploration)
- Sharpe reward + drawdown penalty (risk-aware objective)

## Quick vs. Full Mode

- **Quick** (`--quick`): 2 folds, 50k timesteps. ~5-10 min. **This is the default mode.**
- **Full** (no `--quick`): Full folds, full timesteps. ~30-90 min. Required for server promotion review.

Quick mode is enabled by default for faster iteration. Only switch to full mode when you have a candidate worth validating for server promotion review.

> **Important: `total_timesteps` is hard-capped at 50,000 in quick mode.** Changing `total_timesteps` in train.yaml has NO effect during quick-mode runs — prepare.py silently caps it. Do not waste iterations tuning `total_timesteps` while in quick mode. Set the desired value in train.yaml before your full-mode validation run, where the cap does not apply.

### Choosing `total_timesteps` for Full Mode (Overfitting Prevention)

A fixed `total_timesteps` (e.g. 500k) is NOT safe across all instruments. Different instruments have different data history lengths, which means the same timestep count can be fine for one instrument but cause severe overfitting on another.

**Auto-calculation:** When `total_timesteps` is not explicitly set in `train.yaml`, `prepare.py` auto-calculates it as `wf_train_bars × 30` (~30 data passes, the sweet spot). For the default `wf_train_bars=8640` this yields **259,200** timesteps. You can override by explicitly setting `total_timesteps` in the training section.

**Per-fold proportional scaling (enabled by default):** Each fold automatically scales its timesteps to `len(train_data) × 30.0`, clamped to `[30k, 350k]`. This prevents overfitting when training data is small and under-training when it's large. Control via `wf_proportional_timesteps`, `wf_timesteps_multiplier`, `wf_timesteps_floor`, `wf_timesteps_cap` in train.yaml.

**The overfitting math:** Each PPO episode uses `max_episode_steps` bars (default: 4096) from the training window (`wf_train_bars`, default: 8640). The number of data passes is:

```
data_passes ≈ total_timesteps / wf_train_bars
```

| Data Passes | Risk Level | Recommendation |
|-------------|-----------|----------------|
| < 15 | Under-trained | Increase timesteps or decrease `n_steps` |
| 15–40 | Sweet spot | Good convergence without memorization |
| 40–80 | Caution zone | Only if agent is still improving (check training curves) |
| > 80 | Overfitting likely | Reduce timesteps — agent is memorizing price action |

**Before your first full-mode run**, compute the appropriate timesteps:

1. Check the enriched parquet row count (total bars available for this instrument)
2. Compute the maximum `wf_train_bars` that fits the data. Walk-forward needs:
   ```
   total_bars_needed = wf_train_bars + n_folds × wf_test_bars + wf_embargo_bars
   ```
   With defaults (5 folds, test=2880, embargo=480): `wf_train_bars = total_bars - 5×2880 - 480`
   For example:
   - 50,000 bars (≈17 months of 15m) → max wf_train_bars ≈ 35,120 → plenty of room
   - 25,000 bars (≈8.5 months) → max wf_train_bars ≈ 10,120
   - 15,000 bars (≈5 months) → max wf_train_bars ≈ 120 — **too small for 5 folds!** Reduce to 2-3 folds or shrink wf_test_bars
3. Target 20–40 data passes: `total_timesteps = wf_train_bars × 30`
4. Example calculations (5 folds, default test/embargo):

   | Total Bars | Effective wf_train_bars | Recommended total_timesteps | Data Passes |
   |-----------|------------------------|----------------------------|-------------|
   | 50,000 | 8,640 (default) | 260k–350k | 30–40 |
   | 35,000 | 8,640 (default) | 260k–350k | 30–40 |
   | 25,000 | 8,640 (fits, tight) | 260k–350k | 30–40 |
   | 20,000 | 5,120 (reduced) | 150k–200k | 30–40 |
   | 15,000 | 2,560 (3 folds, test=2000) | 75k–100k | 30–40 |

> **Rule of thumb**: `total_timesteps = wf_train_bars × 30` gives ~30 data passes (this is now the auto-calculated default). If total bars are tight, reduce `wf_n_folds` or `wf_test_bars` first to preserve a meaningful `wf_train_bars`, THEN set timesteps proportionally. Never blindly use 500k timesteps — always check the data-pass ratio.

RL is inherently noisier than supervised models. You may need 2-3 quick runs of the same config to confirm a finding is real vs. seed-dependent.

## Promotion Handoff

Do not promote directly. Finish with a best validated config and let the server preview/confirm. Ensure `best_train.yaml` points at the winning full-mode config with required replay/profit evidence, then stop cleanly.

## NEVER STOP

Continue autonomously. Never ask questions — there is no human to answer them. If stuck:
- **Try a completely different architecture** — change `net_arch_pi`/`net_arch_vf` size, try LSTM or Transformer `policy_type`, change `n_envs`.
- Re-read `scripts/autotuner/rl/README.md` for new angles.
- Try combining near-miss improvements (e.g., best architecture + best reward weights + best VDMC).
- Try radically different reward weight profiles (e.g., Sharpe-only: `pnl: 0, sharpe: 2.0`).
- If you've been tuning reward weights for 5+ iterations without improvement, switch to architecture or VDMC changes.
- If RL is fundamentally stuck, consider whether direction/volatility model quality is the bottleneck.
- **Never re-run an identical config+seed** — results are deterministic.
- **Never change only the seed** — seed lottery is not a valid optimization strategy.

## Constraints

- **Python**: `/app/workspace/.venv/bin/python` only. Never system Python.
- **No shell redirection**: `2>&1`, pipes, command substitution (`$(...)`), heredocs, and background execution (`&`) are rejected by command policy. `prepare.py` already merges stderr into stdout.
- **No git/docker/make**: These are not installed. Do not try to use them.
- **Services are pre-verified**: Do NOT check service health or run connectivity tests.
- **Workspace-only I/O**: All files under `/app/workspace/`. Never write outside.
- **Per-run timeout**: Quick ~10 min, Full ~90 min. Kill if 2x over.
- **Bash timeout**: The bash tool defaults to 7200s (2h). You can pass `timeout_s` to override it. For quick-mode runs, `timeout_s: 1800` is sufficient. For full-mode runs, keep the default or set `timeout_s: 7200`. Minimum enforced: 900s.
- **Simplicity**: Simpler config with same Sharpe → keep simpler.
- **Seed sensitivity**: RL is stochastic. Validate surprising results with a second run.
- **Fully autonomous**: NEVER ask questions. NEVER say "should I...?". There is no human. Make all decisions yourself using your best judgment. When in doubt, choose the action most likely to improve metrics.
- **No identical re-runs**: Same config+seed → same result. Always change at least one meaningful parameter.
- **No seed-only changes**: Changing seed without changing anything else is not optimization. If a config only works with one seed, it is not robust.
- **Minimum change magnitude**: Make meaningful changes. Do not nudge parameters by <20%. Jump to qualitatively different values (e.g., trade_penalty 0.005 → 0.015, not 0.005 → 0.006).
- **Architecture diversity required**: You MUST try at least 3 different `net_arch_pi`/`net_arch_vf` sizes before declaring the search stuck. Reward tuning without architecture search is incomplete.

## Don't Waste Iterations

`composite_rl_score = 1.0×sharpe + 0.5×return − 2.0×drawdown − 0.1×cv` — every knob affects it, so the failure mode here is not "no-op dimensions" but "low-leverage tweaks". Skip these patterns:

- **Seed-only changes** — same config + new seed gives no information about the config. If a result only works with one seed, it is not promotable.
- **Sub-20% parameter nudges** — `trade_penalty: 0.005 → 0.006` produces noise, not signal. Jump to a qualitatively different value (`0.005 → 0.015`) or move to a different parameter.
- **Reward-weight tuning before architecture** — `[64,64]` with tuned rewards loses to `[256,128]` with tuned rewards. Step 6 (Architecture Sweep) is MANDATORY before any reward-coefficient work.
- **HPO repeats on a converged trial space** — once Optuna's top-3 are validated, further HPO trials over the same bounds yield diminishing returns; switch to manual refinement of the winner.

When stuck for 5+ iterations with no improvement, switch dimensions (architecture → VDMC → reward shape → curriculum).

## Time Budget Awareness

The session has a finite wall-clock timeout (user-configurable, typically 2-4h). `prepare.py` prints periodic `[prepare] Training in progress... Xm elapsed` lines during long runs. After each iteration completes, estimate your remaining time budget:

1. Track average iteration duration from training_time_s values.
2. If remaining time < 1.5× average iteration time, **checkpoint the current best and stop** rather than starting a doomed iteration that will be killed by timeout. The server owns promotion preview/confirm after the session.
3. Prefer quick-mode experiments when time is short.

## Phase Advancement (server-tracked contract)

> **Why RL has 4 phases (vs. 8 for direction/volatility):** RL validation uses walk-forward economic replay built into PPO training — a single `validation` phase covers what supervised models split across calibration, multi-seed, and inference-parity phases. The per-fold gates inside PPO already enforce the same constraints (Sharpe stability, drawdown, OOS performance).

The orchestrator tracks your session against a 4-phase plan and refuses to honor `end_turn` while phases remain incomplete and budget is available. Always tag iteration markers with `search_phase: <phase_id>` so the server can attribute work.

| # | Phase ID | Min / Max iters | Advancement |
|---|---|---|---|
| 1 | `baseline_capture` | 1 / 3 | Iteration count |
| 2 | `hpo_screening` | 1 / 20 | Iteration count |
| 3 | `validation` | 2 / 10 | Iteration count |
| 4 | `promotion_proposal` | 0 / 4 | `promotion_scope` (auto-emitted), `development_promotion_metadata`, `promotion_decision`, … |

**Rules:**
- Do not call `end_turn` while any phase is `pending` or `in_progress` and budget remains. The loop guard rejects it and injects a continuation message describing the next action.
- Reaching a phase's `Max iters` ceiling triggers a system nudge to advance. Treat it as a hard signal to move on.
- If you believe the plan should terminate early (e.g. direction/volatility signals are too weak for useful RL training), reply with a single line beginning `TERMINATE_REQUEST:` followed by structured justification referencing each incomplete phase ID. Do not silently `end_turn`. **An explicit `TERMINATE_REQUEST:` waives incomplete iteration-count phases for promotion** (training hard gates still run) — silent `end_turn` does not.

### Phase 2 (`hpo_screening`) — Iteration-Count Phase

Tag iterations with `search_phase: hpo_screening` during architecture sweeps and HPO runs. After 1+ tagged iterations the phase advances automatically. If `--hpo` is not being used, manual quick-mode architecture/reward experiments still count — just tag them.

### Phase 3 (`validation`) — Iteration-Count Phase

Tag at least 2 iterations with `search_phase: validation`. These should include at least one full-mode run of your best config. After 2+ tagged iterations the phase advances.

### Phase 4 (`promotion_proposal`) — Auto-Evidence from Training Pipeline

`promotion_scope` is emitted automatically by `prepare.py` after every training run. **No additional action is needed** — the server records this key in `metrics_json`, and `promotion_proposal` advances after the first iteration completes.

On session completion, the server runs its own promotion evaluation (`_try_auto_promote`) which validates gates, generates `development_promotion_metadata`, and auto-confirms if all gates pass. The agent does not need to construct or emit promotion metadata manually.

When all phases are complete and the session has exhausted its useful experiments, call `end_turn`. The server handles the rest.

## System Architecture Notes

These mechanical constraints govern how PPO training actually works in this codebase. Use them to reason about **why** a config fails, not just **what** to change next.

### Margin Mode vs. Stock Mode

**This section is mandatory reading before tuning any margin-mode session.** Margin and stock are fundamentally different environments — the same configs and reward weights that work for stock mode will fail catastrophically in margin mode.

#### Key Differences

| Dimension | Stock mode | Margin mode |
|-----------|-----------|-------------|
| Effective action range | `[0, max_pos=1]` — long-only, shorts clamped to 0 | `[-max_pos=-3, +max_pos=3]` — full long/short |
| Max position (leverage) | 1× balance | 3× balance (default `leverage: 3`) |
| Episode termination | Always at `max_episode_steps` | Can end **early on margin call** (equity wipes to 0) |
| `flip_minimum` gate | **Auto-passed** (long-only, can't flip) | **ACTIVE** — agent must flip direction ≥3 times per episode |
| Drawdown from a wrong bet | ≤ 100% of position | Up to 300% of position (3× leverage) |
| Fee cost per direction flip | 2× fee_bps (sell + buy) | 2× fee_bps but on 3× notional |
| `leverage` reward weight | Irrelevant (no leverage) | **Critical** — controls over-leveraging behavior |

#### Margin Call / Early Episode Termination

In **margin mode**, if the agent takes a large leveraged position on the wrong side and draws down 100% of equity, the episode terminates early. You will see this in `rl-trainer` logs as:

```
📊 Episode done | steps=837  mean|pos|=1.25  flips=1  gross_pnl=-0.91  dd=0.96
📊 Episode done | steps=1027  mean|pos|=1.04  flips=14  gross_pnl=-0.93  dd=0.99
```

Short episodes (`steps << max_episode_steps`) + near-total drawdown = margin call. This means:
- `mean_oos_trades` is lower than expected (episode cut short = fewer trades)
- `mean_oos_drawdown` can appear as ~100% from a single bad leverage bet
- The `folds_passed` metric will be 0 even if Sharpe looks positive in some episodes

**If you see most episodes shorter than `max_episode_steps/2` with `dd > 0.90` → the agent is using unsafe leverage. Increase drawdown and leverage penalties dramatically.**

#### Required Reward Weight Calibration for Margin Mode

In stock mode, default penalties are calibrated for 1× notional exposure. In margin mode, **the same underlying behavior causes 3× more damage** — so penalties need to be proportionally larger:

| Reward weight | Stock mode range | Margin mode range | Why higher? |
|---------------|-----------------|-------------------|-------------|
| `dd_increment` | 0.03–0.10 | **0.20–1.0** | 3× leverage amplifies drawdown 3× |
| `leverage` | 0.0–0.001 | **0.005–0.05** | Actual leverage now exists and must be penalized |
| `risk` (position size) | 0.0001–0.002 | **0.001–0.01** | Large positions have 3× the notional risk |
| `flip` | 0.001–0.01 | **0.003–0.02** | Direction flip closes a leveraged position + opens opposite: 2× fee on 3× notional |

> **Rule**: When transitioning from stock → margin configs, multiply `dd_increment`, `leverage`, and `risk` by ~3×. Leave `pnl` and `sharpe` weights unchanged.

#### Margin-Mode Reward Curriculum

The stock-mode default curriculum explore weights (`dd_increment: 0.005, leverage: 0.0001, risk: 0.0001`) are **unsafe for margin**. Near-zero penalties during explore teach the agent to make reckless leveraged bets — it will then converge to a high-leverage gambling policy.

Use these starting weights for margin mode:

```yaml
reward_curriculum:
  enabled: true
  interpolation: linear
  stages:
    - name: explore
      until_step: 50000
      weights: {pnl: 2.0, risk: 0.002, dd_increment: 0.15, leverage: 0.005, flip: 0.002, trade: 0.001, hold: 0.0002, sharpe: 0.0}
    - name: shape
      until_step: 100000
      weights: {pnl: 1.5, risk: 0.005, dd_increment: 0.30, leverage: 0.01, flip: 0.008, trade: 0.004, hold: 0.0008, sharpe: 0.3}
    - name: harden
      until_pct: 1.0
      weights: null
```

> The explore stage uses `dd_increment: 0.15` and `leverage: 0.005` — still light enough to let the agent explore long/short positions, but strong enough to prevent runaway leveraged losses that would cause margin calls in the very first episodes.

#### Flip Gate in Margin Mode

In stock mode the flip gate (≥3 direction reversals per episode) is **auto-passed** since the agent can only go long. In **margin mode it is ACTIVE**. This means:
- If your `flip` penalty is too high, the agent learns to pick a direction and hold it without flipping → **flip gate failure**
- If your `flip` penalty is too low, the agent churns excessively → **trades_per_day gate failure**
- Recommended range for margin mode `flip` reward weight: `0.002–0.02`

#### Leverage Control via train.yaml

The `leverage` field is settable in `train.yaml`'s `environment:` section. Default is 3× when trading_mode=margin:

```yaml
environment:
  trading_mode: margin
  leverage: 3       # 1–10x; lower = less amplification, safer but less upside
  max_position: 3.0 # Set by rl_config from leverage; override here to cap exposure
  include_margin_observations: true  # Adds 4 obs features: margin_ratio, distance_to_liq, utilization, mode_flag
```

**Tuning leverage level**: Consider trying `leverage: 1` (margin account that can short but without leverage amplification) as a diagnostic step. If the agent performs much better at 1× leverage, it's the leverage amplification (not the shorting capability) causing the drawdown problem.

#### Margin-Mode Diagnostic: Large Drawdown

If `mean_oos_drawdown > 0.30` in margin mode, work through this priority order:

1. **Check for margin calls**: Are most episodes ending before `max_episode_steps`? If yes → agent is getting liquidated. Immediately:
   - `dd_increment: 0.05 → 0.30 → 0.50 → 0.80` (keep going until margin calls stop)
   - `leverage: 0.001 → 0.01 → 0.05`
   - `risk: 0.001 → 0.005 → 0.01`

2. **Check curriculum explore weights**: Are first 50k steps of training producing `dd≈0.9` in IS episodes? If yes → explore weights need much stronger risk controls (see margin curriculum above).

3. **Check max_position**: Is `mean|pos|` in rl-trainer logs consistently > 2.0? Consider adding `max_position: 1.5` to `environment:` to hard-cap exposure during tuning.

4. **Consider lower leverage**: Try `leverage: 1` to isolate whether the shorting ability or the leverage amplification is causing drawdown.

### PPO Gradient Math

Each PPO update collects a rollout buffer, then performs multiple gradient passes over it:

```
rollout_size   = n_steps × n_envs           (default: 2048 × 4 = 8,192 steps)
minibatches    = rollout_size / batch_size   (default: 8192 / 64 = 128)
gradient_passes = minibatches × n_epochs     (default: 128 × 10 = 1,280 per update!)
ppo_updates    = total_timesteps / rollout_size
```

| n_epochs | batch_size | Gradient passes/update | Risk level |
|----------|-----------|----------------------|------------|
| 3 | 64 | 384 | Safe — converges without overshooting |
| 4 | 64 | 512 | Safe |
| 5 | 64 | 640 | Moderate — watch for seed sensitivity |
| 10 | 64 | 1,280 | **Dangerous** — policy can collapse in a single update |
| 10 | 512 | 160 | Safe (larger batch compensates) |

**Rule**: Keep gradient passes per update between 200–600. If `n_epochs` is high, increase `batch_size` proportionally. If you see seed sensitivity or full-mode collapse, **reduce `n_epochs` first** — it's the highest-leverage fix.

### Quick vs Full Mode: The Curriculum Asymmetry

The 3-stage reward curriculum now uses **absolute step boundaries** (`until_step`) for explore and shape stages, solving the original quick/full mode disparity. The harden stage uses `until_pct: 1.0` to fill the remainder:

| Stage | Quick (100k steps) | Full (500k steps) |
|-------|-------------------|-------------------|
| explore (0–50k) | 0–50k | 0–50k |
| shape (50k–100k) | 50k–100k | 50k–100k |
| **harden (100k–end)** | **100k–100k = ~0 steps** | **100k–500k = 400k steps** |

This means quick-mode is effectively explore+shape only, while full-mode gets extensive harden training. When using quick mode for hypothesis testing, be aware the agent hasn't trained under production weights — evaluate full-mode before making promotion decisions.

> **Legacy `until_pct` configs**: If you encounter an older config using `until_pct` instead of `until_step`, it still works (backward compatible). But when creating new experiments, always use `until_step` for explore and shape to avoid the asymmetry problem.

**Diagnostic**: If full-mode trades << quick-mode trades (e.g., 250 vs 1000 per episode), the agent is **overtrained on penalties in the harden stage**. Fix by:
1. Reducing `n_epochs` (10 → 3) to prevent per-update overshooting
2. Reducing `total_timesteps` to limit harden-stage gradient exposure
3. Verify curriculum uses `until_step` (not `until_pct`) for explore/shape stages

### Trade Count Semantics (ML-64)

`mean_oos_trades` is the **total trades per episode**, NOT per day. To convert:

```
bars_per_day = 24 × 60 / bar_interval_minutes    (96 for 15m)
episode_days = max_episode_steps / bars_per_day   (4096/96 ≈ 42.7 days for 15m)
trades_per_day = mean_oos_trades / episode_days
```

The new `trades_per_day` gate enforces physical bounds:
- **Min**: 2 trades/day (agent must actually trade)
- **Max**: 50% of bars/day (48 for 15m, 12 for 1h — prevents churning)

When comparing quick vs full mode trade counts, always normalize to trades/day. Raw episode totals are meaningless across different `max_episode_steps` or mode settings.

### Seed Sensitivity = Gradient Problem, Not Randomness

If a config works with `seed=42` but fails with `seed=43`, the problem is **not** RL stochasticity — it's that the first PPO update performs too many gradient passes on a randomly-initialized network. Bad initial weights that favor "hold" (zero action) get reinforced 1,280 times (with `n_epochs=10, batch_size=64`) before new rollout data can provide a corrective signal.

**Fix priority for seed sensitivity**:
1. `n_epochs: 10 → 3` (reduces first-update gradient passes from 1,280 to 384)
2. `target_kl: 0.02 → 0.01` (tighter trust region stops destructive epochs earlier)
3. `batch_size: 64 → 256` (fewer minibatches = fewer gradient passes per epoch)

Do NOT treat seed sensitivity by running multiple seeds and picking the winner. That's seed lottery, not optimization. Fix the gradient dynamics so all seeds converge to similar policies.

**Automated seed robustness check (ML-65)**: Set `n_seed_trials: 3` in `train.yaml` to train 3 seeds per fold with median-Sharpe selection. The per-fold output shows `seeds=X/3` — if most folds show `seeds=1/3`, the config is fragile. If `seeds=3/3`, the config is robust across seeds. Use this for validation runs (not quick-mode rapid screening, since it triples fold training time).

### VecNormalize Drift Across Folds

Each walk-forward fold creates a fresh `VecNormalize` wrapper. Observation running statistics (`obs_rms`) start from scratch per fold, meaning the agent sees different normalized feature distributions across folds. This is a source of cross-fold instability (`sharpe_cv > 1.5`).

If cross-fold variance is high despite stable reward weights, the root cause may be observation normalization drift rather than reward or architecture problems.
