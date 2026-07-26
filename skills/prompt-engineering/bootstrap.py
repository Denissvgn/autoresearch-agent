"""P4-015 — Minimal bootstrap.py for the prompt-engineering skill (ARC-011).

Renders the session workspace: writes a placeholder ``prompt.yaml`` and
``eval_set.jsonl`` so the agent can start iterating immediately. This is the
Phase-4 minimal bootstrap; the full ``BootstrapRunner`` (P5-005) replaces it
with a governed-subprocess model in Phase 5.

Run by the session start path via a governed command::

    .venv/bin/python bootstrap.py --workspace <path>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


_DEFAULT_PROMPT = """# Candidate prompt — iterate on this template.
You are a helpful assistant. Answer the user's question accurately.
"""

_DEFAULT_EVAL_SET = [
    {"input": "What is 2+2?", "expected": "4"},
    {"input": "Capital of France?", "expected": "Paris"},
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap the prompt-engineering workspace")
    parser.add_argument("--workspace", required=True, help="Session workspace path")
    args = parser.parse_args()

    ws = Path(args.workspace)
    ws.mkdir(parents=True, exist_ok=True)

    # Write the initial prompt template.
    (ws / "prompt.yaml").write_text(_DEFAULT_PROMPT, encoding="utf-8")

    # Write a minimal eval set (JSONL — one JSON object per line).
    with open(ws / "eval_set.jsonl", "w", encoding="utf-8") as f:
        for example in _DEFAULT_EVAL_SET:
            f.write(json.dumps(example) + "\n")

    # Write a best_prompt.yaml placeholder (the agent writes the winner here).
    (ws / "best_prompt.yaml").write_text(_DEFAULT_PROMPT, encoding="utf-8")

    print(f"Bootstrapped prompt-engineering workspace at {ws}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
