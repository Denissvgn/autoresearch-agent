# TestAutoPhaseEvidenceConsistencyGuard

**Location:** `tests/test_auto_phase_evidence.py:78`
**Kind:** Class
**Bases:** —
**Module:** [test_auto_phase_evidence](../modules/test_auto_phase_evidence.md)

## Description

_Auto-generated from `TestAutoPhaseEvidenceConsistencyGuard` in `tests/test_auto_phase_evidence.py`._

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `test_hard_checks_suppressed_when_auto_phase_evidence_true` | `()` | — | auto_phase_evidence=True → NOT treated as promotion candidate → no hard blockers. |
| `test_hard_checks_active_when_auto_phase_evidence_absent` | `()` | — | No auto_phase_evidence key → real promotion candidate → hard checks apply. |
| `test_hard_checks_active_when_auto_phase_evidence_false` | `()` | — | auto_phase_evidence=False → same as absent → hard checks apply. |
| `test_no_spurious_blockers_for_tabular_sweep_with_auto_evidence` | `()` | — | A plain tabular-sweep iteration with auto_phase_evidence should pass cleanly. |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
*No generated relationships detected.*

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [test_auto_phase_evidence](../modules/test_auto_phase_evidence.md) | 4 | — |
