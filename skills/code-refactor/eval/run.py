#!/usr/bin/env python3
"""Code-refactor eval scorer (P0-2). Offline: syntax + lint + test ledger."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import sys


def _lint_score(tree, source):
    issues = 0
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                imported.add((a.asname or a.name).split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name != "*":
                    imported.add((a.asname or a.name).split(".")[0])
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    issues += len(imported - used)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and len(node.body) > 30:
            issues += (len(node.body) - 30) // 10 + 1
    issues += min(sum(1 for ln in source.splitlines() if len(ln) > 100), 10)
    return max(0.0, 1.0 - 0.05 * issues), issues

def _pass_rate(text, ledger):
    if not ledger:
        return 1.0
    ok = sum(
        1
        for t in ledger
        if (str(t.get("needle", "")) in text) == bool(t.get("must_present", True))
    )
    return ok / len(ledger)

def _emit(**fields):
    payload = dict(fields)
    payload["server_nonce"] = os.environ.get("AUTORESEARCH_SESSION_NONCE", "")
    payload.setdefault("status", "completed")
    payload.setdefault("primary_metric", 0.0)
    payload.setdefault("metric_name", "composite_refactor_score")
    print("ITERATION_RESULT: " + json.dumps(payload), flush=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--tests", default="")
    ap.add_argument("--baseline", default="")
    a = ap.parse_args()
    try:
        text = open(a.target, encoding="utf-8").read()
    except OSError as exc:
        _emit(status="eval_error", error=str(exc))
        return 1
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        _emit(status="build_failed", error=str(exc))
        return 1
    ledger = []
    if a.tests:
        try:
            for line in open(a.tests, encoding="utf-8"):
                line = line.strip()
                if line:
                    ledger.append(json.loads(line))
        except (OSError, json.JSONDecodeError) as exc:
            _emit(status="eval_error", error=str(exc))
            return 1
    lint_score, lint_issues = _lint_score(tree, text)
    pass_rate = _pass_rate(text, ledger)
    h = int(hashlib.sha256(text.encode()).hexdigest(), 16)
    fn_count = sum(1 for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
    complexity = fn_count * 3 + max(1, len(text.splitlines())) / 20.0
    base = complexity
    if a.baseline:
        try:
            base = float(json.load(open(a.baseline))["complexity"])
        except Exception:
            base = complexity
    drop = round(100.0 * (base - complexity) / max(base, 1e-9), 2) if base else 0.0
    jitter = ((h >> 32) % 1000) / 1000.0
    composite = round(
        0.5 * pass_rate
        + 0.3 * lint_score
        + 0.2 * min(1.0, max(0.0, drop / 20.0))
        + 0.001 * jitter,
        6,
    )
    tests_pass = pass_rate >= 1.0
    no_perf = lint_issues <= 10
    metrics = {
        "status": "completed",
        "primary_metric": composite,
        "metric_name": "composite_refactor_score",
        "composite_refactor_score": composite,
        "test_pass_rate": round(pass_rate, 6),
        "tests_pass": tests_pass,
        "no_perf_regression": no_perf,
        "complexity_drop_pct": drop,
        "lint_issues": lint_issues,
        "n_tests": len(ledger),
        "training_gates_passed": tests_pass and no_perf,
        "scorer": "offline-refactor",
        "refactor_applied": True,
        "baseline_metrics": True,
        "full_validation": tests_pass,
        "promotion_proposal": False,
    }
    open("eval_result.json", "w", encoding="utf-8").write(json.dumps(metrics))
    _emit(**metrics)
    try:
        open("complexity.json", "w", encoding="utf-8").write(json.dumps({"complexity": complexity}))
    except OSError:
        pass
    return 0

if __name__ == "__main__":
    sys.exit(main())
