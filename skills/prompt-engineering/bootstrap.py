"""P4-015 — Minimal bootstrap.py for the prompt-engineering skill (ARC-011).

Renders the session workspace: writes the candidate ``prompt.yaml``, the
``eval_set.jsonl`` the deterministic scorer runs against, and the
``best_prompt.yaml`` placeholder the agent writes the winner into.

ABI (P5-005 / X-004 §6 — fixed by review C4, 2026-08-15): JSON on stdin,
JSON object on stdout, exit 0/non-zero. The earlier argparse-CLI shape was
incompatible with the governed ``PluginRunner`` (which fails closed on
non-JSON stdout) and was invoked by nothing::

    {"workspace": "<abs path>", "mode": "live" | "dry", "skill_params": {}}

The emitted JSON echoes the rendered file list (the ``BootstrapRunner``
hashes + indexes them into the ``session_bootstrap.v1`` artifact, P5-006).
The eval script itself is NOT copied into the workspace: it executes from
the read-only packaged skill dir via the command policy's ``script_paths``
resolution (review C4) — the agent-writable session workspace must never
supply executable code to a governed command.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from eval.dataset import load_examples

_DEFAULT_PROMPT = """# Candidate prompt — iterate on this template.
You are a helpful assistant. Answer the user's question accurately.
"""

_DEFAULT_EVAL_SET = [
    {"input": "What is 2+2?", "expected": "4"},
    {"input": "Capital of France?", "expected": "Paris"},
]

_RENDERED = ["prompt.yaml", "eval_set.jsonl", "best_prompt.yaml"]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        json.dump({"error": f"invalid stdin JSON: {exc}"}, sys.stdout)
        return 2

    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get("workspace"), str)
        or not payload["workspace"]
    ):
        json.dump({"error": "workspace is required"}, sys.stdout)
        return 2
    workspace = Path(payload["workspace"])
    mode = payload.get("mode", "live")
    if not workspace.is_absolute() or not isinstance(mode, str) or mode not in {"live", "dry"}:
        json.dump({"error": "absolute workspace and live/dry mode required"}, sys.stdout)
        return 2
    params = payload.get("skill_params", {})
    try:
        if not isinstance(params, dict):
            raise ValueError("skill_params must be an object")
        source = params.get("eval_set")
        if source is None and payload.get("demo_mode") is True:
            examples = _DEFAULT_EVAL_SET
        else:
            if not isinstance(source, str) or not source:
                raise ValueError("eval_set is required outside explicit demo")
            source_path = Path(source)
            if not source_path.is_absolute():
                source_path = workspace / source_path
            examples = load_examples(source_path)
        if any(part.is_symlink() for part in (workspace, *workspace.parents)):
            raise ValueError("workspace must not use symlinks")
        for name in _RENDERED:
            target = workspace / name
            if target.is_symlink() or (target.exists() and not target.is_file()):
                raise ValueError("bootstrap destinations must be regular files")
        dataset_text = "".join(json.dumps(example) + "\n" for example in examples)
        target = workspace / "eval_set.jsonl"
        if target.exists() and load_examples(target) != examples:
            raise ValueError("existing eval_set differs; refusing to overwrite")
    except (OSError, ValueError, UnicodeError):
        json.dump({"error": "invalid dataset or unsafe workspace; no files written"}, sys.stdout)
        return 2

    if mode == "dry":
        json.dump({"rendered": _RENDERED, "mode": "dry",
                   "note": "validated; no files written in dry mode"}, sys.stdout)
        return 0

    workspace.mkdir(parents=True, exist_ok=True)
    # Create data only, preserving prompt edits on re-bootstrap. Exclusive
    # creation also rejects a destination symlink introduced after validation.
    for name in ("prompt.yaml", "best_prompt.yaml"):
        try:
            with (workspace / name).open("x", encoding="utf-8") as stream:
                stream.write(_DEFAULT_PROMPT)
        except FileExistsError:
            pass
    if not target.exists():
        with target.open("x", encoding="utf-8") as stream:
            stream.write(dataset_text)

    json.dump({"rendered": _RENDERED, "mode": "live",
               "workspace": str(workspace)}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
