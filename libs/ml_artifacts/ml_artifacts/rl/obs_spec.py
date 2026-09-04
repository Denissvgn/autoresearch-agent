"""Canonical observation-spec hashing for RL train/serve parity (MQ-D2).

``obs_spec.json`` is the contract that lets the inference service reconstruct
the exact observation vector the RL agent was trained on. This module pins a
deterministic hash over the *structural* fields of that contract so the
serving side can assert at agent-load time that the spec it downloaded is the
one the trainer stamped (mirror of the ``feature_schema_hash`` parity gate,
rule R4). Volatile/diagnostic fields (feature importance, probability
provenance summaries, curriculum stage) are deliberately excluded.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Optional, Tuple

#: Structural fields covered by the hash. Order does not matter (the canonical
#: JSON is key-sorted); absent fields are skipped so older specs hash stably.
OBS_SPEC_HASH_FIELDS = (
    "feature_columns",
    "features_per_timestep",
    "lookback_window",
    "include_margin_obs",
    "include_regime_obs",
    "base_state_features",
    "margin_state_features",
    "regime_state_features",
    "total_obs_dim",
    "normalization",
    "regime_detector",
    "env_contract",
)

_HASH_KEY = "obs_spec_hash"


def compute_obs_spec_hash(spec: Dict[str, Any]) -> str:
    """Deterministic ``sha256:<hex>`` over the structural spec fields."""
    canonical = {
        field: spec[field] for field in OBS_SPEC_HASH_FIELDS if field in spec
    }
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verify_obs_spec_hash(
    spec: Dict[str, Any],
) -> Tuple[Optional[bool], Optional[str], Optional[str]]:
    """Check a loaded spec against its stamped hash.

    Returns ``(ok, stamped, recomputed)`` where ``ok`` is:
    - ``None`` — spec carries no ``obs_spec_hash`` (pre-MQ-D2 artifact;
      caller decides whether to accept legacy specs),
    - ``True`` — stamped hash matches the recomputed one,
    - ``False`` — mismatch: the spec was altered after training (fail closed).
    """
    stamped = spec.get(_HASH_KEY)
    if not stamped:
        return None, None, None
    recomputed = compute_obs_spec_hash(spec)
    return recomputed == str(stamped), str(stamped), recomputed
