"""Bounded JSONL data loading shared by the packaged bootstrap and evaluator."""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path

MAX_DATASET_BYTES = 5 * 1024 * 1024
MAX_EXAMPLES = 10_000


def load_examples(path: str | Path) -> list[dict[str, str]]:
    """Read data only: regular .jsonl files, no symlinks or executable content."""
    path = Path(path)
    if path.suffix.lower() != ".jsonl" or ".." in path.parts:
        raise ValueError("eval_set must be a JSONL path without parent traversal")
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError("eval_set must not use symlinks")
    # NONBLOCK avoids hanging on a FIFO; NOFOLLOW rejects a swapped leaf symlink.
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_DATASET_BYTES:
            raise ValueError("eval_set must be a regular file of at most 5 MiB")
        raw = stream.read(MAX_DATASET_BYTES + 1)
    if len(raw) > MAX_DATASET_BYTES:
        raise ValueError("eval_set exceeds 5 MiB")
    examples = []
    for line in raw.decode("utf-8").splitlines():
        if not line.strip():
            continue
        example = json.loads(line)
        if not isinstance(example, dict) or set(example) != {"input", "expected"}:
            raise ValueError("each example must contain only input and expected")
        if any(not isinstance(value, str) or not value.strip() for value in example.values()):
            raise ValueError("input and expected must be nonempty strings")
        examples.append(example)
        if len(examples) > MAX_EXAMPLES:
            raise ValueError("eval_set exceeds 10000 examples")
    if not examples:
        raise ValueError("eval_set must contain at least one example")
    return examples
