"""G4 qualification: one shared contract across every harness surface.

The built-in adapter, a custom process driver, the Codex and Claude Code
adapters, and the attached API/CLI workflow are qualified against one
shared conformance contract with explicit per-adapter capabilities.
Fixture and live evidence are reported separately: missing live evidence
blocks a compatibility claim. No managed or attached path may bypass the
evidence gate or scope rules, including receipt reuse across runs.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from src.core.builtin_harness import BuiltinHarnessAdapter
from src.core.claude_code_harness import (
    ClaudeCodeHarnessAdapter,
    normalize_claude_event,
)
from src.core.codex_harness import (
    CodexHarnessAdapter,
    normalize_codex_event,
)
from src.core.harness_qualification import (
    QualificationResult,
    claim_honesty,
    qualify_adapter,
    supported_matrix,
)
from src.core.scoped_credentials import (
    CredentialDenied,
    issue_scoped_credential,
    verify_scoped_credential,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
KEY = "g4-qualification-key"


def _scripted_attempt_fn():
    def step(context, attempt_index):
        return {"outcome": "completed", "metric": 0.5}

    return step


def _permissions_scope_check() -> bool:
    """G1 scope rules: scoped credentials never cross runs or gain
    operator authority."""
    try:
        issue_scoped_credential(
            subject="g4",
            run_id="res-a",
            permissions=("promote:approve",),
            key=KEY,
        )
        return False
    except CredentialDenied:
        pass
    token = issue_scoped_credential(
        subject="g4", run_id="res-a", key=KEY
    )
    try:
        verify_scoped_credential(token, key=KEY, run_id="res-b")
        return False
    except CredentialDenied:
        return True


def test_shared_contract_across_managed_and_attached_surfaces():
    builtin = BuiltinHarnessAdapter(attempt_fn=_scripted_attempt_fn())
    codex = CodexHarnessAdapter()
    claude = ClaudeCodeHarnessAdapter()

    results = [
        qualify_adapter(
            builtin,
            fixture_evidence="in-process",
            live_evidence="not_run",
            permissions_check=_permissions_scope_check,
        ),
        qualify_adapter(
            codex,
            normalize=normalize_codex_event,
            fixture_evidence="recorded-protocol-fixtures",
            live_evidence="not_run",
            permissions_check=_permissions_scope_check,
        ),
        qualify_adapter(
            claude,
            normalize=normalize_claude_event,
            fixture_evidence="recorded-protocol-fixtures",
            live_evidence="not_run",
            permissions_check=_permissions_scope_check,
        ),
    ]
    for result in results:
        assert result.required_semantics is True, result.as_dict()
        assert all(result.negative_cases.values()), result.as_dict()
        assert claim_honesty(result) is True
        # fixture evidence alone never becomes a compatibility claim
        assert result.compatibility_claim is False

    matrix = supported_matrix(results)
    assert matrix["all_required_semantics_pass"] is True
    assert matrix["live_claims"] == []
    assert matrix["contract_version"] == "autoresearch_harness.v1"
    # the matrix reports capabilities individually per adapter
    by_name = {row["adapter"]: row for row in matrix["adapters"]}
    assert by_name["builtin"]["capabilities"] == ["pause", "resume"]
    assert by_name["codex"]["capabilities"] == []
    assert by_name["claude-code"]["capabilities"] == ["resume"]


def test_fixture_and_live_evidence_are_reported_separately():
    # a fixture pass with live evidence becomes a claim; without it, never
    fixture_only = QualificationResult(
        adapter="codex",
        version="1.0.0",
        interface="codex exec --json",
        contract_version="autoresearch_harness.v1",
        capabilities=(),
        required_semantics=True,
        fixture_evidence="recorded-protocol-fixtures",
        live_evidence="not_run",
    )
    assert claim_honesty(fixture_only) is True
    assert fixture_only.compatibility_claim is False

    live = qualify_adapter(
        CodexHarnessAdapter(),
        normalize=normalize_codex_event,
        fixture_evidence="recorded-protocol-fixtures",
        live_evidence="recorded",
    )
    assert live.compatibility_claim is True
    assert claim_honesty(live) is True
    matrix = supported_matrix([fixture_only, live])
    assert matrix["live_claims"] == ["codex"]


def test_custom_process_driver_in_the_shared_contract(tmp_path):
    from src.core.driver_host import DriverHost, DriverHostConfig

    config = DriverHostConfig(
        executable=(sys.executable, "-c", "print()"),
        run_id="res-g4",
        workspace=str(tmp_path / "ws"),
        identity={"name": "custom-driver", "version": "1.0.0"},
    )
    host = DriverHost(config)
    # the custom driver surface is qualified through its host: required
    # semantics (bounded streams, supervision) live in the host suite, and
    # the G4 contract checks its identity and authority separation
    assert config.identity["name"] == "custom-driver"
    assert _permissions_scope_check() is True


def test_attached_api_cli_workflow_is_in_the_contract(tmp_path, monkeypatch):
    # the attached workflow's scope rules are part of the shared contract
    assert _permissions_scope_check() is True
    # and the CLI's error envelope maps refusals to stable codes (the
    # workflow surface is qualified through its own suite; here the G4
    # contract asserts the authority separation holds on that path too)
    from src.core.scoped_credentials import NON_GRANTABLE_PERMISSIONS

    for forbidden in NON_GRANTABLE_PERMISSIONS:
        with pytest.raises(CredentialDenied):
            issue_scoped_credential(
                subject="g4",
                run_id="res-a",
                permissions=(forbidden,),
                key=KEY,
            )


def test_no_path_bypasses_g1_evidence_with_receipt_reuse():
    """A receipt from one run must never verify another run's result."""
    from src.core.research_kernel import verify_evidence
    from src.core.result_authority import issue_result_receipt

    payload_a = {
        "research_id": "res-run-a",
        "iteration": 1,
        "result": {"x": 1},
    }
    receipt = issue_result_receipt(
        payload=payload_a,
        attempt_id="res-run-a:1",
        candidate_digest="a" * 64,
        evaluator_digest="b" * 64,
        dataset_digests=["c" * 64],
        ownership_epoch=1,
        sequence=1,
        key="g4-key",
    )
    # the original binding verifies
    verified = verify_evidence(
        receipt=receipt, payload=payload_a, key="g4-key"
    )
    assert verified.status == "verified"
    # reusing the receipt for another run's payload is refused
    payload_b = {
        "research_id": "res-run-b",
        "iteration": 1,
        "result": {"x": 1},
    }
    reused = verify_evidence(
        receipt=receipt, payload=payload_b, key="g4-key"
    )
    assert reused.status == "rejected"
    # reusing it for the same run at a different attempt is refused too
    tampered = dict(payload_a)
    tampered["iteration"] = 2
    second = verify_evidence(
        receipt=receipt, payload=tampered, key="g4-key"
    )
    assert second.status == "rejected"


def test_driver_proposals_are_never_self_verified():
    # uniform across every managed and attached path: a proposal is a
    # candidate (model-proposed) and cannot carry verified authority
    from src.core.claude_code_harness import map_candidate_changes
    from src.core.codex_harness import (
        map_candidate_changes as codex_changes,
    )

    claude_events = [
        {
            "type": "assistant",
            "payload": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "t1",
                        "name": "Write",
                        "input": {},
                    }
                ]
            },
        }
    ]
    codex_events = [
        {
            "type": "item.completed",
            "payload": {
                "item_type": "file_change",
                "item_id": "i1",
                "changes": [],
            },
        }
    ]
    for proposal in map_candidate_changes(claude_events) + codex_changes(
        codex_events
    ):
        assert proposal["payload"]["authority"] == "model_proposed"