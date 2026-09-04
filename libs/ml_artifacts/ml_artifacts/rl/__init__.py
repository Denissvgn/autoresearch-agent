"""Shared RL train/serve parity contracts (MQ-D2 / MQ-D3).

Single source of truth for everything the RL *training environment* and the
*inference serving path* must compute identically:

- :mod:`ml_artifacts.rl.regime` — causal market-regime detection used for the
  regime one-hot observation features.
- :mod:`ml_artifacts.rl.obs_spec` — canonical hash over the observation-spec
  contract, verified at agent load (mirror of the feature-schema parity gate).
- :mod:`ml_artifacts.rl.gating` — the trained direction-confidence gate /
  conviction-sizing math applied by both the env and the serving pipeline.
"""
