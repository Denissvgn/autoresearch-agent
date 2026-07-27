# ML Volatility Model — Knowledge Primer

Domain expertise corpus for the `ml-volatility` skill. Loaded by the bootstrap
(`bootstrap.py`) and referenced by the orchestrator's system-prompt assembly.
The feedback loop (ARC-011 P5-027) appends session insights to
`prior_findings/`; this primer is the stable, hand-curated baseline.

## Primary metric

**`auc`** (higher is better) — area under the ROC curve for the volatility
breakout (up/down) classifier.

## Critical constraint

**`positive_rate`** must be **10–40%** for meaningful class balance. A config
outside this range is over/under-predicting breakouts and should be reverted
even if AUC looks good.

## Feature consistency

Direction and volatility models share the same feature library (v2.1.0, 93
features). They diverge only at selection — **volatility excludes `atr_ratio`
and `bb_width`**. Never change `feature_library_version` without also updating
direction.

## Iteration contract

Modify `train.yaml` hyperparameters (especially the **ATR multiplier**) → run
`scripts/autotuner/volatility/prepare.py --config <workspace>/train.yaml` →
keep/discard based on AUC + positive_rate. Do NOT edit `prepare.py` itself.

## Key levers

- **ATR multiplier** — the dominant lever for volatility breakout sensitivity.
- `positive_rate` target band — tune the decision threshold to land in 10–40%.
- Feature selection (exclude `atr_ratio` / `bb_width`).
- Calibration method (for probability quality downstream of AUC).
