"""Normalized result contract: declared parser semantics, explicit invalid
evidence, and identical rules for stdout and artifact collection.

A result payload either validates against the declared result semantics
(parser format, marker prefix, required fields, field types/units, finite
numbers, schema version, failure statuses) or becomes explicit invalid
evidence — never implicit success and never a promotable placeholder metric.
"""
from __future__ import annotations

import json
import math
import types
from pathlib import Path

import pytest
import yaml

from src.core.output_parser import (
    RESULT_SCHEMA_VERSION,
    ResultSpec,
    extract_raw_result,
    normalize_result,
    parse_and_verify_text,
    parse_result_text,
)
from src.core.skill_loader import load_skill_manifest
from src.core.skill_manifest import FieldTypes, ResearchSkillManifest
from src.core.skill_runtime import ManifestSkillRuntime

REPO_ROOT = Path(__file__).resolve().parents[1]


def _db_spec() -> ResultSpec:
    doc = yaml.safe_load(
        (REPO_ROOT / "skills" / "db-config-tuning" / "SKILL.yaml").read_text(
            encoding="utf-8"
        )
    )
    return ResultSpec.from_output_parser(
        ResearchSkillManifest.model_validate(doc).output_parser
    )


GOOD = (
    "ITERATION_RESULT: "
    + json.dumps({
        "status": "completed", "primary_metric": 250.0, "metric_name": "tps",
        "p99_within_slo": True, "bench_duration_s": 90, "p99_latency_ms": 22.5,
        "target_latency_ms": 25, "server_nonce": "aa",
    })
)


def test_declared_result_fields_types_and_units_are_enforced() -> None:
    result = parse_result_text(GOOD, _db_spec())
    assert result is not None and result.outcome == "completed"
    assert result.primary_metric == 250.0
    assert result.units == {
        "bench_duration_s": "seconds", "p99_latency_ms": "milliseconds",
        "target_latency_ms": "milliseconds",
    }
    record = result.to_dict()
    assert record["result_schema_version"] == RESULT_SCHEMA_VERSION
    assert record["field_units"]["p99_latency_ms"] == "milliseconds"
    assert record["raw_evidence"]["bench_duration_s"] == 90


def test_declared_failure_status_is_nonwinning_and_not_promotable() -> None:
    """A declared failure keeps no promotable metric (the accepted-payload
    regression: a failure payload retained its metric and was accepted)."""
    payload = {"status": "bench_failed", "primary_metric": 123, "metric_name": "tps"}
    result = normalize_result(payload, _db_spec())
    assert result.outcome == "failed"
    assert result.primary_metric is None
    assert result.raw_evidence["primary_metric"] == 123
    record = result.to_dict()
    assert record["primary_metric"] is None
    assert record["result_outcome"] == "failed"


def test_missing_required_fields_are_rejected_consistently() -> None:
    payload = {"status": "completed", "primary_metric": 123, "metric_name": "tps"}
    result = normalize_result(payload, _db_spec())
    assert result.outcome == "invalid"
    assert result.primary_metric is None
    assert any("p99_within_slo" in v for v in result.violations)


def test_nonfinite_numbers_are_rejected() -> None:
    for bad in (math.nan, math.inf):
        payload = {
            "status": "completed", "primary_metric": bad, "metric_name": "tps",
            "p99_within_slo": True,
        }
        result = normalize_result(payload, _db_spec())
        assert result.outcome == "invalid", bad
        assert result.primary_metric is None
    text = GOOD.replace('"p99_latency_ms": 22.5', '"p99_latency_ms": NaN')
    result = parse_result_text(text, _db_spec())
    assert result is not None and result.outcome == "invalid"


def test_declared_type_mismatches_are_invalid() -> None:
    payload = {
        "status": "completed", "primary_metric": 250.0, "metric_name": "tps",
        "p99_within_slo": True, "bench_duration_s": "ninety",
    }
    result = normalize_result(payload, _db_spec())
    assert result.outcome == "invalid"
    assert any("bench_duration_s" in v for v in result.violations)


def test_missing_status_and_gates_never_become_success() -> None:
    spec = _db_spec()
    no_status = {"primary_metric": 250.0, "p99_within_slo": True}
    result = normalize_result(no_status, spec)
    assert result.outcome == "invalid"
    assert "missing status" in result.violations
    # A completed payload without gate signals: gates stay undeclared and
    # normalize to False — never a successful default.
    completed = {
        "status": "completed", "primary_metric": 250.0,
        "metric_name": "tps", "p99_within_slo": True,
    }
    result = normalize_result(completed, spec)
    assert result.outcome == "completed"
    assert result.gates_passed is None
    record = result.to_dict()
    assert record["gates_declared"] is False
    assert record["training_gates_passed"] is False


def test_unknown_status_semantics_and_schema_versions_are_invalid() -> None:
    spec = _db_spec()
    result = normalize_result(
        {"status": "mystery", "primary_metric": 1.0}, spec
    )
    assert result.outcome == "invalid"
    result = normalize_result(
        {
            "status": "completed", "primary_metric": 1.0, "metric_name": "tps",
            "p99_within_slo": True, "schema_version": "v0.9-unknown",
        },
        spec,
    )
    assert result.outcome == "invalid"
    assert any("schema version" in v for v in result.violations)
    ok = normalize_result(
        {
            "status": "completed", "primary_metric": 1.0, "metric_name": "tps",
            "p99_within_slo": True, "schema_version": RESULT_SCHEMA_VERSION,
        },
        spec,
    )
    assert ok.outcome == "completed"


# --- extraction: noise, multiple markers, truncated, invalid JSON ----------


def test_marker_parses_among_noise_and_multiple_markers() -> None:
    spec = _db_spec()
    noisy = "log line one\n" + GOOD + "\n" + "log line two\n"
    result = parse_result_text(noisy, spec)
    assert result is not None and result.outcome == "completed"
    # First well-formed marker wins; a later marker cannot replace it.
    second = GOOD.replace('"primary_metric": 250.0', '"primary_metric": 999.0')
    result = parse_result_text(noisy + second + "\n", spec)
    assert result is not None and result.primary_metric == 250.0
    # A malformed marker is scanned past; the valid one still parses.
    malformed = 'ITERATION_RESULT: {"status": "comp'
    result = parse_result_text(malformed + "\n" + GOOD + "\n", spec)
    assert result is not None and result.outcome == "completed"


def test_truncated_and_invalid_json_yield_no_result() -> None:
    spec = _db_spec()
    assert parse_result_text('ITERATION_RESULT: {"status": "comp', spec) is None
    assert parse_result_text("ITERATION_RESULT: {broken json}", spec) is None
    assert parse_result_text("ITERATION_RESULT: [1, 2, 3]", spec) is None
    assert parse_result_text("no result here at all", spec) is None


def test_declared_format_and_marker_prefix_are_honored() -> None:
    json_spec = ResultSpec(format="json_marker", marker_prefix="CUSTOM_RESULT:")
    assert parse_result_text(GOOD, json_spec) is None
    custom = GOOD.replace("ITERATION_RESULT:", "CUSTOM_RESULT:")
    result = parse_result_text(custom, json_spec)
    assert result is not None and result.outcome == "completed"
    kv_spec = ResultSpec(format="delimited_kv")
    kv_text = "---\nstatus: completed\nprimary_metric: 1.5\n---\n"
    result = parse_result_text(kv_text, kv_spec)
    assert result is not None and result.outcome == "completed"
    # A json_marker spec does not read KV blocks (garbage never parses as a
    # result)...
    assert parse_result_text(kv_text, json_spec) is None
    # ...while the marker channel (declared prefix) works for every format.
    assert parse_result_text(GOOD, kv_spec) is not None


def test_bare_json_is_an_artifact_form_not_an_agent_marker() -> None:
    spec = _db_spec()
    bare = json.dumps(
        {
            "status": "completed", "primary_metric": 2.0, "metric_name": "tps",
            "p99_within_slo": True,
        }
    )
    # Artifact/file collection accepts a bare JSON object...
    assert parse_result_text(bare, spec) is not None
    # ...but agent text must carry the declared marker (relay contract).
    assert parse_result_text(bare, spec, allow_bare_json=False) is None


# --- runtime: declared marker honored end-to-end ---------------------------


def _runtime_with_marker(
    marker: str, require_signed: bool = True
) -> ManifestSkillRuntime:
    doc = yaml.safe_load(
        (REPO_ROOT / "skills" / "db-config-tuning" / "SKILL.yaml").read_text(
            encoding="utf-8"
        )
    )
    doc["output_parser"]["iteration_marker"] = marker
    doc["output_parser"]["require_signed_metrics"] = require_signed
    manifest = ResearchSkillManifest.model_validate(doc)
    return ManifestSkillRuntime(manifest, None)


def test_custom_marker_parses_through_the_runtime() -> None:
    runtime = _runtime_with_marker("CUSTOM_RESULT:")
    config = types.SimpleNamespace(skill_params={}, workspace_path="/ws")
    custom = GOOD.replace("ITERATION_RESULT:", "CUSTOM_RESULT:")
    result = runtime.parse_iteration(custom)
    assert result is not None and result["primary_metric"] == 250.0
    # The fixed prefix no longer parses when the marker is declared otherwise.
    assert runtime.parse_iteration(GOOD) is None
    assert runtime.iteration_marker_prefix() == "CUSTOM_RESULT:"
    assert runtime.parse_result(custom) is not None
    assert config is not None


def test_signed_and_unsigned_imported_results() -> None:
    runtime = _runtime_with_marker("ITERATION_RESULT:")
    nonce = b"\\x01" * 32
    forged = GOOD.replace('"server_nonce": "aa"', '"server_nonce": "deadbeef"')
    # Signed skill: a missing/wrong nonce rejects the imported result.
    assert runtime.parse_iteration(forged, session_nonce=nonce) is None
    signed = GOOD.replace('"server_nonce": "aa"', f'"server_nonce": "{nonce.hex()}"')
    verified = runtime.parse_iteration(signed, session_nonce=nonce)
    assert verified is not None
    assert verified["metrics_verification"] == "metrics_verified"
    # Signed skill without a session nonce: explicit downgrade label.
    downgraded = runtime.parse_iteration(signed)
    assert downgraded is not None
    assert downgraded["metrics_verification"] == "metrics_unverified"
    # Unsigned skill: no verification claim is attached by the contract.
    unsigned = _runtime_with_marker("ITERATION_RESULT:", require_signed=False)
    plain = unsigned.parse_iteration(signed)
    assert plain is not None
    assert "metrics_verification" not in plain


def test_unknown_field_type_declarations_are_rejected_at_load() -> None:
    with pytest.raises(ValueError):
        FieldTypes.model_validate({"p99_latency_ms": "furlongs"})
    doc = yaml.safe_load(
        (REPO_ROOT / "skills" / "db-config-tuning" / "SKILL.yaml").read_text(
            encoding="utf-8"
        )
    )
    doc["output_parser"]["field_types"] = {"tps": "furlongs"}
    with pytest.raises(ValueError):
        ResearchSkillManifest.model_validate(doc)


def test_stale_fallback_files_are_ignored(tmp_path: Path, monkeypatch) -> None:
    """A marker file older than the command start is stale evidence."""
    from src.config import settings
    from src.core.orchestrator import AgentOrchestrator

    ws_root = tmp_path / "workspace"
    marker_dir = ws_root / "runs" / "db-config-tuning" / "DOGE-USDT" / "15m"
    marker_dir.mkdir(parents=True)
    monkeypatch.setattr(settings, "workspace_root", str(ws_root))
    manifest = load_skill_manifest(
        REPO_ROOT / "skills" / "db-config-tuning" / "SKILL.yaml"
    )
    runtime = ManifestSkillRuntime(manifest, None)
    orchestrator = object.__new__(AgentOrchestrator)
    config = types.SimpleNamespace(
        id="res_stale", subject_id="DOGE-USDT", variant="15m",
        instrument="DOGE-USDT", timeframe="15m",
    )
    orchestrator._session_skills = {"res_stale": runtime}
    marker_path = marker_dir / "bench_result.json"
    marker_path.write_text(GOOD, encoding="utf-8")
    import os
    old = os.stat(marker_path).st_mtime - 120
    os.utime(marker_path, (old, old))
    assert orchestrator._read_marker_file(config, min_mtime=old + 60) is None
    # The same fresh file is consumed when it postdates the command start.
    marker_path.write_text(GOOD, encoding="utf-8")
    assert orchestrator._read_marker_file(config, min_mtime=old) is not None
