"""Named base-learner rosters for direction stacking experiments."""

from __future__ import annotations

from typing import Iterable


CURRENT_DEFAULT_DIRECTION_ROSTER = ["lgb", "xgb", "rf"]

EXPANDED_EXISTING_DIRECTION_ROSTER = [
    "lgb",
    "lgb_deep",
    "lgb_shallow",
    "lgb_dart",
    "lgb_goss",
    "xgb",
    "xgb_deep",
    "xgb_conserv",
    "rf",
    "rf_deep",
    "rf_shallow",
]

EXPANDED_SKLEARN_DIRECTION_ROSTER = [
    *EXPANDED_EXISTING_DIRECTION_ROSTER,
    "extra_trees",
    "hist_gradient_boosting",
    "calibrated_sgd",
    "linear_logistic",
]

DIRECTION_ROSTER_PRESETS = {
    "current_default": CURRENT_DEFAULT_DIRECTION_ROSTER,
    "baseline": CURRENT_DEFAULT_DIRECTION_ROSTER,
    "expanded_existing": EXPANDED_EXISTING_DIRECTION_ROSTER,
    "expanded_variants": EXPANDED_EXISTING_DIRECTION_ROSTER,
    "expanded_sklearn": EXPANDED_SKLEARN_DIRECTION_ROSTER,
    "expanded_with_sklearn": EXPANDED_SKLEARN_DIRECTION_ROSTER,
}


def dedupe_roster(model_keys: Iterable[str]) -> list[str]:
    """Return lower-case model keys, preserving first occurrence order."""
    return list(dict.fromkeys(str(key).strip().lower() for key in model_keys if str(key).strip()))


def get_direction_roster_preset(name: str) -> list[str]:
    """Return a copy of a named direction roster preset."""
    key = str(name).strip().lower()
    try:
        return list(DIRECTION_ROSTER_PRESETS[key])
    except KeyError as exc:
        valid = ", ".join(sorted(DIRECTION_ROSTER_PRESETS))
        raise ValueError(f"Unknown direction roster preset '{name}'. Valid presets: {valid}") from exc


def resolve_direction_roster(
    *,
    roster_preset: str | None = None,
    explicit_model_keys: Iterable[str] | None = None,
    default_preset: str = "expanded_existing",
) -> tuple[list[str], str]:
    """Resolve direction model keys and the preset label used for reporting.

    Explicit model keys win over presets so existing configs remain backward
    compatible.  When no explicit keys are provided, ``roster_preset`` selects
    a named roster and falls back to ``default_preset``.
    """
    if explicit_model_keys is not None:
        resolved = dedupe_roster(explicit_model_keys)
        if resolved:
            if roster_preset:
                preset_name = str(roster_preset).strip().lower()
                try:
                    if resolved == get_direction_roster_preset(preset_name):
                        return resolved, preset_name
                except ValueError:
                    pass
            return resolved, "custom"

    preset_name = roster_preset or default_preset
    return get_direction_roster_preset(preset_name), str(preset_name).strip().lower()
