# TestCursorHelper

**Location:** `tests/test_pagination.py:102`
**Kind:** Class
**Bases:** —
**Module:** [test_pagination](../modules/test_pagination.md)

## Description

_Auto-generated from `TestCursorHelper` in `tests/test_pagination.py`._

## Attributes

*No annotated attributes found.*

## Methods

| Method | Signature | Decorators | Description |
|--------|-----------|------------|-------------|
| `test_round_trip_with_string_sort_key_and_string_tiebreak` | `()` | — | — |
| `test_round_trip_with_integer_sort_key_and_int_tiebreak` | `()` | — | — |
| `test_token_is_opaque_and_not_a_raw_offset` | `()` | — | — |
| `test_malformed_tokens_decode_to_none` | `(bad)` | `@pytest.mark.parametrize('bad', [None, '', '   ', '!!!not-base64!!!', 'YWJjZA'])` | — |
| `test_wrong_version_token_decodes_to_none` | `()` | — | — |
| `test_token_missing_fields_decodes_to_none` | `()` | — | — |
| `test_clamp_limit_boundary_table` | `(limit_in, expected)` | `@pytest.mark.parametrize('limit_in, expected', [(None, DEFAULT_PAGE_SIZE), (0, DEFAULT_PAGE_SIZE), (-5, DEFAULT_PAGE_SIZE), (1, 1), (50, 50), (MAX_PAGE_SIZE, MAX_PAGE_SIZE), (MAX_PAGE_SIZE + 1, MAX_PAGE_SIZE), (10000, MAX_PAGE_SIZE)])` | — |

## Relationships

<!-- Auto-generated relationship summary. Do not edit by hand. -->
*No generated relationships detected.*

### Summary

| Module | Methods | Attributes |
|---|---:|---|
| [test_pagination](../modules/test_pagination.md) | 7 | — |
