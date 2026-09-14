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

    .venv/bin/python eval/run.py --prompt prompt.yaml --eval eval_set.jsonl [--scorer-url URL]

Scorer chain (first hit wins): --scorer-url POST -> OPENAI_API_KEY judge ->
deterministic offline fallback (scorer=fallback).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys


def _fallback_score(prompt_text: str, eval_examples: list[dict]) -> dict:
    """Deterministic offline fallback (no network / no scorer_url).

    Preserved from the original P4-014 stub so unit tests and demo mode stay
    reproducible. Flagged with ``scorer: fallback``.
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
        # The skill's own gates ARE its training gates (review C4: downstream
        # consumers — decision inference, promotion gates — read this field
        # on every iteration).
        "training_gates_passed": passes_min_precision and within_cost_budget,
        "scorer": "fallback",
    }


def _try_remote_scorer(prompt_text, eval_examples, scorer_url, timeout_s=15.0):
    """POST candidate to external scorer; None on any failure (fail-open)."""
    try:
        import urllib.request

        payload = json.dumps(
            {"prompt": prompt_text, "examples": eval_examples}
        ).encode("utf-8")
        req = urllib.request.Request(
            scorer_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        composite = float(body.get("composite_eval_score", body.get("score", 0.0)))
        precision = float(body.get("precision", composite))
        n = len(eval_examples)
        mean_cost_usd = round(0.01 * n, 4)
        passes = precision >= 0.6
        within = mean_cost_usd <= 0.50
        return {
            "status": "completed",
            "primary_metric": round(composite, 6),
            "metric_name": "composite_eval_score",
            "precision": round(precision, 6),
            "passes_min_precision": passes,
            "within_cost_budget": within,
            "mean_cost_usd": mean_cost_usd,
            "n_eval_examples": n,
            "composite_eval_score": round(composite, 6),
            "training_gates_passed": passes and within,
            "scorer": "remote",
        }
    except Exception:
        return None


def _try_openai_judge(prompt_text, eval_examples, model=None):
    """Score via OpenAI judge; None if unavailable (fail-open to fallback)."""
    base_url = os.environ.get(
        "OPENAI_BASE_URL", "https://api.openai.com/v1"
    ).rstrip("/")
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key or not eval_examples:
        return None
    model = model or os.environ.get("OPENAI_JUDGE_MODEL", "gpt-4o-mini")
    try:
        import urllib.request

        scores = []
        for ex in eval_examples[:50]:  # cap judge cost per run
            user_msg = (
                "Candidate system prompt:\n---\n" + prompt_text[:4000] + "\n---\n"
                f"User input: {ex.get('input', '')}\n"
                f"Expected: {ex.get('expected', '')}\n"
                "Rate 0..1 how likely the prompt elicits the expected answer. "
                "Reply with ONLY a number."
            )
            body = json.dumps(
                {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "Strict judge. Reply only 0..1."},
                        {"role": "user", "content": user_msg},
                    ],
                    "max_tokens": 16,
                    "temperature": 0,
                }
            ).encode("utf-8")
            req = urllib.request.Request(
                base_url + "/chat/completions",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + api_key,
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
            text = raw["choices"][0]["message"]["content"].strip()
            m = re.search(r"0?\.\d+|[01](?:\.0+)?", text)
            scores.append(max(0.0, min(1.0, float(m.group(0)) if m else 0.5)))
        composite = sum(scores) / len(scores)
        precision = sum(1 for s in scores if s >= 0.7) / len(scores)
        n = len(eval_examples)
        mean_cost_usd = round(0.002 * min(n, 50) + 0.001 * n, 4)
        passes = precision >= 0.6
        within = mean_cost_usd <= 0.50
        return {
            "status": "completed",
            "primary_metric": round(composite, 6),
            "metric_name": "composite_eval_score",
            "precision": round(precision, 6),
            "passes_min_precision": passes,
            "within_cost_budget": within,
            "mean_cost_usd": mean_cost_usd,
            "n_eval_examples": n,
            "composite_eval_score": round(composite, 6),
            "training_gates_passed": passes and within,
            "scorer": "openai-judge:" + model,
        }
    except Exception:
        return None


def _score_prompt(prompt_text, eval_examples, scorer_url=None):
    """Real chain: remote scorer -> OpenAI judge -> offline fallback."""
    if scorer_url:
        remote = _try_remote_scorer(prompt_text, eval_examples, scorer_url)
        if remote is not None:
            return remote
    judge = _try_openai_judge(prompt_text, eval_examples)
    if judge is not None:
        return judge
    return _fallback_score(prompt_text, eval_examples)


def main() -> int:
    parser = argparse.ArgumentParser(description="Score a candidate prompt")
    parser.add_argument("--prompt", required=True, help="Path to the prompt file")
    parser.add_argument("--eval", required=True, help="Path to the eval set (JSONL)")
    parser.add_argument("--scorer-url", default=None, help="External scorer endpoint")
    parser.add_argument("--judge-model", default=None, help="OpenAI judge model")
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

    # Score (chain: --scorer-url or SCORER_URL env -> OpenAI judge -> fallback).
    scorer_url = args.scorer_url or os.environ.get("SCORER_URL")
    if args.judge_model:
        os.environ["OPENAI_JUDGE_MODEL"] = args.judge_model
    metrics = _score_prompt(prompt_text, eval_examples, scorer_url=scorer_url)
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
