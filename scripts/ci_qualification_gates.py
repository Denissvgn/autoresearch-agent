#!/usr/bin/env python3
"""Named qualification gates for CI — enforceable compatibility claims.

Deterministic gates cover trust, domain semantics, migrations,
cross-store behavior, adapters, API/CLI/UI, and deployment artifacts.
Missing required coverage fails the run; every skip must carry an
explicit owner; qualification inputs and adapter versions are pinned;
live external checks are opt-in, budget-bounded, and reported in a lane
visibly separate from mocks; archived evidence is scanned for secrets.

Usage:
    python scripts/ci_qualification_gates.py [--gate NAME] [--live]
        [--report-dir PATH] [--dry-run]
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_VERSION = "autoresearch_harness.v1"
PIN_FILE = REPO_ROOT / "qualification-inputs.json"
LIVE_OPT_IN_ENV = "AUTORESEARCH_LIVE_JOBS"
BUDGET_ENV = "AUTORESEARCH_LIVE_BUDGET_USD"


# --------------------------------------------------------------------
# Skip ownership: a skip without an owner here is a failure.
# --------------------------------------------------------------------
@dataclass(frozen=True)
class SkipOwner:
    pattern: str
    owner: str
    reason: str


SKIP_OWNERS: tuple[SkipOwner, ...] = (
    SkipOwner(
        "tests/test_packaging.py::*installed*",
        "qa-ci",
        "env-gated: requires AUTORESEARCH_DIST_DIR release artifacts",
    ),
    SkipOwner(
        "tests/test_packaging.py::test_release_archives_contain_only_bundled_skills*",
        "qa-ci",
        "env-gated: requires AUTORESEARCH_DIST_DIR release artifacts",
    ),
    SkipOwner(
        "tests/test_result_artifact_ingestion.py::test_direction_and_volatility_marker_emit_results_json_path",
        "platform-maintainers",
        "checkout-dependent: platform workspace scripts (scripts/autotuner) are optional here",
    ),
    SkipOwner(
        "tests/test_agent_cli.py::*installed*",
        "qa-ci",
        "env-gated: requires AUTORESEARCH_DIST_DIR release artifacts",
    ),
    SkipOwner(
        "tests/test_codex_harness.py::*live*",
        "qa-maintainers",
        "opt-in live job: codex CLI + scoped credential required",
    ),
    SkipOwner(
        "tests/test_claude_code_harness.py::*live*",
        "qa-maintainers",
        "opt-in live job: claude CLI + scoped credential required",
    ),
    SkipOwner(
        "tests/test_prompt_evaluation_domain.py::*live*",
        "qa-maintainers",
        "opt-in live job: authorized scorer endpoint required",
    ),
    SkipOwner(
        "*postgres*",
        "qa-ci",
        "env-gated: Postgres legs run in the Distributed CI lane",
    ),
)


# --------------------------------------------------------------------
# Named gates
# --------------------------------------------------------------------
@dataclass(frozen=True)
class Gate:
    name: str
    kind: str  # "deterministic" | "live"
    suites: tuple[str, ...]
    required_coverage: tuple[str, ...]
    requires_env: tuple[str, ...] = ()
    budget_s: int = 900


GATES: tuple[Gate, ...] = (
    Gate(
        "trust",
        "deterministic",
        (
            "tests/test_result_authority.py",
            "tests/test_result_semantics.py",
            "tests/test_result_artifact_ingestion.py",
        ),
        (
            "test_result_authority",
            "test_result_semantics",
            "test_result_artifact_ingestion",
        ),
    ),
    Gate(
        "domain-semantics",
        "deterministic",
        (
            "tests/test_prompt_evaluation_domain.py",
            "tests/test_code_refactor_domain.py",
            "tests/test_latency_benchmark.py",
        ),
        ("prompt_evaluation", "code_refactor", "latency"),
    ),
    Gate(
        "migrations",
        "deterministic",
        (
            "tests/test_results_store_migrations.py",
            "tests/test_migration_restore_qualification.py",
            "tests/test_run_spec_persistence.py",
        ),
        ("results_store_migrations", "migration_restore", "run_spec"),
    ),
    Gate(
        "cross-store",
        "deterministic",
        (
            "tests/test_leaderboard_comparability.py",
            "tests/test_state_store.py",
        ),
        ("leaderboard_comparability", "state_store"),
    ),
    Gate(
        "adapters",
        "deterministic",
        (
            "tests/test_harness_sdk.py",
            "tests/test_builtin_harness.py",
            "tests/test_codex_harness.py",
            "tests/test_claude_code_harness.py",
            "tests/test_harness_contracts_g4.py",
        ),
        (
            "harness_sdk",
            "builtin_harness",
            "codex_harness",
            "claude_code_harness",
            "harness_contracts_g4",
        ),
    ),
    Gate(
        "api-cli-ui",
        "deterministic",
        (
            "tests/test_agent_api.py",
            "tests/test_agent_cli.py",
            "tests/test_harnesses_api.py",
            "tests/test_openapi_contract.py",
        ),
        ("agent_api", "agent_cli", "harnesses_api", "openapi_contract"),
    ),
    Gate(
        "deployment-artifacts",
        "deterministic",
        ("tests/test_packaging.py",),
        ("packaging",),
    ),
    Gate(
        "live-external",
        "live",
        (
            "tests/test_codex_harness.py",
            "tests/test_claude_code_harness.py",
        ),
        ("codex_harness", "claude_code_harness"),
        requires_env=(LIVE_OPT_IN_ENV, BUDGET_ENV),
        budget_s=1200,
    ),
)


# --------------------------------------------------------------------
# Pure checks (each has deliberate negative fixtures in tests/)
# --------------------------------------------------------------------
def check_required_coverage(
    passed_ids: Sequence[str], required: Sequence[str]
) -> list[str]:
    """An advertised feature without executable coverage fails."""
    errors = []
    for needle in required:
        if not any(needle in node for node in passed_ids):
            errors.append(
                f"missing conformance coverage: no passed test matches {needle!r}"
            )
    return errors


def check_skip_ownership(
    skipped_ids: Sequence[str], owners: Sequence[SkipOwner]
) -> list[str]:
    """A skip without a declared owner fails the run."""
    errors = []
    for node in sorted(set(skipped_ids)):
        if not any(fnmatch.fnmatch(node, o.pattern) for o in owners):
            errors.append(f"unowned skip (declare an owner or fix it): {node}")
    return errors


def check_pinned_inputs(
    pinned: Mapping[str, Any], current: Mapping[str, Any]
) -> list[str]:
    """Qualification inputs and adapter versions must match the pin."""
    errors = []
    for key in sorted(set(pinned) | set(current)):
        if pinned.get(key) != current.get(key):
            errors.append(
                f"qualification input drift for {key!r}: "
                f"pinned={pinned.get(key)!r} current={current.get(key)!r}"
            )
    return errors


def check_unsupported_report(
    descriptors: Sequence[Mapping[str, Any]],
    optional_capabilities: Sequence[str],
) -> list[str]:
    """Every unadvertised optional capability must carry a reason."""
    errors = []
    for descriptor in descriptors:
        advertised = set(descriptor.get("capabilities") or [])
        reported = {
            entry.get("capability")
            for entry in descriptor.get("unsupported_capabilities") or []
        }
        for capability in sorted(set(optional_capabilities) - advertised):
            if capability not in reported:
                errors.append(
                    f"harness {descriptor.get('name')!r} leaves "
                    f"unsupported capability {capability!r} unreported"
                )
        for entry in descriptor.get("unsupported_capabilities") or []:
            if not entry.get("reason"):
                errors.append(
                    f"harness {descriptor.get('name')!r} reports "
                    f"{entry.get('capability')!r} without a reason"
                )
    return errors


_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{24,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)


def scan_for_secrets(text: str, secret_values: Sequence[str] = ()) -> list[str]:
    """Archived evidence must contain no secrets."""
    findings = []
    for pattern in _SECRET_PATTERNS:
        for _match in pattern.findall(text):
            findings.append(f"secret pattern present: {pattern.pattern!r}")
    for value in secret_values:
        if value and value in text:
            findings.append("configured secret value present in evidence")
    return findings


def redact(text: str, secret_values: Sequence[str] = ()) -> str:
    redacted = text
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    for value in secret_values:
        if value:
            redacted = redacted.replace(value, "[REDACTED]")
    return redacted


# --------------------------------------------------------------------
# Pinned qualification inputs
# --------------------------------------------------------------------
def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect_current_inputs() -> dict[str, Any]:
    """Live identity of every qualification input the gates depend on."""
    sys.path.insert(0, str(REPO_ROOT))
    from src.api.harnesses import build_default_registry
    from src.core.latency_benchmark import build_workload

    registry = build_default_registry()
    adapters = {}
    for name in registry.names():
        identity = dict(registry.resolve(name).identity())
        adapters[name] = identity.get("version")
    inputs: dict[str, Any] = {
        "contract_version": CONTRACT_VERSION,
        "adapters": adapters,
        "benchmark_workload_digest": build_workload().digest(),
    }
    eval_root = REPO_ROOT / "skills" / "prompt-engineering" / "eval"
    if eval_root.exists():
        inputs["prompt_eval_sources"] = {
            path.name: _file_digest(path)
            for path in sorted(eval_root.glob("*.py"))
        }
    fixture_root = REPO_ROOT / "tests" / "fixtures" / "refactor_project"
    if fixture_root.exists():
        inputs["refactor_fixture"] = {
            str(path.relative_to(fixture_root)): _file_digest(path)
            for path in sorted(fixture_root.rglob("*.py"))
        }
    return inputs


# --------------------------------------------------------------------
# Pytest execution and result parsing
# --------------------------------------------------------------------
@dataclass
class GateResult:
    name: str
    kind: str
    status: str  # "pass" | "fail" | "skipped-live" | "skipped-declared"
    passed: list[str] = field(default_factory=list)  # noqa: RUF012
    failed: list[str] = field(default_factory=list)  # noqa: RUF012
    skipped: list[str] = field(default_factory=list)  # noqa: RUF012
    errors: list[str] = field(default_factory=list)  # noqa: RUF012
    duration_s: float = 0.0
    log: str = ""


def parse_pytest_output(output: str) -> tuple[list[str], list[str], list[str]]:
    passed: list[str] = []
    failed: list[str] = []
    skipped: list[str] = []
    for line in output.splitlines():
        stripped = line.strip()
        for verdict, bucket in (
            ("PASSED", passed),
            ("FAILED", failed),
            ("SKIPPED", skipped),
            ("ERROR", failed),
        ):
            tokens = stripped.split()
            if verdict in tokens[1:] and "::" in tokens[0]:
                bucket.append(tokens[0])
    return passed, failed, skipped


def run_pytest(suites: Sequence[str], timeout_s: int) -> tuple[int, str]:
    command = [
        str(REPO_ROOT / ".venv" / "bin" / "python"),
        "-m",
        "pytest",
        *suites,
        "-v",
        "--tb=short",
        "-p",
        "no:cacheprovider",
    ]
    completed = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout_s,
        env={**os.environ, "ANTHROPIC_BASE_URL": "http://anthropic.invalid",
             "ANTHROPIC_AUTH_TOKEN": "test-token"},
    )
    return completed.returncode, completed.stdout + completed.stderr


def evaluate_gate(
    gate: Gate,
    *,
    run: Callable[[Sequence[str], int], tuple[int, str]],
    owners: Sequence[SkipOwner] = SKIP_OWNERS,
    live_opt_in: bool = False,
    missing_env: Sequence[str] = (),
) -> GateResult:
    """One gate: coverage, ownership, and honest live separation."""
    result = GateResult(name=gate.name, kind=gate.kind, status="pass")
    if gate.kind == "live":
        if not live_opt_in:
            result.status = "skipped-live"
            result.errors.append(
                "live gate not opted in: set "
                f"{LIVE_OPT_IN_ENV}=1 with {BUDGET_ENV} and scoped credentials"
            )
            return result
        if missing_env:
            result.status = "fail"
            result.errors.append(
                f"live gate opted in but missing required env: {sorted(missing_env)}"
            )
            return result
    started = time.monotonic()
    try:
        code, output = run(gate.suites, gate.budget_s)
    except subprocess.TimeoutExpired:
        result.status = "fail"
        result.errors.append(f"gate exceeded its {gate.budget_s}s budget")
        return result
    result.duration_s = time.monotonic() - started
    passed, failed, skipped = parse_pytest_output(output)
    result.passed, result.failed, result.skipped = passed, failed, skipped
    result.log = redact(output)
    if failed or code != 0:
        result.status = "fail"
        result.errors.append(f"pytest exit {code}: {len(failed)} failed test(s)")
    result.errors.extend(check_required_coverage(passed, gate.required_coverage))
    result.errors.extend(check_skip_ownership(skipped, owners))
    if result.errors:
        result.status = "fail"
    return result


# --------------------------------------------------------------------
# Candidate run
# --------------------------------------------------------------------
def collect_capability_report() -> tuple[list[dict[str, Any]], list[str]]:
    """The unsupported-capability report the gates enforce."""
    from src.api.harnesses import _descriptor, build_default_registry
    from src.core.harness_contract import OPTIONAL_CAPABILITIES

    registry = build_default_registry()
    descriptors = [_descriptor(registry.resolve(n)) for n in registry.names()]
    errors = check_unsupported_report(descriptors, sorted(OPTIONAL_CAPABILITIES))
    return descriptors, errors


def write_evidence(
    report_dir: Path,
    payload: Mapping[str, Any],
    secret_values: Sequence[str] = (),
) -> list[str]:
    """Archive sanitized evidence; return sanitization findings."""
    text = json.dumps(payload, indent=2, sort_keys=True)
    findings = scan_for_secrets(text, secret_values)
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "gates.json").write_text(redact(text, secret_values))
    return findings


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gate", action="append", default=None)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--report-dir", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    selected = [
        g for g in GATES
        if args.gate is None or g.name in set(args.gate)
    ]
    missing_env = [
        name
        for name in ("AUTORESEARCH_CODEX_LIVE", "AUTORESEARCH_CLAUDE_LIVE")
        if not os.environ.get(name)
    ]

    errors: list[str] = []
    results: list[GateResult] = []
    for gate in selected:
        result = evaluate_gate(
            gate,
            run=run_pytest,
            live_opt_in=args.live,
            missing_env=missing_env if gate.kind == "live" else (),
        )
        results.append(result)
        marker = {"pass": "PASS", "fail": "FAIL"}.get(
            result.status, result.status
        )
        print(f"[{marker}] gate {result.name} ({result.kind})")
        for message in result.errors:
            print(f"    - {message}")

    # pinned qualification inputs and adapter versions
    current = collect_current_inputs()
    if PIN_FILE.exists():
        pinned = json.loads(PIN_FILE.read_text())
        drift = check_pinned_inputs(pinned, current)
        errors.extend(drift)
    else:
        errors.append(
            f"missing pinned qualification inputs: {PIN_FILE.name}"
        )

    # unsupported-capability reporting completeness
    descriptors, capability_errors = collect_capability_report()
    errors.extend(capability_errors)

    statuses = {r.name: r.status for r in results}
    deterministic_fails = [
        r.name for r in results if r.kind == "deterministic" and r.status != "pass"
    ]
    if deterministic_fails:
        errors.append(f"deterministic gates failed: {deterministic_fails}")

    report = {
        "kind": "ci-qualification-gates",
        "live_opt_in": bool(args.live),
        "gates": [
            {
                "name": r.name,
                "kind": r.kind,
                "status": r.status,
                "passed": len(r.passed),
                "failed": len(r.failed),
                "skipped": r.skipped,
                "errors": r.errors,
                "duration_s": round(r.duration_s, 3),
            }
            for r in results
        ],
        "capability_report": [
            {
                "name": d.get("name"),
                "version": d.get("version"),
                "capabilities": d.get("capabilities"),
                "unsupported": d.get("unsupported_capabilities"),
            }
            for d in descriptors
        ],
        "pinned_inputs": current,
        "errors": errors,
        "statuses": statuses,
    }
    secret_values = [
        os.environ.get(name, "")
        for name in ("ANTHROPIC_AUTH_TOKEN", "AUTORESEARCH_API_TOKEN")
    ]
    report_dir = Path(
        args.report_dir
        or (REPO_ROOT / "workspace" / "qualification" / "ci")
    )
    if not args.dry_run:
        findings = write_evidence(report_dir, report, secret_values)
        if findings:
            errors.append(f"evidence sanitization findings: {findings}")
            print(f"[FAIL] evidence sanitization: {findings}")

    ok = not errors
    print(
        f"[{'PASS' if ok else 'FAIL'}] qualification gates "
        f"({len(results)} lanes; live={bool(args.live)})"
    )
    for message in errors:
        print(f"    - {message}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())