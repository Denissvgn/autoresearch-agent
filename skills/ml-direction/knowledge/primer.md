# ML Direction Model — Knowledge Primer

Domain expertise corpus for the `ml-direction` skill. Loaded by the bootstrap
(`bootstrap.py`) and referenced by the orchestrator's system-prompt assembly.
The feedback loop (ARC-011 P5-027) appends session insights to
`prior_findings/`; this primer is the stable, hand-curated baseline.

## Primary metric

**`composite_direction_score`** (higher is better) — a three-term blend:

- **AUC discrimination (40%)** — `0.6·walkforward_mean_auc + 0.4·stacking_holdout_auc`.
  Moved by `direction_pct_threshold`, `prediction_horizon`, `horizon_candidates`,
  `sample_weight_halflife`, `purge_multiplier`, `base_model_keys`, `cv_folds`,
  and the feature lanes in `feature_config`. Serving is Option A (single best
  base learner shipped), so `meta_model` / `stacking_calibration_*` do not move
  this term — leave them at defaults.
- **Probability quality (30%)** — `1 − normalized_brier` (Brier vs 0.25 random
  ceiling). Moved by richer features, cleaner labels (`label_mode`,
  `direction_pct_threshold`), and the served calibrator (`calibration_method`).
  Weak base discrimination caps this term — improve the signal first.
- **Post-cost economics (30%)** — squashed post-cost Sharpe from a fee+slippage
  replay on OOF probabilities, scaled down by a drawdown penalty. A config with
  catastrophic max-drawdown cannot score ≥ 0.5 on Sharpe alone.

A high-AUC model with weak, compressed probabilities (Brier ≈ 0.25) scores near
zero on the probability-quality term. A candidate that loses money post-cost or
suffers a deep drawdown scores below 0.5 on economics.

## Iteration contract

Modify `train.yaml` hyperparameters → run
`scripts/autotuner/direction/prepare.py --config <workspace>/train.yaml` →
keep/discard based on the primary metric. Do NOT edit `prepare.py` itself.

## Key levers (by term they move)

- **AUC**: `direction_pct_threshold`, `prediction_horizon`, `horizon_candidates`,
  `sample_weight_halflife`, `purge_multiplier`, `base_model_keys`, `cv_folds`,
  feature lanes.
- **Probability quality**: `feature_config` lanes, `label_mode`,
  `calibration_method`.
- **Economics**: reward/penalty weights in the post-cost replay (downstream of
  the served probabilities).
