# test_config_promoter_atomic Module

**Path:** `tests/test_config_promoter_atomic.py`

## Description

P0-012 — Crash-during-write promotion tests.

The backlog names this file explicitly (``ARC-011-backlog.md`` §3, task
P0-012). The atomic-write helper ``_atomic_write_text`` (in
``src/core/promotion_target.py``) uses temp + ``fsync`` + ``os.replace`` +
directory ``fsync`` so a crash midway through a promotion write leaves the
target file's prior content intact and no half-written temp visible at the
target path.

These tests inject failures at each stage of the write (write, fsync, rename)
and assert the target file is unchanged + the temp is cleaned up. The happy-
path coverage in ``test_hardening_phase1_to_5.py`` only checks the post-
rename state on success; these tests pin the atomicity contract (the core
acceptance criterion: "partial write must not corrupt the promoted config").

## Imports

| Source | Symbols |
|--------|---------|
| `__future__` | `annotations` |
| `os` | `os` |
| `pathlib` | `Path` |
| `pytest` | `pytest` |
| `src.core.promotion_target` | `_atomic_write_text` |
| `threading` | `threading` |
| `time` | `time` |
| `unittest.mock` | `patch` |

## Local dependency map

<!-- Auto-generated local dependency summary. Do not edit by hand. -->
```mermaid
flowchart LR
    n0["src/core/promotion_target.py"]
    n1["tests/test_config_promoter_atomic.py"]
    n1 --> n0
    click n0 "../modules/promotion_target.md"
    click n1 "../modules/test_config_promoter_atomic.md"
```

### Internal neighbors

| Direction | Module |
|---|---|
| Outbound | [promotion_target](../modules/promotion_target.md) |

### External packages

| Language | Used packages | Undeclared packages |
|---|---:|---:|
| python | 1 | 1 |

## Functions

| Function | Signature | Decorators | Description |
|----------|-----------|------------|-------------|
| `_seed_target` | `(tmp_path: Path) -> Path` | — | — |
| `_temp_files` | `(tmp_path: Path) -> list[Path]` | — | Leftover temp files from a failed atomic write (prefix '.' suffix '.tmp'). |
| `test_os_replace_failure_preserves_existing_file` | `(tmp_path: Path) -> None` | — | — |
| `test_fsync_failure_preserves_existing_file` | `(tmp_path: Path) -> None` | — | — |
| `test_write_failure_preserves_existing_file` | `(tmp_path: Path) -> None` | — | — |
| `test_atomic_write_overwrites_and_leaves_no_temp` | `(tmp_path: Path) -> None` | — | — |
| `test_atomic_write_creates_nested_parent` | `(tmp_path: Path) -> None` | — | — |
| `test_concurrent_reader_never_sees_partial_content` | `(tmp_path: Path) -> None` | — | While a background thread overwrites the config, a polling reader sees |
