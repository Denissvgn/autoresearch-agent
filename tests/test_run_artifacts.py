"""Content-addressed artifacts: bundles, safe imports, atomic retention.

Multi-file candidate bundles round-trip exactly, tampered objects are
detected, symlinks and archive traversal cannot widen imported roots, and
cleanup/retention respect live references even when interrupted.
"""

from __future__ import annotations

import io
import tarfile
import zipfile

import pytest

from src.core.run_artifacts import (
    ArtifactError,
    ArtifactLimits,
    ArtifactStore,
    bundle_digest,
    snapshot_parent_workspace,
)


def _store(tmp_path, **limit_kwargs) -> ArtifactStore:
    return ArtifactStore(
        tmp_path / "artifacts", limits=ArtifactLimits(**limit_kwargs),
    )


def test_multi_file_bundle_round_trips_exactly(tmp_path):
    store = _store(tmp_path)
    source = tmp_path / "candidate"
    (source / "nested").mkdir(parents=True)
    (source / "a.yaml").write_text("metric: 1\n", encoding="utf-8")
    (source / "nested" / "b.json").write_text('{"x": 2}\n', encoding="utf-8")
    descriptor = store.import_tree(source)
    assert set(descriptor["files"]) == {"a.yaml", "nested/b.json"}
    assert store.verify_bundle(descriptor["digest"]) is True

    dest = tmp_path / "reconstructed"
    written = store.reconstruct(descriptor["digest"], dest)
    assert set(written) == {"a.yaml", "nested/b.json"}
    assert (dest / "a.yaml").read_text(encoding="utf-8") == "metric: 1\n"
    assert (dest / "nested" / "b.json").read_text(encoding="utf-8") == '{"x": 2}\n'
    # Content addressing is deterministic: identical content, identical digest.
    again = store.import_tree(source)
    assert again["digest"] == descriptor["digest"]


def test_tampered_objects_are_detected_never_used(tmp_path):
    store = _store(tmp_path)
    descriptor = store.create_bundle({"a.txt": b"original"})
    object_path = (
        store.root / "objects"
        / descriptor["files"]["a.txt"]["sha256"][:2]
        / descriptor["files"]["a.txt"]["sha256"]
    )
    object_path.chmod(0o644)
    object_path.write_bytes(b"tampered")
    assert store.verify_bundle(descriptor["digest"]) is False
    with pytest.raises(ArtifactError, match="corrupt"):
        store.reconstruct(descriptor["digest"], tmp_path / "out")


def test_import_tree_refuses_symlinks(tmp_path):
    store = _store(tmp_path)
    source = tmp_path / "candidate"
    source.mkdir()
    (source / "real.txt").write_text("x", encoding="utf-8")
    (source / "link.txt").symlink_to(source / "real.txt")
    with pytest.raises(ArtifactError, match="symlink"):
        store.import_tree(source)
    with pytest.raises(ArtifactError, match="symlink"):
        store.import_tree(source, includes=["link.txt"])


def test_archive_traversal_and_links_cannot_widen_the_root(tmp_path):
    store = _store(tmp_path)
    evil_tar = tmp_path / "evil.tar"
    with tarfile.open(evil_tar, "w") as archive:
        member = tarfile.TarInfo(name="../escape.txt")
        payload = b"escaped"
        member.size = len(payload)
        archive.addfile(member, io.BytesIO(payload))
    with pytest.raises(ArtifactError, match="traverses"):
        store.import_archive(evil_tar)

    absolute_tar = tmp_path / "absolute.tar"
    with tarfile.open(absolute_tar, "w") as archive:
        member = tarfile.TarInfo(name="/etc/passwd")
        payload = b"root"
        member.size = len(payload)
        archive.addfile(member, io.BytesIO(payload))
    with pytest.raises(ArtifactError, match="relative"):
        store.import_archive(absolute_tar)

    link_tar = tmp_path / "link.tar"
    with tarfile.open(link_tar, "w") as archive:
        member = tarfile.TarInfo(name="innocent.txt")
        member.type = tarfile.SYMTYPE
        member.linkname = "/etc/passwd"
        archive.addfile(member)
    with pytest.raises(ArtifactError, match="link member"):
        store.import_archive(link_tar)

    evil_zip = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil_zip, "w") as archive:
        archive.writestr("../escape.txt", "escaped")
    with pytest.raises(ArtifactError, match="traverses"):
        store.import_archive(evil_zip)

    good = tmp_path / "good.zip"
    with zipfile.ZipFile(good, "w") as archive:
        archive.writestr("nested/inner.txt", "inner")
    descriptor = store.import_archive(good)
    assert set(descriptor["files"]) == {"nested/inner.txt"}
    assert store.verify_bundle(descriptor["digest"]) is True


def test_import_limits_are_enforced(tmp_path):
    store = _store(tmp_path, max_files=1)
    source = tmp_path / "candidate"
    source.mkdir()
    (source / "a.txt").write_text("1", encoding="utf-8")
    (source / "b.txt").write_text("2", encoding="utf-8")
    with pytest.raises(ArtifactError, match="max_files"):
        store.import_tree(source)

    store = _store(tmp_path / "two", max_file_bytes=2)
    with pytest.raises(ArtifactError, match="max_file_bytes"):
        store.create_bundle({"big.txt": b"too big"})


def test_partial_writes_are_cleaned_and_never_visible(tmp_path):
    store = _store(tmp_path)
    descriptor = store.create_bundle({"a.txt": b"payload"})
    staging = store.root / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    abandoned = staging / "abandoned.tmp"
    abandoned.write_bytes(b"partial")
    removed = store.cleanup_partial()
    assert "abandoned.tmp" in removed
    assert not abandoned.exists()
    assert store.verify_bundle(descriptor["digest"]) is True


def test_retention_respects_live_references_and_resumes(tmp_path):
    store = _store(tmp_path)
    parent = store.create_bundle({"parent.txt": b"parent"})
    stale = store.create_bundle({"stale.txt": b"stale"})
    assert store.verify_bundle(stale["digest"]) is True

    result = store.gc(live_digests=[parent["digest"]])
    assert result["kept_bundles"] == 1
    assert store.verify_bundle(parent["digest"]) is True
    with pytest.raises(ArtifactError, match="not in the store"):
        store.load_bundle(stale["digest"])
    again = store.gc(live_digests=[parent["digest"]])
    assert again["kept_bundles"] == 1
    assert store.verify_bundle(parent["digest"]) is True


def test_parent_snapshot_is_a_bounded_reference(tmp_path):
    store = _store(tmp_path)
    parent_ws = tmp_path / "parent_ws"
    parent_ws.mkdir()
    (parent_ws / "best_candidate.yaml").write_text("metric: 9\n", encoding="utf-8")
    (parent_ws / "eval_result.json").write_text("{}", encoding="utf-8")
    scratch = parent_ws / "scratch"
    scratch.mkdir()
    (scratch / "ignored.txt").write_text("noise", encoding="utf-8")

    descriptor = snapshot_parent_workspace(
        parent_ws, store,
        includes=["best_candidate.yaml", "eval_result.json"],
    )
    assert set(descriptor["files"]) == {
        "best_candidate.yaml", "eval_result.json",
    }
    assert bundle_digest(descriptor["files"]) == descriptor["digest"]
