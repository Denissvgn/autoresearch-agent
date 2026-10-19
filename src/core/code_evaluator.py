"""The isolated code evaluator: real tests, lint, and types.

A candidate bundle is a set of file contents for named target files in a
fixture project. The evaluator copies the project to an isolated work
directory, applies the bundle with test files and evaluation entrypoints
protected (candidate edits to them are reverted — editing tests can never
improve a result), and runs the real fixed tests, lint, and type checks
with bounded time. Performance is measured only where a controlled
benchmark exists; a required-but-unmeasured performance gate is a
rejection, never a pass.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

PROTECTED_PREFIXES = ("tests/", "eval/")
PROTECTED_NAMES = ("conftest.py",)

DEFAULT_TIMEOUT_S = 60.0


@dataclass(frozen=True)
class CandidateBundle:
    """A multi-file candidate: named target files with full contents."""

    candidate_id: str
    files: Mapping[str, str]

    def digest(self) -> str:
        canonical = json.dumps(
            {name: self.files[name] for name in sorted(self.files)},
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EvalRequirements:
    """Explicit gates: tests, lint, types, and optional performance."""

    expected_tests: tuple[str, ...]
    lint: bool = True
    type_check: bool = True
    performance_required: bool = False
    performance_benchmark: Optional[str] = None
    performance_budget_s: Optional[float] = None


@dataclass
class EvalReport:
    """The trusted evaluator's report: real evidence, honest gaps."""

    passed: bool
    bundle_digest: str
    exit_codes: dict[str, int] = field(default_factory=dict)
    tests: dict[str, Any] = field(default_factory=dict)
    lint_ok: bool = False
    type_ok: bool = False
    performance: Optional[dict[str, Any]] = None
    protected_edits_reverted: tuple[str, ...] = ()
    failures: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def is_protected(path: str) -> bool:
    normalized = path.replace("\\", "/").lstrip("./")
    if normalized.split("/")[-1] in PROTECTED_NAMES:
        return True
    return any(normalized.startswith(prefix) for prefix in PROTECTED_PREFIXES)


def apply_bundle(
    project_root: Path, bundle: CandidateBundle, workdir: Path
) -> tuple[Path, tuple[str, ...]]:
    """Copy the project and apply the bundle; protected files revert."""
    if workdir.exists():
        shutil.rmtree(workdir)
    shutil.copytree(project_root, workdir)
    reverted = []
    for name, content in sorted(bundle.files.items()):
        parts = name.replace("\\", "/").split("/")
        if ".." in parts:
            raise ValueError(f"unsafe target path {name!r}")
        normalized = "/".join(p for p in parts if p not in (".", ""))
        if is_protected(normalized):
            reverted.append(normalized)
            continue
        target = workdir / normalized
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return workdir, tuple(reverted)


def _run(
    command: Sequence[str], *, cwd: Path, timeout_s: float
) -> tuple[int, str, bool]:
    """Run one real check with a bounded timeout. Returns (exit, out, timed_out)."""
    try:
        completed = subprocess.run(
            list(command),
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        return (
            completed.returncode,
            completed.stdout + completed.stderr,
            False,
        )
    except subprocess.TimeoutExpired as exc:
        output = ""
        if exc.stdout:
            output += (
                exc.stdout.decode("utf-8", "replace")
                if isinstance(exc.stdout, bytes)
                else exc.stdout
            )
        return (124, output, True)


def _parse_test_report(output: str) -> dict[str, Any]:
    results: dict[str, str] = {}
    for line in output.splitlines():
        if "::" not in line:
            continue
        tokens = line.split()
        node = tokens[0]
        for verdict in ("PASSED", "FAILED", "SKIPPED", "ERROR"):
            if verdict in tokens[1:]:
                results[node.split("::")[-1]] = verdict
                break
    return results


def evaluate_bundle(
    project_root: Path,
    bundle: CandidateBundle,
    requirements: EvalRequirements,
    *,
    workdir: Optional[Path] = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> EvalReport:
    """Evaluate a bundle against the fixed gates with real tooling."""
    work = workdir or Path(
        tempfile.mkdtemp(prefix=f"code-eval-{bundle.candidate_id}-")
    )
    work, reverted = apply_bundle(project_root, bundle, work)
    failures: list[str] = []
    exit_codes: dict[str, int] = {}

    # 1. the expected test set must be collected (deletion is visible)
    code, output, timed_out = _run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests",
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        cwd=work,
        timeout_s=timeout_s,
    )
    exit_codes["collect"] = code
    collected = {
        line.split("::")[-1]
        for line in output.splitlines()
        if "::" in line and not line.startswith("ERROR")
    }
    missing = sorted(set(requirements.expected_tests) - collected)
    if timed_out:
        failures.append("collect: timeout")
    elif code != 0:
        failures.append(f"collect: exit {code}")
    if missing:
        failures.append(f"tests missing from the run: {missing}")

    # 2. the real fixed tests must all pass (a skip is not a pass)
    code, output, timed_out = _run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests",
            "-v",
            "--tb=no",
            "-p",
            "no:cacheprovider",
        ],
        cwd=work,
        timeout_s=timeout_s,
    )
    exit_codes["tests"] = code
    report = _parse_test_report(output)
    verdicts = {
        name: report.get(name, "MISSING")
        for name in requirements.expected_tests
    }
    tests = {
        "expected": list(requirements.expected_tests),
        "verdicts": verdicts,
        "passed": sum(1 for v in verdicts.values() if v == "PASSED"),
        "failed": sum(1 for v in verdicts.values() if v == "FAILED"),
        "skipped": sum(1 for v in verdicts.values() if v == "SKIPPED"),
        "missing": sum(1 for v in verdicts.values() if v == "MISSING"),
    }
    if timed_out:
        failures.append("tests: timeout")
    elif code != 0:
        failures.append(f"tests: exit {code}")
    for name, verdict in sorted(verdicts.items()):
        if verdict != "PASSED":
            failures.append(f"test {name}: {verdict}")

    # 3. lint and types: real checks, explicit requirements
    lint_ok = True
    if requirements.lint:
        code, _output, timed_out = _run(
            [sys.executable, "-m", "ruff", "check", "calc", "tests"],
            cwd=work,
            timeout_s=timeout_s,
        )
        exit_codes["lint"] = code
        lint_ok = code == 0 and not timed_out
        if not lint_ok:
            failures.append(f"lint: exit {code}")

    type_ok = True
    if requirements.type_check:
        code, _output, timed_out = _run(
            [sys.executable, "-m", "mypy", "calc"],
            cwd=work,
            timeout_s=timeout_s,
        )
        exit_codes["type"] = code
        type_ok = code == 0 and not timed_out
        if not type_ok:
            failures.append(f"type: exit {code}")

    # 4. performance: measured only with a controlled benchmark
    performance: Optional[dict[str, Any]] = None
    if requirements.performance_required:
        if requirements.performance_benchmark is None:
            failures.append(
                "performance gate required but unmeasured (no controlled "
                "benchmark)"
            )
        else:
            started = time.perf_counter()
            code, _output, timed_out = _run(
                [
                    sys.executable,
                    "-c",
                    (
                        "from calc.totals import order_total\n"
                        "for _ in range(2000):\n"
                        "    order_total([(10.0, 2), (5.0, 3)], 10.0)\n"
                    ),
                ],
                cwd=work,
                timeout_s=timeout_s,
            )
            duration = time.perf_counter() - started
            exit_codes["performance"] = code
            within = (
                requirements.performance_budget_s is None
                or duration <= requirements.performance_budget_s
            )
            performance = {
                "benchmark": requirements.performance_benchmark,
                "duration_s": duration,
                "within_budget": bool(within and not timed_out),
            }
            if not performance["within_budget"]:
                failures.append("performance: outside the controlled budget")

    return EvalReport(
        passed=not failures,
        bundle_digest=bundle.digest(),
        exit_codes=exit_codes,
        tests=tests,
        lint_ok=lint_ok,
        type_ok=type_ok,
        performance=performance,
        protected_edits_reverted=reverted,
        failures=tuple(failures),
    )


def promotion_preview(
    *, bundle: CandidateBundle, report: EvalReport
) -> dict[str, Any]:
    """Artifact-bound promotion: the report travels with its bundle.

    The promotion is the exact snapshot that was evaluated — a mutated
    bundle can never ride an earlier report.
    """
    digest = bundle.digest()
    if report.bundle_digest != digest:
        raise ValueError(
            "the evaluation report is bound to a different bundle snapshot"
        )
    if not report.passed:
        raise ValueError("an unpassed evaluation never previews promotion")
    return {
        "bundle_digest": digest,
        "candidate_id": bundle.candidate_id,
        "passed": True,
        "tests_passed": report.tests.get("passed"),
        "snapshot": "promoted exactly as evaluated",
    }
