#!/usr/bin/env python3
"""Execution-ledger validator: fail closed on inconsistent task state.

Validates the private execution ledger set (cards, run, gates, prerequisites,
decisions) that a long-running implementation effort keeps to make progress
durable and auditable. Checks card-ID well-formedness, dependency resolution
and acyclicity, state/transition legality, acceptance-to-check references, and
closure-evidence completeness for completed records.

Card IDs are treated as opaque strings validated against the ledger's own
registry plus a generic pattern; no planning vocabulary is hard-coded here.
Run at every state change and on resume.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

CARD_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]{0,15}$")
CHECK_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.]{0,63}$")

STATES = frozenset({
    "PENDING", "INACTIVE", "READY", "IN_PROGRESS",
    "VERIFYING", "REWORK", "WAITING_EXTERNAL", "DONE",
})

# Legal state transitions (from -> allowed to). Self-loops are not recorded.
TRANSITIONS: dict[str, frozenset[str]] = {
    "PENDING": frozenset({"READY", "INACTIVE"}),
    "INACTIVE": frozenset({"PENDING", "READY"}),
    "READY": frozenset({"IN_PROGRESS", "WAITING_EXTERNAL", "PENDING"}),
    "IN_PROGRESS": frozenset({"VERIFYING", "REWORK", "WAITING_EXTERNAL"}),
    "VERIFYING": frozenset({"DONE", "REWORK", "WAITING_EXTERNAL"}),
    "REWORK": frozenset({"IN_PROGRESS", "WAITING_EXTERNAL"}),
    "WAITING_EXTERNAL": frozenset({"READY", "PENDING", "INACTIVE"}),
    "DONE": frozenset({"REWORK"}),
}

RESULT_STATES = frozenset({"PASS", "FAIL", "SKIP", "INCONCLUSIVE"})

REQUIRED_RECORD_FIELDS = (
    "card_id", "status", "depends_on", "acceptance", "verification_recipe",
    "verification_results", "review", "attempt_history", "updated_at",
)


class LedgerError(Exception):
    """Raised for structural problems that make the ledger uninterpretable."""


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise LedgerError(f"missing ledger file: {path.name}") from None
    except json.JSONDecodeError as exc:
        raise LedgerError(f"unparseable JSON in {path.name}: {exc}") from exc


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise LedgerError(f"missing ledger file: {path.name}")
    rows = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise LedgerError(
                f"unparseable JSONL at {path.name}:{n}: {exc}") from exc
    return rows


def validate_cards(cards_doc: dict, errors: list[str]) -> set[str]:
    """Validate the card registry; returns the set of known card IDs."""
    cards = cards_doc.get("cards")
    if not isinstance(cards, list) or not cards:
        errors.append("cards.json: 'cards' must be a non-empty list")
        return set()
    known: set[str] = set()
    for i, rec in enumerate(cards):
        where = f"cards[{i}]"
        missing = [f for f in REQUIRED_RECORD_FIELDS if f not in rec]
        if missing:
            errors.append(f"{where}: missing required fields {missing}")
            continue
        cid = rec["card_id"]
        if not isinstance(cid, str) or not CARD_ID_RE.match(cid):
            errors.append(f"{where}: malformed card_id {cid!r}")
            continue
        if cid in known:
            errors.append(f"{where}: duplicate card_id {cid!r}")
        known.add(cid)
        where = f"card {cid}"
        if rec["status"] not in STATES:
            errors.append(f"{where}: unknown status {rec['status']!r}")
        if not isinstance(rec["depends_on"], list):
            errors.append(f"{where}: depends_on must be a list")
        for entry in rec["attempt_history"]:
            src = entry.get("from")
            dst = entry.get("to")
            if src not in STATES or dst not in STATES:
                errors.append(f"{where}: attempt_history has unknown states {src!r}->{dst!r}")
            elif dst != src and dst not in TRANSITIONS[src]:
                errors.append(f"{where}: illegal transition {src} -> {dst}")
        if rec["attempt_history"]:
            last = rec["attempt_history"][-1]
            if last.get("to") != rec["status"]:
                errors.append(
                    f"{where}: status {rec['status']!r} contradicts last "
                    f"transition to {last.get('to')!r}"
                )
        _validate_acceptance(rec, errors)
    return known


def _validate_acceptance(rec: dict, errors: list[str]) -> None:
    cid = rec.get("card_id", "?")
    where = f"card {cid}"
    recipe_checks = set()
    for entry in rec["verification_recipe"]:
        chk = entry.get("check_id")
        if not isinstance(chk, str) or not CHECK_ID_RE.match(chk):
            errors.append(f"{where}: malformed check_id {chk!r} in verification_recipe")
        elif chk in recipe_checks:
            errors.append(f"{where}: duplicate check_id {chk!r} in verification_recipe")
        else:
            recipe_checks.add(chk)
    accepted = set()
    for acc in rec["acceptance"]:
        aid = acc.get("id")
        if not isinstance(aid, str) or not aid:
            errors.append(f"{where}: acceptance entry without id")
            continue
        if aid in accepted:
            errors.append(f"{where}: duplicate acceptance id {aid!r}")
        accepted.add(aid)
        for chk in acc.get("check_ids", []):
            if chk not in recipe_checks:
                errors.append(f"{where}: acceptance {aid} references unknown check {chk!r}")
        if not isinstance(acc.get("satisfied"), bool):
            errors.append(f"{where}: acceptance {aid} missing boolean 'satisfied'")
    for res in rec["verification_results"]:
        chk = res.get("check_id")
        if chk not in recipe_checks:
            errors.append(f"{where}: verification result references unknown check {chk!r}")
        if res.get("status") not in RESULT_STATES:
            errors.append(f"{where}: check {chk!r} has unknown result status {res.get('status')!r}")


def validate_dependencies(cards_doc: dict, known: set[str], errors: list[str]) -> None:
    """Dependency references must resolve and the graph must be acyclic."""
    cards = cards_doc.get("cards") or []
    graph: dict[str, list[str]] = {}
    for rec in cards:
        cid = rec.get("card_id")
        if cid not in known:
            continue
        deps = rec.get("depends_on") or []
        bad = [d for d in deps if d not in known]
        if bad:
            errors.append(f"card {cid}: depends on unknown cards {bad}")
        if cid in deps:
            errors.append(f"card {cid}: depends on itself")
        graph[cid] = [d for d in deps if d in known]
    # Iterative DFS cycle detection across every node.
    state = {c: 0 for c in graph}
    for root in graph:
        if state[root] != 0:
            continue
        stack = [(root, iter(graph[root]))]
        state[root] = 1
        while stack:
            node, it = stack[-1]
            advanced = False
            for dep in it:
                if state.get(dep) == 1:
                    errors.append(f"dependency cycle involving {dep!r}")
                elif state.get(dep) == 0:
                    state[dep] = 1
                    stack.append((dep, iter(graph[dep])))
                    advanced = True
                    break
            if not advanced:
                state[node] = 2
                stack.pop()


def validate_closure(cards_doc: dict, errors: list[str]) -> None:
    """A DONE record requires complete, passing, current closure evidence."""
    cards = cards_doc.get("cards") or []
    status_by_id = {c.get("card_id"): c.get("status") for c in cards}
    for rec in cards:
        cid = rec.get("card_id", "?")
        where = f"card {cid}"
        deps = rec.get("depends_on") or []
        unfinished = [d for d in deps if status_by_id.get(d) != "DONE"]
        if rec.get("status") == "DONE" and unfinished:
            errors.append(f"{where}: DONE but prerequisite cards not DONE: {unfinished}")
        if rec.get("status") != "DONE":
            continue
        review = rec.get("review") or {}
        if not review.get("complete"):
            errors.append(f"{where}: DONE without review marked complete")
        for finding in review.get("findings") or []:
            if not finding.get("resolved"):
                errors.append(f"{where}: DONE with unresolved review finding")
        for acc in rec.get("acceptance") or []:
            if not acc.get("satisfied"):
                errors.append(f"{where}: DONE with unsatisfied acceptance {acc.get('id')!r}")
        results = {r.get("check_id"): r for r in rec.get("verification_results") or []}
        for entry in rec.get("verification_recipe") or []:
            chk = entry.get("check_id")
            res = results.get(chk)
            if res is None:
                errors.append(f"{where}: DONE without result for check {chk!r}")
            elif res.get("status") != "PASS":
                errors.append(f"{where}: DONE with check {chk!r} status {res.get('status')!r}")
        if not rec.get("source_commit"):
            errors.append(f"{where}: DONE without source_commit")
        if not rec.get("implementation_commits"):
            errors.append(f"{where}: DONE without implementation_commits")


def validate_side_files(ledger_dir: Path, known: set[str], errors: list[str]) -> None:
    """run/gates/prerequisites/decisions must parse and cross-reference cleanly."""
    run = _load_json(ledger_dir / "run.json")
    for field in ("run_id", "completion_target", "active_card", "base_commit"):
        if not run.get(field):
            errors.append(f"run.json: missing {field!r}")
    active = run.get("active_card")
    if active is not None and known and active not in known:
        errors.append(f"run.json: active_card {active!r} is not a known card")

    gates = _load_json(ledger_dir / "gates.json")
    if not isinstance(gates.get("named_gates"), list) or not gates.get("named_gates"):
        errors.append("gates.json: 'named_gates' must be a non-empty list")

    prereqs = _load_json(ledger_dir / "prerequisites.json")
    rows = prereqs.get("prerequisites")
    if not isinstance(rows, list):
        errors.append("prerequisites.json: 'prerequisites' must be a list")
    else:
        pids = set()
        for row in rows:
            pid = row.get("id")
            if not pid or pid in pids:
                errors.append(f"prerequisites.json: missing or duplicate id {pid!r}")
            pids.add(pid)
            if row.get("status") not in {"AVAILABLE", "MISSING", "DENIED", "UNVERIFIED"}:
                errors.append(f"prerequisite {pid}: unknown status {row.get('status')!r}")

    decisions = _load_jsonl(ledger_dir / "decisions.jsonl")
    seen = set()
    for row in decisions:
        did = row.get("decision_id")
        if not did or did in seen:
            errors.append(f"decisions.jsonl: missing or duplicate decision_id {did!r}")
        seen.add(did)
        for field in ("question", "resolution", "evidence", "timestamp", "reopening_trigger"):
            if not row.get(field):
                errors.append(f"decision {did}: missing {field!r}")


def validate_ledger(ledger_dir: Path) -> list[str]:
    """Run every check; return the list of errors found (empty = valid)."""
    errors: list[str] = []
    try:
        cards_doc = _load_json(ledger_dir / "cards.json")
        known = validate_cards(cards_doc, errors)
        if known:
            validate_dependencies(cards_doc, known, errors)
            validate_closure(cards_doc, errors)
            validate_side_files(ledger_dir, known, errors)
    except LedgerError as exc:
        errors.append(str(exc))
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate an execution ledger directory.")
    ap.add_argument("ledger_dir", type=Path)
    args = ap.parse_args()
    errors = validate_ledger(args.ledger_dir)
    if errors:
        print(f"ledger INVALID: {len(errors)} error(s)")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("ledger OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
