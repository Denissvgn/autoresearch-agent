# test_execution_ledger_validator Module

**Path:** `tests/test_execution_ledger_validator.py`

## Description

Tests for the execution-ledger validator (scripts/check_execution_ledger.py).

Fixtures use synthetic opaque card IDs; no real planning vocabulary appears
here by design — the validator must stay domain-agnostic.

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `importlib.util` | `importlib.util` |
| `json` | `json` |
| `pathlib` | `Path` |
| `pytest` | `pytest` |
| `sys` | `sys` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
*No internal module dependencies detected.*

### External packages

| Language | Used packages | Undeclared packages |
|---|---:|---:|
| python | 1 | 1 |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_card` | `(cid: str, **overrides) -> dict` | — | — |
| `_done_card` | `(cid: str, **overrides) -> dict` | — | — |
| `_write_ledger` | `(tmp_path: Path, cards: list[dict], **side_tweaks) -> Path` | — | — |
| `test_valid_minimal_ledger_passes` | `(tmp_path)` | — | — |
| `test_unknown_dependency_card_rejected` | `(tmp_path)` | — | — |
| `test_duplicate_card_id_rejected` | `(tmp_path)` | — | — |
| `test_malformed_card_id_rejected` | `(tmp_path)` | — | — |
| `test_unknown_state_rejected` | `(tmp_path)` | — | — |
| `test_illegal_transition_rejected` | `(tmp_path)` | — | — |
| `test_status_contradicting_history_rejected` | `(tmp_path)` | — | — |
| `test_dependency_cycle_rejected` | `(tmp_path)` | — | — |
| `test_done_without_evidence_rejected` | `(tmp_path)` | — | A DONE record missing results/review/commits must not validate. |
| `test_done_with_failed_check_rejected` | `(tmp_path)` | — | — |
| `test_done_with_unsatisfied_acceptance_rejected` | `(tmp_path)` | — | — |
| `test_done_with_unfinished_prerequisite_rejected` | `(tmp_path)` | — | — |
| `test_done_with_unresolved_review_finding_rejected` | `(tmp_path)` | — | — |
| `test_fully_evidenced_done_record_passes` | `(tmp_path)` | — | — |
| `test_acceptance_unknown_check_reference_rejected` | `(tmp_path)` | — | — |
| `test_result_unknown_check_reference_rejected` | `(tmp_path)` | — | — |
| `test_missing_ledger_file_is_error_not_crash` | `(tmp_path)` | — | — |
| `test_active_card_must_be_known` | `(tmp_path)` | — | — |
| `test_real_ledger_directory_is_valid` | `()` | — | The live run ledger must validate whenever it is present. |
