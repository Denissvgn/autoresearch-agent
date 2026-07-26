#!/usr/bin/env python3
"""Prompt-engineering eval scorer (ARC-011 P4-014).

Scores a candidate prompt against a labeled eval set and emits an
``ITERATION_RESULT:`` JSON marker carrying the W11 anti-forgery nonce
(``server_nonce``, read from ``AUTORESEARCH_SESSION_NONCE``).

The scorer is deliberately deterministic: it derives a composite score from a
hash of the prompt text so the e2e test (P4-016) gets reproducible metrics
without an external LLM scorer. A real deployment would replace the scoring
body with a call to ``--scorer-url``; the marker contract (nonce + fields) stays
the same.

Usage::

    .venv/bin/python eval/run.py --prompt prompt.yaml --eval eval_set.jsonl
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys


def _score_prompt(prompt_text: str, eval_examples: list[dict]) -> dict:
    """Derive deterministic metrics from the prompt text + eval set size.

    A real scorer calls an external endpoint; this deterministic stub hashes the
    prompt to produce a stable composite score in [0, 1), precision, and a cost
    estimate. The gates (passes_min_precision, within_cost_budget) are derived
    from the score so the orchestrator's phase logic exercises real decisions.
    """
    h = int(hashlib.sha256(prompt_text.encode()).hexdigest(), 16)
    composite = (h % 10000) / 10000.0  # [0, 1)
    precision = ((h >> 16) % 10000) / 10000.0  # [0, 1)
    n = len(eval_examples)
    mean_cost_usd = 0.01 * n  # $0.01 per eval example

    passes_min_precision = precision >= 0.6
    within_cost_budget = mean_cost_usd <= 0.50

    return {
        "status": "completed",
        "primary_metric": round(composite, 6),
        "metric_name": "composite_eval_score",
        "precision": round(precision, 6),
        "passes_min_precision": passes_min_precision,
        "within_cost_budget": within_cost_budget,
        "mean_cost_usd": round(mean_cost_usd, 4),
        "n_eval_examples": n,
        "composite_eval_score": round(composite, 6),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Score a candidate prompt")
    parser.add_argument("--prompt", required=True, help="Path to the prompt file")
    parser.add_argument("--eval", required=True, help="Path to the eval set (JSONL)")
    args = parser.parse_args()

    # Read the prompt.
    try:
        with open(args.prompt, encoding="utf-8") as f:
            prompt_text = f.read()
    except OSError as exc:
        print(f"eval_error: cannot read prompt: {exc}", file=sys.stderr)
        _emit(status="eval_error", error=str(exc))
        return 1

    # Read the eval set (JSONL — one JSON object per line).
    eval_examples: list[dict] = []
    try:
        with open(args.eval, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    eval_examples.append(json.loads(line))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"eval_error: cannot read eval set: {exc}", file=sys.stderr)
        _emit(status="eval_error", error=str(exc))
        return 1

    # Score.
    metrics = _score_prompt(prompt_text, eval_examples)
    _emit(**metrics)
    return 0


def _emit(**fields: object) -> None:
    """Emit an ``ITERATION_RESULT:`` JSON line with the anti-forgery nonce."""
    nonce = os.environ.get("AUTORESEARCH_SESSION_NONCE", "")
    payload = dict(fields)
    payload["server_nonce"] = nonce
    # Ensure required fields are present (the parser checks for them).
    payload.setdefault("status", "completed")
    payload.setdefault("primary_metric", 0.0)
    payload.setdefault("metric_name", "composite_eval_score")
    payload.setdefault("n_eval_examples", 0)
    print("ITERATION_RESULT: " + json.dumps(payload), flush=True)


if __name__ == "__main__":
    sys.exit(main())
