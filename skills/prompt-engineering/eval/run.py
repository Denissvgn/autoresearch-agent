#!/usr/bin/env python3
"""Fail-closed prompt scoring with an explicit remote endpoint or demo mode.

The server must force --eval, --scorer-url and --demo at execution time.
Ambient provider credentials and scorer URLs are deliberately ignored.
Remote errors never fall through to synthetic success, even in demo mode.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from urllib.parse import urlsplit

from dataset import load_examples


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
    """POST to the explicit endpoint; None means failure, never fallback."""
    try:
        import urllib.request

        url = urlsplit(scorer_url)
        if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password or url.fragment:
            raise ValueError("invalid scorer URL")
        payload = json.dumps(
            {"prompt": prompt_text, "examples": eval_examples}
        ).encode("utf-8")
        req = urllib.request.Request(
            scorer_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                raise ValueError("scorer redirects are not allowed")

        opener = urllib.request.build_opener(NoRedirect)
        with opener.open(req, timeout=timeout_s) as resp:
            raw = resp.read(1024 * 1024 + 1)
            if resp.status != 200 or len(raw) > 1024 * 1024:
                raise ValueError("invalid scorer response")
            body = json.loads(raw.decode("utf-8"))
        if not isinstance(body, dict) or body.get("status", "completed") != "completed":
            raise ValueError("scorer did not complete")
        composite = body.get("composite_eval_score", body.get("score"))
        precision = body.get("precision", composite)
        for value in (composite, precision):
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError("scorer metrics must be finite numbers in [0, 1]")
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


def _score_prompt(prompt_text, eval_examples, scorer_url=None, *, demo=False):
    if scorer_url:
        remote = _try_remote_scorer(prompt_text, eval_examples, scorer_url)
        if remote is not None:
            return remote
        return _error("remote scorer failed", len(eval_examples))
    if demo is True:
        return _fallback_score(prompt_text, eval_examples)
    return _error("live evaluation requires --scorer-url", len(eval_examples))


def _error(message, n=0):
    return {
        "status": "eval_error", "error": message, "primary_metric": None,
        "n_eval_examples": n, "training_gates_passed": False,
        "passes_min_precision": False, "within_cost_budget": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Score a candidate prompt", allow_abbrev=False)
    parser.add_argument("--prompt", required=True, help="Path to the prompt file")
    parser.add_argument("--eval", required=True, help="Path to the eval set (JSONL)")
    parser.add_argument("--scorer-url", default=None, help="External scorer endpoint")
    parser.add_argument("--demo", choices=("true", "false"), default="false",
                        help="Server-controlled synthetic demo scoring (default false)")
    args = parser.parse_args()

    # Read the prompt.
    try:
        with open(args.prompt, encoding="utf-8") as f:
            prompt_text = f.read()
    except (OSError, UnicodeError):
        _emit(**_error("cannot read prompt"))
        return 1

    try:
        eval_examples = load_examples(args.eval)
    except (OSError, ValueError, UnicodeError):
        _emit(**_error("invalid eval set"))
        return 1

    metrics = _score_prompt(prompt_text, eval_examples,
                            scorer_url=args.scorer_url, demo=args.demo == "true")
    _emit(**metrics)
    return 0 if metrics["status"] == "completed" else 1


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
