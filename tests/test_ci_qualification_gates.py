"""CI qualification gates: deliberate negative fixtures for every guard.

An advertised feature without executable coverage, an unowned skip, a
drifted qualification input, an incomplete unsupported-capability
report, a secret in archived evidence, or a mislabeled live lane must
each fail the gates; the committed pin file must match live inputs.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

_SPEC = importlib.util.spec_from_file_location(
    "ci_qualification_gates",
    REPO_ROOT / "scripts" / "ci_qualification_gates.py",
)
cqg = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
sys.modules["ci_qualification_gates"] = cqg
_SPEC.loader.exec_module(cqg)


def _fake_run(output: str):
    def run(suites, timeout_s):
        return (0 if "FAILED" not in output else 1), output

    return run


GOOD_OUTPUT = """
tests/test_result_authority.py::test_receipt PASSED [100%]
tests/test_result_authority.py::test_live_thing SKIPPED [100%]
1 passed, 1 skipped in 0.1s
"""


def test_parse_pytest_output_handles_percent_suffixes():
    passed, failed, skipped = cqg.parse_pytest_output(GOOD_OUTPUT)
    assert passed == ["tests/test_result_authority.py::test_receipt"]
    assert skipped == ["tests/test_result_authority.py::test_live_thing"]
    assert failed == []


def test_advertised_feature_without_coverage_fails():
    gate = cqg.Gate(
        "demo", "deterministic",
        ("tests/test_result_authority.py",),
        ("test_result_authority", "test_missing_feature"),
    )
    result = cqg.evaluate_gate(gate, run=_fake_run(GOOD_OUTPUT))
    assert result.status == "fail"
    assert any("missing conformance coverage" in e for e in result.errors)
    assert any("test_missing_feature" in e for e in result.errors)


def test_unowned_skip_fails_and_owned_skip_passes():
    # an owned skip (matches a declared SkipOwner pattern) is fine
    gate = cqg.Gate(
        "demo", "deterministic",
        ("tests/test_result_authority.py",),
        ("test_result_authority",),
    )
    result = cqg.evaluate_gate(
        gate,
        run=_fake_run(GOOD_OUTPUT),
        owners=(cqg.SkipOwner("*live*", "qa", "opt-in live job"),),
    )
    assert result.status == "pass"
    # an unowned skip fails the run
    bad_output = GOOD_OUTPUT.replace("test_live_thing", "test_sneaky_skip")
    result = cqg.evaluate_gate(gate, run=_fake_run(bad_output), owners=())
    assert result.status == "fail"
    assert any("unowned skip" in e for e in result.errors)
    assert any("test_sneaky_skip" in e for e in result.errors)


def test_pinned_input_drift_fails():
    pinned = {"adapters": {"codex": "1.0.0"}, "contract_version": "v1"}
    current = {"adapters": {"codex": "2.0.0"}, "contract_version": "v1"}
    errors = cqg.check_pinned_inputs(pinned, current)
    assert len(errors) == 1
    assert "drift" in errors[0]
    assert "codex" in errors[0]
    # identical inputs pass
    assert cqg.check_pinned_inputs(pinned, dict(pinned)) == []


def test_incomplete_unsupported_capability_report_fails():
    descriptors = [
        {
            "name": "demo",
            "capabilities": ["pause"],
            "unsupported_capabilities": [
                {"capability": "steering", "reason": ""},
            ],
        }
    ]
    errors = cqg.check_unsupported_report(descriptors, ["pause", "resume", "steering"])
    # 'resume' is unadvertised and unreported; 'steering' has no reason
    assert any("resume" in e and "unreported" in e for e in errors)
    assert any("steering" in e and "without a reason" in e for e in errors)
    complete = [
        {
            "name": "demo",
            "capabilities": ["pause"],
            "unsupported_capabilities": [
                {"capability": "resume", "reason": "not advertised"},
                {"capability": "steering", "reason": "not advertised"},
            ],
        }
    ]
    assert cqg.check_unsupported_report(complete, ["pause", "resume", "steering"]) == []


def test_secret_in_evidence_is_found_and_redacted():
    text = "token sk-abcdefghijklmnop123456 and Bearer " + "x" * 30
    findings = cqg.scan_for_secrets(text)
    assert findings
    redacted = cqg.redact(text)
    assert "sk-" not in redacted
    assert "Bearer" not in redacted or "[REDACTED]" in redacted
    # configured secret values are matched too
    assert cqg.scan_for_secrets("plain", ["plain"])
    assert cqg.scan_for_secrets("clean text", ["plain"]) == []


def test_live_gate_is_visibly_separate_and_never_silent():
    gate = cqg.Gate(
        "live-external", "live",
        ("tests/test_codex_harness.py",),
        ("codex_harness",),
        requires_env=(cqg.LIVE_OPT_IN_ENV, cqg.BUDGET_ENV),
    )
    # without opt-in: a declared skip, never a pass
    result = cqg.evaluate_gate(gate, run=_fake_run(GOOD_OUTPUT))
    assert result.status == "skipped-live"
    assert result.status != "pass"
    assert any("not opted in" in e for e in result.errors)
    # opted in but missing required env/budget: fails explicitly
    result = cqg.evaluate_gate(
        gate,
        run=_fake_run(GOOD_OUTPUT),
        live_opt_in=True,
        missing_env=["AUTORESEARCH_CODEX_LIVE"],
    )
    assert result.status == "fail"
    assert any("missing required env" in e for e in result.errors)
    # opted in and complete: it runs and reports kind=live
    live_output = (
        "tests/test_codex_harness.py::test_live_smoke PASSED [100%]\n"
        "1 passed in 0.1s\n"
    )
    result = cqg.evaluate_gate(
        gate, run=_fake_run(live_output), live_opt_in=True
    )
    assert result.kind == "live"
    assert result.status == "pass"


def test_gate_budget_timeout_fails():
    def slow_run(suites, timeout_s):
        raise cqg.subprocess.TimeoutExpired(cmd="pytest", timeout=timeout_s)

    gate = cqg.Gate("demo", "deterministic", ("tests/x.py",), ("x",))
    result = cqg.evaluate_gate(gate, run=slow_run)
    assert result.status == "fail"
    assert any("budget" in e for e in result.errors)


def test_evidence_write_is_sanitized_and_findings_fail(tmp_path):
    payload = {
        "gates": [{"name": "demo"}],
        "leak": "sk-abcdefghijklmnop123456",
    }
    findings = cqg.write_evidence(tmp_path, payload)
    assert findings  # the leak is found
    archived = (tmp_path / "gates.json").read_text()
    assert "sk-abcdefghijklmnop123456" not in archived
    assert "[REDACTED]" in archived
    clean = cqg.write_evidence(tmp_path / "clean", {"gates": []})
    assert clean == []


def test_committed_pin_file_matches_live_inputs():
    """The candidate's pinned qualification inputs match reality."""
    assert cqg.PIN_FILE.exists(), "qualification-inputs.json must be committed"
    pinned = json.loads(cqg.PIN_FILE.read_text())
    current = cqg.collect_current_inputs()
    assert cqg.check_pinned_inputs(pinned, current) == []


def test_capability_report_on_the_real_registry_is_complete():
    descriptors, errors = cqg.collect_capability_report()
    assert errors == []
    names = {d["name"] for d in descriptors}
    assert {"builtin", "codex", "claude-code"} <= names
    for descriptor in descriptors:
        for entry in descriptor["unsupported_capabilities"]:
            assert entry["reason"]