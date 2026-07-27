# ML RL (PPO) Agent — Knowledge Primer

Domain expertise corpus for the `ml-rl` skill. Loaded by the bootstrap
(`bootstrap.py`) and referenced by the orchestrator's system-prompt assembly.
The feedback loop (ARC-011 P5-027) appends session insights to
`prior_findings/`; this primer is the stable, hand-curated baseline.

## Dependency

**RL tuning depends on direction + volatility models being already trained** —
the RL agent consumes their predictions as observation features. Do not start an
RL session for an instrument whose direction/volatility models are not yet
trained.

## Primary metric

**`mean_oos_sharpe`** (higher is better) — aggregate out-of-sample Sharpe
across walk-forward folds. The critical companion is **`mean_oos_drawdown`**
(lower magnitude is better).

## Walk-forward folds

RL training uses **rolling walk-forward validation** to prevent overfitting.
Each fold trains a fresh PPO agent on a window of past data, skips an embargo
gap (to prevent leakage), and evaluates on the next unseen window. The
aggregate OOS metrics (`mean_oos_sharpe`, `mean_oos_drawdown`, …) are averages
across all folds. A config that works on one regime may fail on another — folds
test across multiple regimes.

## Iteration contract

Modify `train.yaml` hyperparameters (PPO settings, reward weights, environment
config) → run `scripts/autotuner/rl/prepare.py --config <workspace>/train.yaml`
→ keep/discard based on `mean_oos_sharpe` + `mean_oos_drawdown`. Do NOT edit
`prepare.py` itself.

## Key levers

- **Reward shaping** — the reward weight balances (action penalty, drawdown
  penalty, profit reward). The most common RL failure mode is a reward shape
  that causes overtrading or undertrading.
- **PPO hyperparameters** — `ent_coef` (entropy coefficient for exploration),
  `clip_range`, `n_steps`, `batch_size`, `n_epochs`.
- **Fixed settings** — some RL settings are fixed (do NOT modify in train.yaml);
  the bootstrap flags these in the prompt.
