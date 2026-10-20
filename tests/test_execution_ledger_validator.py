
"""Tests for the execution-ledger validator (scripts/check_execution_ledger.py).

Fixtures use synthetic opaque card IDs; no real planning vocabulary appears
here by design — the validator must stay domain-agnostic.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "check_execution_ledger", REPO_ROOT / "scripts" / "check_execution_ledger.py"
)
assert _SPEC is not None
cel = importlib.util.module_from_spec(_SPEC)
sys.modules["check_execution_ledger"] = cast(ModuleType, cel)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(cel)


def _card(cid: str, **overrides) -> dict:
    rec = {
        "card_id": cid,
        "status": "PENDING",
        "depends_on": [],
        "acceptance": [
            {"id": f"{cid}.A1", "criterion": "demo", "check_ids": [f"{cid}.C1"],
             "satisfied": True},
        ],
        "verification_recipe": [
            {"check_id": f"{cid}.C1", "command": "true"},
        ],
        "verification_results": [],
        "review": {"kind": "self-review", "findings": [], "complete": False},
        "source_commit": None,
        "implementation_commits": [],
        "attempt_history": [],
        "updated_at": "2026-10-15T00:00:00Z",
    }
    rec.update(overrides)
    return rec


def _done_card(cid: str, **overrides) -> dict:
    rec = _card(
        cid,
        status="DONE",
        attempt_history=[{"from": "READY", "to": "IN_PROGRESS"},
                         {"from": "IN_PROGRESS", "to": "VERIFYING"},
                         {"from": "VERIFYING", "to": "DONE"}],
        verification_results=[{"check_id": f"{cid}.C1", "status": "PASS"}],
        review={"kind": "self-review", "findings": [], "complete": True},
        source_commit="abc123",
        implementation_commits=["abc123"],
    )
    rec.update(overrides)
    return rec


def _write_ledger(tmp_path: Path, cards: list[dict], **side_tweaks) -> Path:
    (tmp_path / "cards.json").write_text(
        json.dumps({"schema_version": 1, "run_id": "r", "cards": cards}))
    run = {"run_id": "r", "completion_target": "T", "active_card": cards[0]["card_id"],
           "base_commit": "abc123"}
    run.update(side_tweaks.get("run", {}))
    (tmp_path / "run.json").write_text(json.dumps(run))
    (tmp_path / "gates.json").write_text(json.dumps(
        {"named_gates": [{"gate_id": "G", "name": "g", "closing_card": "T"}]}))
    (tmp_path / "prerequisites.json").write_text(json.dumps(
        {"prerequisites": [{"id": "P", "status": "MISSING"}]}))
    (tmp_path / "decisions.jsonl").write_text(json.dumps(
        {"decision_id": "D", "question": "q", "resolution": "r", "evidence": "e",
         "timestamp": "t", "reopening_trigger": "x"}) + "\n")
    return tmp_path


def test_valid_minimal_ledger_passes(tmp_path):
    d = _write_ledger(tmp_path, [_card("T001")])
    assert cel.validate_ledger(d) == []


def test_unknown_dependency_card_rejected(tmp_path):
    d = _write_ledger(tmp_path, [_card("T001", depends_on=["NOPE"])])
    errors = cel.validate_ledger(d)
    assert any("unknown cards" in e for e in errors)


def test_duplicate_card_id_rejected(tmp_path):
    d = _write_ledger(tmp_path, [_card("T001"), _card("T001")])
    errors = cel.validate_ledger(d)
    assert any("duplicate card_id" in e for e in errors)


def test_malformed_card_id_rejected(tmp_path):
    d = _write_ledger(tmp_path, [_card("bad id!")])
    errors = cel.validate_ledger(d)
    assert any("malformed card_id" in e for e in errors)


def test_unknown_state_rejected(tmp_path):
    d = _write_ledger(tmp_path, [_card("T001", status="HALTED")])
    errors = cel.validate_ledger(d)
    assert any("unknown status" in e for e in errors)


def test_illegal_transition_rejected(tmp_path):
    d = _write_ledger(tmp_path, [_card("T001", attempt_history=[
        {"from": "PENDING", "to": "DONE"}])])
    errors = cel.validate_ledger(d)
    assert any("illegal transition" in e for e in errors)


def test_status_contradicting_history_rejected(tmp_path):
    d = _write_ledger(tmp_path, [_card("T001", status="READY", attempt_history=[
        {"from": "PENDING", "to": "READY"}, {"from": "READY", "to": "IN_PROGRESS"}])])
    errors = cel.validate_ledger(d)
    assert any("contradicts last transition" in e for e in errors)


def test_dependency_cycle_rejected(tmp_path):
    d = _write_ledger(tmp_path, [
        _card("T001", depends_on=["T002"]), _card("T002", depends_on=["T001"])])
    errors = cel.validate_ledger(d)
    assert any("cycle" in e for e in errors)


def test_done_without_evidence_rejected(tmp_path):
    """A DONE record missing results/review/commits must not validate."""
    d = _write_ledger(tmp_path, [_done_card(
        "T001",
        verification_results=[],
        review={"kind": "self-review", "findings": [], "complete": False},
        implementation_commits=[],
    )])
    errors = cel.validate_ledger(d)
    assert any("without result for check" in e for e in errors)
    assert any("without review marked complete" in e for e in errors)
    assert any("without implementation_commits" in e for e in errors)


def test_done_with_failed_check_rejected(tmp_path):
    d = _write_ledger(tmp_path, [_done_card(
        "T001", verification_results=[{"check_id": "T001.C1", "status": "SKIP"}])])
    errors = cel.validate_ledger(d)
    assert any("status 'SKIP'" in e for e in errors)


def test_done_with_unsatisfied_acceptance_rejected(tmp_path):
    d = _write_ledger(tmp_path, [_done_card(
        "T001",
        acceptance=[{"id": "T001.A1", "criterion": "demo",
                     "check_ids": ["T001.C1"], "satisfied": False}],
    )])
    errors = cel.validate_ledger(d)
    assert any("unsatisfied acceptance" in e for e in errors)


def test_done_with_unfinished_prerequisite_rejected(tmp_path):
    d = _write_ledger(tmp_path, [
        _done_card("T001", depends_on=["T002"]), _card("T002")])
    errors = cel.validate_ledger(d)
    assert any("prerequisite cards not DONE" in e for e in errors)


def test_done_with_unresolved_review_finding_rejected(tmp_path):
    d = _write_ledger(tmp_path, [_done_card(
        "T001",
        review={"kind": "self-review",
                "findings": [{"summary": "gap", "resolved": False}],
                "complete": True})])
    errors = cel.validate_ledger(d)
    assert any("unresolved review finding" in e for e in errors)


def test_fully_evidenced_done_record_passes(tmp_path):
    d = _write_ledger(tmp_path, [_done_card("T001")])
    assert cel.validate_ledger(d) == []


def test_acceptance_unknown_check_reference_rejected(tmp_path):
    d = _write_ledger(tmp_path, [_card("T001", acceptance=[
        {"id": "T001.A1", "criterion": "demo", "check_ids": ["T001.GHOST"],
         "satisfied": True}])])
    errors = cel.validate_ledger(d)
    assert any("unknown check 'T001.GHOST'" in e for e in errors)


def test_result_unknown_check_reference_rejected(tmp_path):
    d = _write_ledger(tmp_path, [_card("T001", verification_results=[
        {"check_id": "T001.GHOST", "status": "PASS"}])])
    errors = cel.validate_ledger(d)
    assert any("unknown check 'T001.GHOST'" in e for e in errors)


def test_missing_ledger_file_is_error_not_crash(tmp_path):
    errors = cel.validate_ledger(tmp_path)
    assert any("missing ledger file" in e for e in errors)


def test_active_card_must_be_known(tmp_path):
    d = _write_ledger(tmp_path, [_card("T001")], run={"active_card": "NOPE"})
    errors = cel.validate_ledger(d)
    assert any("active_card" in e for e in errors)


def test_real_ledger_directory_is_valid():
    """The live run ledger must validate whenever it is present."""
    ledger = REPO_ROOT / "workspace" / "autonomous-implementation"
    if not (ledger / "cards.json").exists():
        pytest.skip("no run ledger present in this checkout")
    assert cel.validate_ledger(ledger) == []