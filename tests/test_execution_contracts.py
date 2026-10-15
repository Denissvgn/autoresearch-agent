"""Tests for the versioned research and execution contracts.

Fixture payloads use synthetic identifiers and digest strings only.
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Optional

import pytest
from pydantic import ValidationError

from src.core import execution_contracts as ec

REPO_ROOT = Path(__file__).resolve().parents[1]

DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
DIGEST_C = "sha256:" + "c" * 64
DIGEST_D = "sha256:" + "d" * 64


def _candidate(candidate_id: str = "cand-1", digest: str = DIGEST_A) -> ec.CandidateIdentity:
    return ec.CandidateIdentity(candidate_id=candidate_id, digest=digest)


def _observation(
    candidate_digest: str = DIGEST_A,
    *,
    fidelity: str = "measured",
    observation_id: str = "obs-1",
) -> ec.ObservationIdentity:
    return ec.ObservationIdentity(
        observation_id=observation_id,
        candidate_digest=candidate_digest,
        subject_id="subject-1",
        variant="variant-1",
        seed=7,
        scorer=ec.ScorerRef(scorer_id="scorer-1", version="1.0", digest=DIGEST_B),
        dataset_digests=[DIGEST_C],
        fidelity=fidelity,  # type: ignore[arg-type]
    )


def _receipt() -> ec.ResultReceipt:
    return ec.ResultReceipt(
        receipt_id="rcpt-1",
        nonce="nonce-1",
        ownership_epoch=1,
        sequence=0,
        envelope_digest=DIGEST_D,
    )


def _capabilities(
    *, integration: str = "managed", extra: Optional[list[str]] = None
) -> ec.CapabilityDescriptor:
    return ec.CapabilityDescriptor(
        integration=integration,  # type: ignore[arg-type]
        adapter_id="adapter-1",
        protocol_version="1",
        capabilities=sorted(ec.MINIMUM_SUPPORTED_CAPABILITIES | set(extra or [])),
    )


def _objective(direction: str = "maximize") -> ec.ObjectivePolicy:
    return ec.ObjectivePolicy(
        metric_field="primary_metric",
        direction=direction,  # type: ignore[arg-type]
        tie_tolerance=1e-9,
    )


def _run_spec(**overrides: Any) -> ec.RunSpec:
    payload: dict[str, Any] = {
        "run_id": "run-1",
        "integration": "managed",
        "skill": ec.SkillPackageRef(
            skill_id="prompt-engineering", version="0.3.0", digest=DIGEST_A
        ),
        "parameters": {"target_file": "refactor_target.py"},
        "harness": ec.HarnessConfig(
            adapter_id="adapter-1",
            protocol_version="1",
            effective_config={"model": "example-model"},
            model_roles={"primary": "example-model"},
        ),
        "inputs": ec.RunInputs(
            candidate_input_digests=[DIGEST_B],
            evaluator_digest=DIGEST_C,
            dataset_digests=[DIGEST_D],
            environment=ec.EnvironmentIdentity(dependency_lock_digest=DIGEST_A),
        ),
        "capabilities": _capabilities(),
        "isolation": ec.LINUX_ISOLATION_BOUNDARY,
        "policy_version": "execution-policy.v1",
        "budget": ec.BudgetDimensions(
            max_iterations=8, max_budget_usd=1.5, timeout_s=1800, max_concurrency=1
        ),
        "objective": _objective(),
    }
    payload.update(overrides)
    return ec.RunSpec(**payload)


def _execution_request(**overrides: Any) -> ec.ExecutionRequest:
    payload: dict[str, Any] = {
        "request_id": "req-1",
        "run_id": "run-1",
        "attempt_id": "attempt-1",
        "integration": "managed",
        "run_spec_digest": DIGEST_A,
        "candidate": _candidate(),
        "evaluator_digest": DIGEST_C,
        "dataset_digests": [DIGEST_D],
        "environment_digest": DIGEST_B,
        "workspace": ec.WorkspaceBounds(writable_roots=["candidate"], read_only_roots=["inputs"]),
        "network": ec.NetworkPolicy(),
        "resources": ec.ResourceLimits(wall_clock_s=600, memory_mb=512, max_processes=8),
    }
    payload.update(overrides)
    return ec.ExecutionRequest(**payload)


def _verified_result(**overrides: Any) -> ec.VerifiedResult:
    payload: dict[str, Any] = {
        "result_id": "res-1",
        "run_id": "run-1",
        "attempt_id": "attempt-1",
        "candidate": _candidate(),
        "observation": _observation(),
        "status": "succeeded",
        "metrics": {"primary_metric": 0.75},
        "evaluator_digest": DIGEST_C,
        "receipt": _receipt(),
        "produced_at": "2026-10-15T12:00:00Z",
        "provenance": "evaluator_owned",
        "verification": "verified",
    }
    payload.update(overrides)
    return ec.VerifiedResult(**payload)


# ---------------------------------------------------------------------------
# Versioning and round-trip
# ---------------------------------------------------------------------------


def test_contract_versions_are_unique() -> None:
    versions = list(ec.CONTRACT_VERSIONS.values())
    assert len(versions) == len(set(versions))
    assert ec.RunSpec.model_fields["schema_version"].default == ec.RUN_SPEC_SCHEMA_VERSION


def test_run_spec_rejects_unknown_schema_version() -> None:
    with pytest.raises(ValidationError):
        _run_spec(schema_version="research_run_spec.v99")


def test_every_top_level_contract_rejects_unknown_version() -> None:
    cases = [
        (ec.CandidateIdentity, {"candidate_id": "c", "digest": DIGEST_A}),
        (ec.ObjectivePolicy, {"metric_field": "m", "direction": "minimize"}),
    ]
    for model, base in cases:
        with pytest.raises(ValidationError):
            model(**base, schema_version="research_unknown.v2")


def test_run_spec_json_round_trip() -> None:
    spec = _run_spec()
    restored = ec.RunSpec.model_validate_json(spec.model_dump_json())
    assert restored == spec
    assert restored.spec_digest() == spec.spec_digest()


def test_execution_request_json_round_trip() -> None:
    request = _execution_request()
    restored = ec.ExecutionRequest.model_validate_json(request.model_dump_json())
    assert restored == request


def test_verified_result_json_round_trip() -> None:
    result = _verified_result()
    restored = ec.VerifiedResult.model_validate_json(result.model_dump_json())
    assert restored == result


# ---------------------------------------------------------------------------
# Secrets and mutable candidate data
# ---------------------------------------------------------------------------


def test_secret_reference_wire_form_round_trip() -> None:
    ref = ec.SecretReference(name="scorer.api_key", role="evaluator")
    assert ref.wire_form() == "secret://scorer.api_key"
    assert ec.SecretReference.parse(ref.wire_form(), role="evaluator") == ref
    assert ec.is_secret_reference(ref.wire_form())
    assert not ec.is_secret_reference("sk-raw-value")


def test_secret_reference_rejects_invalid_names() -> None:
    with pytest.raises(ValidationError):
        ec.SecretReference(name="No Spaces")


def test_run_spec_rejects_raw_credential_parameters() -> None:
    # Model-level checks surface through pydantic's ValidationError wrapper.
    with pytest.raises(ValidationError):
        _run_spec(parameters={"api_key": "sk-raw-value"})


def test_run_spec_accepts_secret_reference_parameters() -> None:
    spec = _run_spec(parameters={"api_key": "secret://scorer.api_key"})
    assert spec.parameters["api_key"] == "secret://scorer.api_key"


def test_plain_parameter_names_are_not_flagged_as_secrets() -> None:
    spec = _run_spec(parameters={"max_tokens": 512})
    assert spec.parameters["max_tokens"] == 512


def test_attached_run_rejects_operator_and_approver_credentials() -> None:
    for role in ("operator", "approver"):
        with pytest.raises(ValidationError):
            _execution_request(
                integration="attached",
                secrets=[ec.SecretReference(name="svc.token", role=role)],  # type: ignore[arg-type]
            )


def test_attached_run_accepts_scoped_harness_credentials() -> None:
    request = _execution_request(
        integration="attached",
        secrets=[ec.SecretReference(name="driver.auth", role="harness", scope="attempt")],
    )
    assert request.secrets[0].scope == "attempt"


def test_duplicate_secret_references_rejected() -> None:
    with pytest.raises(ValidationError):
        _execution_request(
            secrets=[
                ec.SecretReference(name="driver.auth"),
                ec.SecretReference(name="driver.auth"),
            ]
        )


def test_run_spec_rejects_inline_mutable_candidate_data() -> None:
    with pytest.raises(ValidationError):
        _run_spec(candidate_data={"files": {"a.py": "print(1)"}})


def test_candidate_data_identity_is_order_independent() -> None:
    one = ec.CandidateData(payload={"a": 1, "b": 2}).identity("cand-1")
    two = ec.CandidateData(payload={"b": 2, "a": 1}).identity("cand-1")
    assert one.digest == two.digest
    three = ec.CandidateData(payload={"a": 1, "b": 3}).identity("cand-1")
    assert three.digest != one.digest


# ---------------------------------------------------------------------------
# Identity and objective policy
# ---------------------------------------------------------------------------


def test_digest_shape_is_enforced() -> None:
    with pytest.raises(ValidationError):
        _candidate(digest="md5:notasha")


def test_observation_context_digest_separates_fidelity() -> None:
    measured = _observation(fidelity="measured")
    simulated = _observation(fidelity="simulated")
    assert measured.context_digest() != simulated.context_digest()
    assert _observation(observation_id="obs-2").context_digest() == measured.context_digest()


def test_objective_policy_maps_skill_metric_vocabulary() -> None:
    lower = ec.objective_policy_from_skill_metric(
        metric_field="p95_latency_ms", direction="lower_is_better"
    )
    higher = ec.objective_policy_from_skill_metric(
        metric_field="score", direction="higher_is_better"
    )
    assert lower.direction == "minimize"
    assert higher.direction == "maximize"


def test_objective_policy_rejects_nonfinite_threshold() -> None:
    with pytest.raises(ValidationError):
        ec.MetricConstraint(
            metric_field="score", comparator=">=", threshold=float("nan")
        )


# ---------------------------------------------------------------------------
# Capabilities and isolation boundary
# ---------------------------------------------------------------------------


def test_capability_descriptor_rejects_unknown_identifiers() -> None:
    with pytest.raises(ValidationError):
        ec.CapabilityDescriptor(
            integration="managed",
            adapter_id="a",
            protocol_version="1",
            capabilities=["start", "read_mind"],
        )


def test_capability_descriptor_rejects_claimed_and_unsupported_overlap() -> None:
    with pytest.raises(ValidationError):
        ec.CapabilityDescriptor(
            integration="managed",
            adapter_id="a",
            protocol_version="1",
            capabilities=["start"],
            unsupported={"start": "not actually"},
        )


def test_minimum_capabilities_pass_and_fail() -> None:
    ec.ensure_minimum_capabilities(_capabilities())
    weak = ec.CapabilityDescriptor(
        integration="managed",
        adapter_id="a",
        protocol_version="1",
        capabilities=["start"],
        unsupported={"cancel": "no cancellation channel"},
    )
    with pytest.raises(ec.UnsupportedCapabilityError) as excinfo:
        ec.ensure_minimum_capabilities(weak)
    assert "cancel" in str(excinfo.value)


def test_capabilities_outside_operator_allowance_rejected() -> None:
    descriptor = _capabilities(extra=["pause"])
    ec.ensure_capabilities_allowed(
        descriptor, allowed=frozenset(ec.MINIMUM_SUPPORTED_CAPABILITIES | {"pause"})
    )
    with pytest.raises(ec.UnsupportedCapabilityError):
        ec.ensure_capabilities_allowed(
            descriptor, allowed=frozenset(ec.MINIMUM_SUPPORTED_CAPABILITIES)
        )


def test_qualified_isolation_boundary_accepted() -> None:
    ec.ensure_isolation_boundary(ec.LINUX_ISOLATION_BOUNDARY)


def test_application_only_isolation_rejected() -> None:
    weak = ec.IsolationBoundary(
        platform="linux",
        enforcement="application",
        process_isolation=True,
        filesystem_confinement=True,
        network_policy=True,
        resource_limits=True,
    )
    with pytest.raises(ec.UnsupportedCapabilityError):
        ec.ensure_isolation_boundary(weak)


def test_missing_resource_limits_rejected() -> None:
    weak = ec.IsolationBoundary(
        platform="linux",
        enforcement="os",
        process_isolation=True,
        filesystem_confinement=True,
        network_policy=True,
        resource_limits=False,
    )
    with pytest.raises(ec.UnsupportedCapabilityError):
        ec.ensure_isolation_boundary(weak)


# ---------------------------------------------------------------------------
# Verified results
# ---------------------------------------------------------------------------


def test_succeeded_result_requires_metrics() -> None:
    with pytest.raises(ValidationError):
        _verified_result(metrics={})


def test_failed_result_must_not_claim_metrics() -> None:
    failure = ec.FailureRecord(
        code="eval_error", message="scorer crashed", stage="evaluation", retryable=True
    )
    with pytest.raises(ValidationError):
        _verified_result(status="failed", metrics={"primary_metric": 1.0}, failure=failure)
    result = _verified_result(status="failed", metrics={}, failure=failure)
    assert result.status == "failed"
    assert result.failure is not None and result.failure.retryable


def test_non_succeeded_result_requires_failure_record() -> None:
    with pytest.raises(ValidationError):
        _verified_result(status="timeout", metrics={})


def test_nonfinite_metrics_rejected() -> None:
    with pytest.raises(ValidationError):
        _verified_result(metrics={"primary_metric": float("inf")})


def test_imported_results_stay_unverified() -> None:
    with pytest.raises(ValidationError):
        _verified_result(provenance="imported", verification="verified")
    result = _verified_result(provenance="imported", verification="unverified_imported")
    assert result.verification == "unverified_imported"


def test_evaluator_owned_results_are_verified_by_construction() -> None:
    with pytest.raises(ValidationError):
        _verified_result(verification="unverified_imported")


# ---------------------------------------------------------------------------
# Execution request policy
# ---------------------------------------------------------------------------


def test_network_deny_rejects_allowed_hosts() -> None:
    with pytest.raises(ValidationError):
        ec.NetworkPolicy(mode="deny", allowed_hosts=["example.test"])


def test_execution_request_rejects_bad_digest_shapes() -> None:
    with pytest.raises(ValidationError):
        _execution_request(environment_digest="sha1:abc")


def test_request_run_spec_binding_accepts_exact_match() -> None:
    spec = _run_spec()
    request = _execution_request(
        run_id=spec.run_id,
        run_spec_digest=spec.spec_digest(),
        evaluator_digest=spec.inputs.evaluator_digest,
        dataset_digests=list(spec.inputs.dataset_digests),
        environment_digest=spec.inputs.environment.digest(),
    )
    ec.ensure_request_matches_run_spec(request, spec)


@pytest.mark.parametrize(
    "override",
    [
        {"run_spec_digest": DIGEST_B},
        {"run_id": "run-other"},
        {"evaluator_digest": DIGEST_D},
        {"dataset_digests": [DIGEST_C]},
        {"environment_digest": DIGEST_C},
        {"integration": "attached"},
    ],
)
def test_request_run_spec_binding_rejects_mismatches(override: dict) -> None:
    spec = _run_spec()
    bound: dict[str, Any] = {
        "run_id": spec.run_id,
        "run_spec_digest": spec.spec_digest(),
        "evaluator_digest": spec.inputs.evaluator_digest,
        "dataset_digests": list(spec.inputs.dataset_digests),
        "environment_digest": spec.inputs.environment.digest(),
    }
    bound.update(override)
    request = _execution_request(**bound)
    with pytest.raises(ec.ContractError):
        ec.ensure_request_matches_run_spec(request, spec)


# ---------------------------------------------------------------------------
# Input layers and precedence
# ---------------------------------------------------------------------------


def _resolve(**kwargs: Any) -> ec.ResolvedRunInputs:
    kwargs.setdefault("operator", ec.OperatorConstraints())
    return ec.resolve_run_inputs(**kwargs)


def test_precedence_chain_for_budget_fields() -> None:
    resolved = _resolve(
        explicit={"max_iterations": 10},
        skill_defaults=ec.SkillDefaults(budget={"max_iterations": 5, "timeout_s": 900}),
        harness_preferences=ec.HarnessPreferences(timeout_s=600, max_concurrency=3),
    )
    by_field = {r.field: r for r in resolved.records}
    assert by_field["budget.max_iterations"].source == "explicit"
    assert resolved.budget.max_iterations == 10
    assert by_field["budget.timeout_s"].source == "skill_default"
    assert resolved.budget.timeout_s == 900
    assert by_field["budget.max_concurrency"].source == "harness_preference"
    assert resolved.budget.max_concurrency == 3
    assert by_field["budget.max_budget_usd"].source == "system_default"
    assert resolved.budget.max_budget_usd == 0.0


def test_operator_constraints_bound_explicit_inputs() -> None:
    resolved = _resolve(
        operator=ec.OperatorConstraints(max_iterations=5, max_budget_usd=2.0),
        explicit={"max_iterations": 12, "max_budget_usd": 99.0},
    )
    by_field = {r.field: r for r in resolved.records}
    assert resolved.budget.max_iterations == 5
    assert by_field["budget.max_iterations"].requested == 12
    assert by_field["budget.max_iterations"].bounded is True
    assert resolved.budget.max_budget_usd == 2.0
    assert by_field["budget.max_budget_usd"].bounded is True


def test_harness_preferences_cannot_widen_authority() -> None:
    resolved = _resolve(
        operator=ec.OperatorConstraints(max_concurrency=2),
        harness_preferences=ec.HarnessPreferences(max_concurrency=8),
    )
    assert resolved.budget.max_concurrency == 2
    record = {r.field: r for r in resolved.records}["budget.max_concurrency"]
    assert record.source == "harness_preference"
    assert record.requested == 8
    assert record.bounded is True


def test_harness_preferences_never_set_domain_parameters() -> None:
    resolved = _resolve(
        skill_defaults=ec.SkillDefaults(parameters={"target_file": "skill.py"}),
    )
    assert resolved.parameters == {"target_file": "skill.py"}
    assert not any(r.field.startswith("parameters.") for r in resolved.records
                   if r.source == "harness_preference")


def test_explicit_parameters_override_skill_defaults() -> None:
    resolved = _resolve(
        explicit={"target_file": "explicit.py", "seed": 3},
        skill_defaults=ec.SkillDefaults(parameters={"target_file": "skill.py"}),
    )
    assert resolved.parameters == {"target_file": "explicit.py", "seed": 3}
    sources = {r.field: r.source for r in resolved.records}
    assert sources["parameters.target_file"] == "explicit"
    assert sources["parameters.seed"] == "explicit"


def test_model_roles_prefer_skill_defaults_over_preferences() -> None:
    resolved = _resolve(
        skill_defaults=ec.SkillDefaults(model_roles={"primary": "skill-model"}),
        harness_preferences=ec.HarnessPreferences(
            model_roles={"primary": "pref-model", "insight": "pref-insight"}
        ),
    )
    assert resolved.model_roles == {"primary": "skill-model", "insight": "pref-insight"}


def test_budget_fields_never_leak_into_parameters() -> None:
    resolved = _resolve(explicit={"max_iterations": 4, "target_file": "x.py"})
    assert "max_iterations" not in resolved.parameters
    assert resolved.parameters == {"target_file": "x.py"}


def test_resolve_rejects_negative_spend_request() -> None:
    with pytest.raises(ec.ContractError):
        _resolve(explicit={"max_budget_usd": -1.0})


def test_resolve_rejects_raw_secret_values() -> None:
    with pytest.raises(ec.ContractError):
        _resolve(explicit={"api_key": "sk-raw-value"})


# ---------------------------------------------------------------------------
# Legacy readers and the compatibility mapping
# ---------------------------------------------------------------------------


def _legacy_manifest(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "research_session_manifest.v2",
        "research_id": "res-1",
        "instrument": "subject-legacy",
        "timeframe": "variant-legacy",
        "model_type": "direction",
        "objective": "improve calibrated direction_proba",
        "budget": {"max_budget_usd": 2.5, "quick_mode": False},
        "max_iterations": 9,
        "timeout_s": 1200,
    }
    payload.update(overrides)
    return payload


def test_legacy_manifest_maps_preserved_fields() -> None:
    migrated = ec.read_legacy_session_manifest(_legacy_manifest())
    assert migrated.skill_id == "ml-direction"  # legacy alias resolution
    assert migrated.subject_id == "subject-legacy"
    assert migrated.variant == "variant-legacy"
    assert migrated.budget.max_budget_usd == 2.5
    assert migrated.budget.max_iterations == 9
    assert migrated.budget.timeout_s == 1200
    assert migrated.legacy_objective_text == "improve calibrated direction_proba"
    assert "model_type" in migrated.preserved_fields
    assert set(migrated.absent_rejected_fields) == {"session_nonce", "mlflow_experiment"}


def test_legacy_reader_accepts_v1_and_v3_and_rejects_unknown() -> None:
    for version in ("research_session_manifest.v1", "research_session_manifest.v3"):
        migrated = ec.read_legacy_session_manifest(_legacy_manifest(schema_version=version))
        assert migrated.source_schema == version
    with pytest.raises(ec.ContractMigrationError):
        ec.read_legacy_session_manifest(_legacy_manifest(schema_version="research_session_manifest.v9"))


def test_legacy_reader_rejects_requested_incomplete_features() -> None:
    with pytest.raises(ec.ContractMigrationError) as excinfo:
        ec.read_legacy_session_manifest(
            _legacy_manifest(session_nonce="nonce-1", mlflow_experiment="exp-1")
        )
    fields = {issue["legacy_field"] for issue in excinfo.value.issues}
    assert fields == {"session_nonce", "mlflow_experiment"}


def test_legacy_reader_tolerates_absent_rejected_fields() -> None:
    migrated = ec.read_legacy_session_manifest(_legacy_manifest(session_nonce=None))
    assert "session_nonce" in migrated.absent_rejected_fields


def test_legacy_reader_never_invents_a_budget() -> None:
    payload = _legacy_manifest()
    del payload["budget"]
    with pytest.raises(ec.ContractMigrationError):
        ec.read_legacy_session_manifest(payload)


def test_legacy_reader_rejects_raw_secret_parameters() -> None:
    with pytest.raises(ec.ContractError):
        ec.read_legacy_session_manifest(_legacy_manifest(skill_params={"api_key": "sk-raw"}))


def test_legacy_start_request_converts_minutes_and_defaults() -> None:
    migrated = ec.read_legacy_start_request(
        {
            "model_type": "direction",
            "instrument": "subject-legacy",
            "timeframe": "variant-legacy",
            "skill_params": {"target_file": "x.py"},
            "timeout_minutes": 30,
            "focus_hint": "keep the last shape",
        }
    )
    assert migrated.skill_id == "ml-direction"
    assert migrated.budget.timeout_s == 1800
    assert migrated.budget.max_iterations == ec.SYSTEM_DEFAULTS["max_iterations"]
    assert migrated.parameters == {"target_file": "x.py"}
    assert migrated.focus_hint == "keep the last shape"


def test_legacy_session_manifest_preserves_focus_hint() -> None:
    migrated = ec.read_legacy_session_manifest(
        _legacy_manifest(focus_hint="keep the simplification")
    )
    assert migrated.focus_hint == "keep the simplification"
    assert "focus_hint" in migrated.preserved_fields


def test_compatibility_mapping_distinguishes_preserved_and_rejected() -> None:
    dispositions = {entry.disposition for entry in ec.LEGACY_COMPATIBILITY}
    assert dispositions == {"preserved", "rejected"}
    for entry in ec.LEGACY_COMPATIBILITY:
        assert entry.reason
        if entry.disposition == "rejected":
            assert entry.rejected_when == "non-empty"
        else:
            assert entry.contract_field or "retained" in entry.reason
    # The mapping names concrete contract targets for migrated fields.
    assert any(
        entry.contract_field for entry in ec.LEGACY_COMPATIBILITY
        if entry.disposition == "preserved"
    )


# ---------------------------------------------------------------------------
# Kernel contracts stay free of harness SDK types
# ---------------------------------------------------------------------------

_FORBIDDEN_IMPORT_ROOTS = {
    "anthropic",
    "openai",
    "claude_agent_sdk",
    "claude_code",
    "codex",
    "agent_sdk",
    "langchain",
}


def test_kernel_contract_module_imports_no_harness_sdks() -> None:
    source = (REPO_ROOT / "src" / "core" / "execution_contracts.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)
    import_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            import_roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            import_roots.add(node.module.split(".")[0])
    assert import_roots & _FORBIDDEN_IMPORT_ROOTS == set()