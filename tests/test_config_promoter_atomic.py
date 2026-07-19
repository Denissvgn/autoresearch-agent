"""P0-012 — Crash-during-write promotion tests.

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
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from src.core.promotion_target import _atomic_write_text

_OLD_CONTENT = "version: old-v1\n# the live config a crash must preserve\n"
_NEW_CONTENT = "version: new-v2\n# the promoted config\n"


def _seed_target(tmp_path: Path) -> Path:
    target = tmp_path / "config.yaml"
    target.write_text(_OLD_CONTENT, encoding="utf-8")
    return target


def _temp_files(tmp_path: Path) -> list[Path]:
    """Leftover temp files from a failed atomic write (prefix '.' suffix '.tmp')."""
    return [p for p in tmp_path.iterdir() if p.name.startswith(".") and p.name.endswith(".tmp")]


# ---------------------------------------------------------------------------
# Crash during each stage of the atomic write — target file preserved
# ---------------------------------------------------------------------------


def test_os_replace_failure_preserves_existing_file(tmp_path: Path) -> None:
    target = _seed_target(tmp_path)

    with patch("src.core.promotion_target.os.replace", side_effect=OSError("disk full")):
        with pytest.raises(OSError, match="disk full"):
            _atomic_write_text(str(target), _NEW_CONTENT)

    assert target.read_text(encoding="utf-8") == _OLD_CONTENT
    assert _temp_files(tmp_path) == []


def test_fsync_failure_preserves_existing_file(tmp_path: Path) -> None:
    target = _seed_target(tmp_path)

    with patch("src.core.promotion_target.os.fsync", side_effect=OSError("io error")):
        with pytest.raises(OSError, match="io error"):
            _atomic_write_text(str(target), _NEW_CONTENT)

    assert target.read_text(encoding="utf-8") == _OLD_CONTENT
    assert _temp_files(tmp_path) == []


def test_write_failure_preserves_existing_file(tmp_path: Path) -> None:
    target = _seed_target(tmp_path)

    real_fdopen = os.fdopen

    def _failing_fdopen(fd, *args, **kwargs):
        fh = real_fdopen(fd, *args, **kwargs)
        original_write = fh.write

        def _write(_data):
            raise OSError("write failed mid-stream")

        fh.write = _write  # type: ignore[method-assign]
        return fh

    with patch("src.core.promotion_target.os.fdopen", side_effect=_failing_fdopen):
        with pytest.raises(OSError, match="write failed mid-stream"):
            _atomic_write_text(str(target), _NEW_CONTENT)

    assert target.read_text(encoding="utf-8") == _OLD_CONTENT
    assert _temp_files(tmp_path) == []


# ---------------------------------------------------------------------------
# Happy path (self-contained in this file)
# ---------------------------------------------------------------------------


def test_atomic_write_overwrites_and_leaves_no_temp(tmp_path: Path) -> None:
    target = _seed_target(tmp_path)

    _atomic_write_text(str(target), _NEW_CONTENT)

    assert target.read_text(encoding="utf-8") == _NEW_CONTENT
    assert _temp_files(tmp_path) == []


def test_atomic_write_creates_nested_parent(tmp_path: Path) -> None:
    target = tmp_path / "deep" / "nested" / "config.json"

    _atomic_write_text(str(target), "{}")

    assert target.read_text(encoding="utf-8") == "{}"


# ---------------------------------------------------------------------------
# Concurrent reader never observes a partial file
# ---------------------------------------------------------------------------


def test_concurrent_reader_never_sees_partial_content(tmp_path: Path) -> None:
    """While a background thread overwrites the config, a polling reader sees
    only complete old or complete new content — never a truncated/mid-write
    string. This is the durability property ``os.replace`` guarantees: the
    rename is atomic at the filesystem level, so the path always resolves to
    a complete file.
    """
    target = _seed_target(tmp_path)
    stop = threading.Event()
    observed = set()
    error: list[Exception] = []

    def _reader():
        while not stop.is_set():
            content = target.read_text(encoding="utf-8")
            if content not in (_OLD_CONTENT, _NEW_CONTENT):
                error.append(AssertionError(f"reader saw partial content: {content!r}"))
                return
            observed.add(content)
            time.sleep(0.001)

    reader = threading.Thread(target=_reader)
    reader.start()
    try:
        # Give the reader a moment to observe the old content, then overwrite.
        time.sleep(0.02)
        _atomic_write_text(str(target), _NEW_CONTENT)
        time.sleep(0.02)  # let the reader observe the new content
    finally:
        stop.set()
        reader.join(timeout=2)

    assert not error, error
    # The reader observed at least the old content (the rename may or may not
    # have been observed depending on timing, but never a partial).
    assert _OLD_CONTENT in observed
