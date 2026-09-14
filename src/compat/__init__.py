"""Legacy compatibility surfaces (P1-2).

Historical trading-platform vocabulary and pre-migration DB-row rendering
live here, clearly quarantined from the domain-neutral runtime:

* ``legacy_alias.py`` — the legacy ``model_type`` ↔ ``skill_id`` bridge.
* ``ml_enrichment.py`` — RL economic-replay / feature-readiness projection
  for pre-migration iteration rows.
* ``legacy_phase_tables.py`` — the DIRECTION/VOLATILITY/FALLBACK phase plans
  and their legacy lookups (``phases_for_model``), the historical RL OOS
  evidence keys, and the DM-14 primary-sweep knob table.

Every module under ``src/compat/`` exists only so pre-migration database rows
still render and legacy API callers keep working; nothing here may grow new
features. The domain-coupling guard exempts (and thereby documents) each file
kept here.
"""