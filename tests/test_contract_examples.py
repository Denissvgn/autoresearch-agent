"""Tests for the serialized contract examples under examples/contracts/v1/.

Every example bundle must validate against the contract models and
round-trip through JSON unchanged.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.core import execution_contracts as ec

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples" / "contracts" / "v1"

DOMAIN_DIRECTIONS = {
    "prompt-evaluation": "maximize",
    "code-test": "maximize",
    "latency-minimization": "minimize",
}

EXPECTED_INTEGRATION_COVERAGE = {
    (domain, integration)
    for domain in DOMAIN_DIRECTIONS
    for integration in ("managed", "attached")
}


def _bundles() -> list[tuple[str, dict[str, Any]]]:
    return [
        (path.stem, json.loads(path.read_text(encoding="utf-8")))
        for path in sorted(EXAMPLES_DIR.glob("*.json"))
    ]


def _bundle(name: str) -> dict[str, Any]:
    return json.loads((EXAMPLES_DIR / f"{name}.json").read_text(encoding="utf-8"))


def _round_trip(model: type, payload: dict[str, Any]) -> Any:
    instance = model.model_validate(payload)
    assert model.model_validate_json(instance.model_dump_json()) == instance
    return instance


def test_every_example_file_parses_with_identity_fields() -> None:
    bundles = _bundles()
    assert len(bundles) >= 11
    for name, bundle in bundles:
        assert bundle["example_id"] == name
        assert bundle["kind"] in {"integration", "review", "compatibility"}
        assert bundle["description"]


def test_integration_bundles_cover_both_directions_and_three_domains() -> None:
    coverage = {
        (bundle["domain"], bundle["integration"])
        for _, bundle in _bundles()
        if bundle["kind"] == "integration"
    }
    assert coverage == EXPECTED_INTEGRATION_COVERAGE


@pytest.mark.parametrize(
    "name",
    [
        f"{integration}-{domain}"
        for domain in sorted(DOMAIN_DIRECTIONS)
        for integration in ("managed", "attached")
    ],
)
def test_integration_bundle_contracts_validate_and_agree(name: str) -> None:
    bundle = _bundle(name)
    spec = _round_trip(ec.RunSpec, bundle["run_spec"])
    request = _round_trip(ec.ExecutionRequest, bundle["execution_request"])
    result = _round_trip(ec.VerifiedResult, bundle["verified_result"])

    assert spec.integration == bundle["integration"]
    assert request.integration == bundle["integration"]
    assert spec.objective.direction == DOMAIN_DIRECTIONS[bundle["domain"]]
    assert request.run_spec_digest == spec.spec_digest()
    assert request.run_id == spec.run_id
    assert result.run_id == request.run_id
    assert result.attempt_id == request.attempt_id
    assert result.candidate.digest == request.candidate.digest
    assert result.observation.candidate_digest == request.candidate.digest
    assert set(result.metrics) == {spec.objective.metric_field}

    ec.ensure_minimum_capabilities(spec.capabilities)
    ec.ensure_isolation_boundary(spec.isolation)
    ec.reject_raw_secret_parameters(spec.parameters, "example run_spec parameters")


def test_integration_bundles_reference_no_raw_credentials() -> None:
    for _, bundle in _bundles():
        for section in ("run_spec", "execution_request"):
            payload = bundle.get(section)
            if not payload:
                continue
            for ref in payload.get("secrets", []):
                assert set(ref) == {"name", "provider", "role", "scope"}
            ec.reject_raw_secret_parameters(
                payload.get("parameters", {}), f"{bundle['example_id']}.{section}"
            )


# ---------------------------------------------------------------------------
# Review examples
# ---------------------------------------------------------------------------


def test_review_failure_example_claims_no_metrics() -> None:
    bundle = _bundle("review-failure")
    result = _round_trip(ec.VerifiedResult, bundle["verified_result"])
    assert result.status == "failed"
    assert result.metrics == {}
    assert result.failure is not None
    assert result.failure.stage == "evaluation"
    request = _round_trip(ec.ExecutionRequest, bundle["execution_request"])
    assert result.attempt_id == request.attempt_id


def test_review_continuation_preserves_lineage_and_nondefaults() -> None:
    bundle = _bundle("review-continuation")
    spec = _round_trip(ec.RunSpec, bundle["run_spec"])
    assert spec.lineage.parent_run_id is not None
    assert spec.lineage.checkpoint_refs
    assert spec.lineage.focus_hint
    # Nondefault settings survive into the continuation.
    assert spec.parameters["max_complexity"] == 6
    assert spec.budget.max_iterations == 17
    assert spec.budget.max_budget_usd == 2.25
    assert spec.budget.timeout_s == 1500


def test_review_minimization_selects_the_lower_measurement() -> None:
    bundle = _bundle("review-minimization")
    policy = _round_trip(ec.ObjectivePolicy, bundle["objective_policy"])
    results = [
        _round_trip(ec.VerifiedResult, item) for item in bundle["verified_results"]
    ]
    assert policy.direction == "minimize"
    best = min(results, key=lambda r: r.metrics[policy.metric_field])
    assert best.result_id == bundle["winner_result_id"]


def test_review_unsupported_capability_is_rejected_before_work() -> None:
    bundle = _bundle("review-unsupported-capability")
    descriptor = _round_trip(ec.CapabilityDescriptor, bundle["capability_descriptor"])
    expected = bundle["expected_rejection"]
    assert expected["error"] == "UnsupportedCapabilityError"
    with pytest.raises(ec.UnsupportedCapabilityError) as excinfo:
        ec.ensure_minimum_capabilities(descriptor)
    for missing in expected["missing_capabilities"]:
        assert missing in str(excinfo.value)
    assert set(expected["missing_capabilities"]) == (
        ec.MINIMUM_SUPPORTED_CAPABILITIES - set(descriptor.capabilities)
    )


def test_legacy_compatibility_example_matches_the_code_mapping() -> None:
    bundle = _bundle("legacy-compatibility")
    serialized = bundle["mapping"]
    assert serialized == [
        entry.model_dump(mode="json") for entry in ec.LEGACY_COMPATIBILITY
    ]
    dispositions = {entry["disposition"] for entry in serialized}
    assert dispositions == {"preserved", "rejected"}