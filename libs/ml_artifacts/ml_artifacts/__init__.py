"""Shared runtime helpers for ML artifacts produced by training services."""

__all__ = ["__version__", "LIBRARY_VERSION", "FEATURE_CONTRACT_VERSION"]

# Bump 0.1.0 → 0.2.0: DM-5 multi-horizon ensemble changes the meta-feature
# matrix shape from (n, B) → (n, H*B). Old artifacts (single-horizon,
# feature_contract_version absent / "0.1.0") continue to load via the
# legacy pyfunc path; new artifacts ("0.2.0") carry ``horizon_roster``
# and use the expanded-shape dispatch.
__version__ = "0.2.0"
LIBRARY_VERSION = __version__

# Standalone constant the stacking pyfunc writes into the ensemble dict
# and reads back at inference time. Distinct from ``__version__`` so the
# library can evolve (e.g. helper additions) without forcing a feature-
# contract migration on every release.
FEATURE_CONTRACT_VERSION = "0.2.0"
