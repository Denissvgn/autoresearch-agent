"""Symlink-race and shared-alias resistance for filesystem operations.

Every sensitive write must be immune to check/use races: dangling leaf
links, linked parents, hardlink aliases, and concurrent rename/link
replacement must never create or overwrite data outside the authorized
root. Denied operations must name themselves (``write`` / ``read`` /
``copy``) in the error.
"""
from __future__ import annotations

import json
import os
import stat
import threading
from pathlib import Path

import pytest

from src.core import fs_safety
from src.core.fs_safety import FilesystemSafetyError
from src.core.iteration_snapshot import write_iteration_attempt_snapshot
from src.core.result_artifact import enrich_marker_from_result_artifact
from src.core.tool_access import build_tool_access_context
from src.core.trial_workspace import stage_trial_workspace


def _sentinel(outside: Path) -> Path:
    target = outside / "sentinel.txt"
    target.write_bytes(b"SENTINEL")
    os.chmod(target, 0o600)
    return target


def _assert_untouched(sentinel: Path) -> None:
    assert sentinel.read_bytes() == b"SENTINEL"
    assert stat.S_IMODE(sentinel.stat().st_mode) == 0o600


# ── the original defect: a dangling leaf link bypassed write confinement ───


def test_dangling_leaf_symlink_never_creates_the_outside_target(tmp_path: Path) -> None:
    root = tmp_path / "session"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = _sentinel(outside)
    (root / "dangling.txt").symlink_to(outside / "not-yet-created.txt")

    with pytest.raises(FilesystemSafetyError) as excinfo:
        fs_safety.safe_write_text(str(root), "dangling.txt", "tampered")

    err = excinfo.value
    assert err.operation == "write"
    assert "symlink" in str(err)
    assert not (outside / "not-yet-created.txt").exists()
    _assert_untouched(sentinel)


def test_symlink_to_existing_file_is_denied_for_write(tmp_path: Path) -> None:
    root = tmp_path / "session"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = _sentinel(outside)
    (root / "linked.txt").symlink_to(sentinel)

    with pytest.raises(FilesystemSafetyError) as excinfo:
        fs_safety.safe_write_text(str(root), "linked.txt", "tampered")

    assert excinfo.value.operation == "write"
    assert "symlink" in str(excinfo.value)
    _assert_untouched(sentinel)


# ── linked parents ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("target_kind", ["outside", "inside"])
def test_linked_parent_is_denied_for_write(tmp_path: Path, target_kind: str) -> None:
    root = tmp_path / "session"
    (root / "real").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = _sentinel(outside)
    link_target = outside if target_kind == "outside" else root / "real"
    (root / "sub").symlink_to(link_target)

    with pytest.raises(FilesystemSafetyError) as excinfo:
        fs_safety.safe_write_text(str(root), "sub/file.txt", "tampered")

    err = excinfo.value
    assert err.operation == "write"
    assert "symlink" in err.reason
    assert not (outside / "file.txt").exists()
    assert not (root / "real" / "file.txt").exists()
    _assert_untouched(sentinel)


# ── hardlink aliases for shared files ──────────────────────────────────────


def test_hardlinked_leaf_write_is_denied(tmp_path: Path) -> None:
    root = tmp_path / "session"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = _sentinel(outside)
    os.link(sentinel, root / "alias.txt")

    with pytest.raises(FilesystemSafetyError) as excinfo:
        fs_safety.safe_write_text(str(root), "alias.txt", "tampered")

    err = excinfo.value
    assert err.operation == "write"
    assert "hard links" in err.reason
    _assert_untouched(sentinel)


def test_non_regular_leaf_write_is_denied(tmp_path: Path) -> None:
    root = tmp_path / "session"
    (root / "dirleaf").mkdir(parents=True)

    with pytest.raises(FilesystemSafetyError) as excinfo:
        fs_safety.safe_write_text(str(root), "dirleaf", "tampered")

    assert excinfo.value.operation == "write"
    assert "not a regular file" in excinfo.value.reason


# ── path validation and parent creation ────────────────────────────────────


@pytest.mark.parametrize("bad", ["", "/etc/passwd", "../escape.txt", "a/../../b.txt"])
def test_unsafe_relative_paths_are_rejected(tmp_path: Path, bad: str) -> None:
    root = tmp_path / "session"
    root.mkdir()
    with pytest.raises(FilesystemSafetyError):
        fs_safety.safe_write_text(str(root), bad, "x")


def test_nested_parent_creation_without_following_links(tmp_path: Path) -> None:
    root = tmp_path / "session"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = _sentinel(outside)

    written = fs_safety.safe_write_text(str(root), "a/b/c.txt", "nested")
    assert Path(written).read_text(encoding="utf-8") == "nested"

    (root / "a" / "trap").symlink_to(outside)
    with pytest.raises(FilesystemSafetyError) as excinfo:
        fs_safety.safe_write_text(str(root), "a/trap/x.txt", "tampered")
    assert "symlink" in excinfo.value.reason
    assert not (outside / "x.txt").exists()
    _assert_untouched(sentinel)


# ── replacement semantics ──────────────────────────────────────────────────


def test_replace_updates_regular_leaf_without_temp_leftovers(tmp_path: Path) -> None:
    root = tmp_path / "session"
    root.mkdir()
    fs_safety.safe_write_text(str(root), "f.txt", "first")
    fs_safety.safe_write_text(str(root), "f.txt", "second")
    assert (root / "f.txt").read_text(encoding="utf-8") == "second"
    assert sorted(p.name for p in root.iterdir()) == ["f.txt"]


# ── swap between authorization and write (the check/use race) ──────────────


def test_leaf_swapped_to_dangling_link_after_authorization_is_denied(tmp_path: Path) -> None:
    shared = tmp_path / "shared"
    session = shared / "runs" / "s"
    session.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = _sentinel(outside)
    access = build_tool_access_context(str(session), workspace_root=str(shared))

    path = access.authorize_write("candidate.txt")  # passes: no link yet
    (session / "candidate.txt").symlink_to(outside / "created.txt")  # swap
    root, relative = access.writable_root_and_relative(path)

    with pytest.raises(FilesystemSafetyError) as excinfo:
        fs_safety.safe_write_text(root, relative, "tampered")

    assert excinfo.value.operation == "write"
    assert not (outside / "created.txt").exists()
    _assert_untouched(sentinel)


def test_parent_swapped_to_link_after_authorization_is_denied(tmp_path: Path) -> None:
    shared = tmp_path / "shared"
    session = shared / "runs" / "s"
    (session / "sub").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = _sentinel(outside)
    access = build_tool_access_context(str(session), workspace_root=str(shared))

    path = access.authorize_write("sub/file.txt")  # passes: real parent
    os.rename(session / "sub", session / "sub-old")
    (session / "sub").symlink_to(outside)  # swap
    root, relative = access.writable_root_and_relative(path)

    with pytest.raises(FilesystemSafetyError) as excinfo:
        fs_safety.safe_write_text(root, relative, "tampered")

    assert excinfo.value.operation == "write"
    assert "symlink" in excinfo.value.reason
    assert not (outside / "file.txt").exists()
    _assert_untouched(sentinel)


# ── concurrent rename/link replacement ─────────────────────────────────────


def test_concurrent_rename_and_link_replacement_never_escapes(tmp_path: Path) -> None:
    root = tmp_path / "session"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = _sentinel(outside)
    sub = root / "sub"
    sub.mkdir()
    stop = threading.Event()

    def attacker() -> None:
        i = 0
        while not stop.is_set():
            old = root / f"sub-old-{i % 2}"
            try:
                os.rename(sub, old)
                os.symlink(outside, sub)
                os.unlink(sub)
                os.rename(old, sub)
            except OSError:
                try:
                    if old.exists() and not sub.exists():
                        os.rename(old, sub)
                except OSError:
                    pass
            try:
                if (root / "leaf.txt").is_symlink():
                    os.unlink(root / "leaf.txt")
                else:
                    (root / "leaf.txt").symlink_to(outside / "leaf-target.txt")
            except OSError:
                pass
            i += 1

    thread = threading.Thread(target=attacker, daemon=True)
    thread.start()
    try:
        for i in range(300):
            for relative in ("sub/file.txt", "leaf.txt"):
                try:
                    fs_safety.safe_write_text(str(root), relative, f"payload-{i}")
                except FilesystemSafetyError:
                    pass  # a swap landed first: denial is the safe outcome
    finally:
        stop.set()
        thread.join(timeout=10)

    assert not thread.is_alive()
    _assert_untouched(sentinel)
    assert sorted(p.name for p in outside.iterdir()) == ["sentinel.txt"]


# ── import reads: links and shared aliases are refused ─────────────────────


def test_import_read_requires_regular_single_link_file(tmp_path: Path) -> None:
    root = tmp_path / "session"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = _sentinel(outside)

    (root / "real.json").write_text("{}", encoding="utf-8")
    assert fs_safety.read_regular_file(str(root), "real.json") == b"{}"

    (root / "linked.json").symlink_to(root / "real.json")
    with pytest.raises(FilesystemSafetyError) as excinfo:
        fs_safety.read_regular_file(str(root), "linked.json")
    assert excinfo.value.operation == "read"
    assert "symlink" in excinfo.value.reason

    os.link(sentinel, root / "alias.json")
    with pytest.raises(FilesystemSafetyError) as excinfo:
        fs_safety.read_regular_file(str(root), "alias.json")
    assert excinfo.value.operation == "read"
    assert "hard links" in excinfo.value.reason

    with pytest.raises(FilesystemSafetyError):
        fs_safety.read_regular_file(str(root), "../outside/sentinel.txt")

    with pytest.raises(FileNotFoundError):
        fs_safety.read_regular_file(str(root), "missing.json")


# ── staged inputs: no link is ever followed ────────────────────────────────


def test_stage_trial_workspace_skips_links_and_hardlinks(tmp_path: Path) -> None:
    session = tmp_path / "session"
    session.mkdir()
    trial = tmp_path / "trial"
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = _sentinel(outside)

    (session / "regular.txt").write_text("REGULAR", encoding="utf-8")
    (session / "nested").mkdir()
    (session / "nested" / "inner.txt").write_text("INNER", encoding="utf-8")
    (session / "file-link.txt").symlink_to(sentinel)
    (session / "dir-link").symlink_to(outside)
    os.link(sentinel, session / "alias.txt")
    (session / "nested" / "inner-link.txt").symlink_to(sentinel)

    staged = stage_trial_workspace(str(session), str(trial))

    assert staged == 2  # regular.txt and nested/
    assert (trial / "regular.txt").read_text(encoding="utf-8") == "REGULAR"
    assert (trial / "nested" / "inner.txt").read_text(encoding="utf-8") == "INNER"
    assert not (trial / "file-link.txt").exists()
    assert not (trial / "dir-link").exists()
    assert not (trial / "alias.txt").exists()
    assert not (trial / "nested" / "inner-link.txt").exists()
    for staged_file in trial.rglob("*"):
        if staged_file.is_file():
            assert b"SENTINEL" not in staged_file.read_bytes()
    _assert_untouched(sentinel)


# ── result collection: strict import, safe target write ────────────────────


def _result_marker(name: str = "results.json") -> dict:
    return {"results_json_path": name}


def test_result_collection_rejects_linked_sources(tmp_path: Path) -> None:
    ws = tmp_path / "session"
    ws.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = _sentinel(outside)

    (ws / "real.json").write_text('{"score": 1}', encoding="utf-8")
    (ws / "results.json").symlink_to(ws / "real.json")
    assert enrich_marker_from_result_artifact(
        marker=_result_marker(), workspace=str(ws), iteration=1
    ) is None
    assert not (ws / "server_snapshots").exists()

    os.unlink(ws / "results.json")
    os.link(sentinel, ws / "results.json")
    assert enrich_marker_from_result_artifact(
        marker=_result_marker(), workspace=str(ws), iteration=2
    ) is None
    assert not (ws / "server_snapshots").exists()
    _assert_untouched(sentinel)


def test_result_collection_target_link_is_not_followed(tmp_path: Path) -> None:
    ws = tmp_path / "session"
    ws.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = _sentinel(outside)
    (ws / "results.json").write_text('{"score": 1}', encoding="utf-8")
    (ws / "server_snapshots").mkdir()
    (ws / "server_snapshots" / "iteration_0001_results.json").symlink_to(sentinel)

    assert enrich_marker_from_result_artifact(
        marker=_result_marker(), workspace=str(ws), iteration=1
    ) is None
    _assert_untouched(sentinel)


def test_result_collection_still_copies_regular_results(tmp_path: Path) -> None:
    ws = tmp_path / "session"
    ws.mkdir()
    (ws / "results.json").write_text('{"score": 1}', encoding="utf-8")

    merged = enrich_marker_from_result_artifact(
        marker=_result_marker(), workspace=str(ws), iteration=3
    )
    assert merged is not None
    copied = ws / "server_snapshots" / "iteration_0003_results.json"
    assert json.loads(copied.read_text(encoding="utf-8")) == {"score": 1}
    assert merged["result_artifact_sha256"]


# ── attempt snapshots: planted target links are refused ────────────────────


def test_attempt_snapshot_write_refuses_planted_target_link(tmp_path: Path) -> None:
    ws = tmp_path / "session"
    ws.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = _sentinel(outside)
    (ws / "server_snapshots").mkdir()
    (ws / "server_snapshots" / "iteration_0001_attempt.json").symlink_to(sentinel)

    with pytest.raises(FilesystemSafetyError) as excinfo:
        write_iteration_attempt_snapshot(
            workspace=str(ws), snapshot={"iteration": 1, "x": 1}
        )
    assert excinfo.value.operation == "write"
    _assert_untouched(sentinel)


def test_attempt_snapshot_write_still_works(tmp_path: Path) -> None:
    ws = tmp_path / "session"
    ws.mkdir()
    written = write_iteration_attempt_snapshot(
        workspace=str(ws), snapshot={"iteration": 2, "x": 1}
    )
    assert Path(written).name == "iteration_0002_attempt.json"
    assert json.loads(Path(written).read_text(encoding="utf-8"))["x"] == 1