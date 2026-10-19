"""Measured latency minimization over an agent-owned loopback service.

A controlled benchmark: a loopback HTTP service serving a frozen data/
query workload, a request mix frozen before comparison, warmup, a
resource envelope, percentile latency with guardrails, repeated
measurements with uncertainty, and an immutable evaluation-context
identity. A candidate becomes the minimization winner only when its
measured improvement passes guardrails and qualification evidence;
noisy or incomparable samples never win. A simulated (sleep-based)
mode exists only as a separately labeled mode and is never comparable
with measured results. The workload ships as a skill (no core edits)
and every result labels its environment limits.
"""
from __future__ import annotations

import hashlib
import json
import platform
import random
import statistics
import sys
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence

MODE_MEASURED = "measured"
MODE_SIMULATED = "simulated"


@dataclass(frozen=True)
class Workload:
    """The fixed data/query workload: a dataset and a frozen request mix."""

    workload_id: str
    items: tuple[tuple[str, float], ...]
    request_keys: tuple[str, ...]

    def digest(self) -> str:
        canonical = json.dumps(
            {
                "workload_id": self.workload_id,
                "items": [list(i) for i in self.items],
                "request_keys": list(self.request_keys),
            },
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_workload(
    *, workload_id: str = "latency-min-1", size: int = 20000
) -> Workload:
    """A frozen workload: a dataset and a request mix decided before runs."""
    items = tuple((f"key-{i}", float(i)) for i in range(size))
    rng = random.Random(20261019)  # frozen: the mix never changes per run
    keys = tuple(f"key-{rng.randrange(size)}" for _ in range(120))
    return Workload(workload_id=workload_id, items=items, request_keys=keys)


# server variants: real implementation changes, never sleep-based scores
def _variant_scan(items: tuple[tuple[str, float], ...], key: str) -> float:
    for k, v in items:
        if k == key:
            return v
    return -1.0


_INDEX_CACHE: dict[tuple[int, int], dict[str, float]] = {}


def _variant_index(
    items: tuple[tuple[str, float], ...], key: str
) -> float:
    cache_key = (id(items), len(items))
    index = _INDEX_CACHE.get(cache_key)
    if index is None:
        index = dict(items)
        _INDEX_CACHE[cache_key] = index
    return index.get(key, -1.0)


def _variant_rescan(
    items: tuple[tuple[str, float], ...], key: str
) -> float:
    # a real regression: recompute everything for every query
    total = 0.0
    found = -1.0
    for k, v in items:
        total += v
        if k == key:
            found = v
    return found + total * 0.0


VARIANTS: dict[str, Callable[[tuple[tuple[str, float], ...], str], float]] = {
    "baseline-scan": _variant_scan,
    "improved-index": _variant_index,
    "regressed-rescan": _variant_rescan,
}


class _QueryHandler(BaseHTTPRequestHandler):
    variant: Callable[[tuple[tuple[str, float], ...], str], float]
    items: tuple[tuple[str, float], ...] = ()

    def do_GET(self) -> None:  # noqa: N802 (http.server API)
        key = self.path.partition("?key=")[2]
        value = self.variant(self.items, key)
        body = json.dumps({"value": value}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: Any) -> None:  # silence per-request logs
        return


class LoopbackService:
    """The agent-owned loopback HTTP service under measurement."""

    def __init__(
        self,
        variant: Callable[[tuple[tuple[str, float], ...], str], float],
        items: tuple[tuple[str, float], ...],
    ) -> None:
        handler = type(
            "BoundQueryHandler",
            (_QueryHandler,),
            {"variant": staticmethod(variant), "items": items},
        )
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True
        )

    @property
    def address(self) -> tuple[str, int]:
        return self._server.server_address[:2]  # type: ignore[return-value]

    def __enter__(self) -> "LoopbackService":
        self._thread.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5.0)


@dataclass(frozen=True)
class MeasurementProtocol:
    """Frozen before comparison: mix, warmup, repeats, guardrails."""

    protocol_id: str
    warmup_requests: int = 20
    repeats: int = 3
    requests_per_repeat: int = 40
    p_target: float = 0.95
    max_error_rate: float = 0.0
    min_throughput_rps: float = 0.0
    max_uncertainty: float = 0.35
    min_improvement: float = 0.10
    resource_envelope_threads: int = 8

    def digest(self) -> str:
        return hashlib.sha256(
            json.dumps(
                {
                    "protocol_id": self.protocol_id,
                    "warmup": self.warmup_requests,
                    "repeats": self.repeats,
                    "n": self.requests_per_repeat,
                    "p": self.p_target,
                    "env_threads": self.resource_envelope_threads,
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()


def evaluation_context(
    protocol: MeasurementProtocol,
    workload: Workload,
    *,
    mode: str = MODE_MEASURED,
) -> dict[str, Any]:
    """Immutable baseline/evaluation-context identity for comparability."""
    return {
        "context_digest": hashlib.sha256(
            f"{protocol.digest()}:{workload.digest()}:{mode}".encode("utf-8")
        ).hexdigest(),
        "protocol_id": protocol.protocol_id,
        "workload_id": workload.workload_id,
        "mode": mode,
        "environment": {
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "cpu_count": __import__("os").cpu_count(),
        },
        "environment_limits": (
            "results are machine- and load-specific: latency and throughput "
            "apply only to this environment label and resource envelope"
        ),
    }


def _calibrate(probe: Optional[Callable[[], float]] = None) -> float:
    """A fixed CPU probe: median of three rounds; contention detection."""
    if probe is not None:
        return probe()

    def _round() -> float:
        started = time.perf_counter()
        total = 0
        for i in range(200_000):
            total += i % 7
        return time.perf_counter() - started

    return statistics.median([_round(), _round(), _round()])


@dataclass
class Measurement:
    """One variant's measured result: evidence, not a claim."""

    variant_id: str
    mode: str
    context: dict[str, Any]
    p_target: float = 0.95
    repeat_latencies_s: list[list[float]] = field(default_factory=list)
    error_count: int = 0
    throughput_rps: float = 0.0
    contended: bool = False
    contention_ratio: float = 1.0

    @property
    def p_latencies(self) -> list[float]:
        """Per-repeat p-target latency samples."""
        values = []
        for repeat in self.repeat_latencies_s:
            ordered = sorted(repeat)
            index = min(
                len(ordered) - 1,
                int(round(self.p_target * (len(ordered) - 1))),
            )
            values.append(ordered[index])
        return values

    @property
    def median_p_latency(self) -> float:
        values = self.p_latencies
        return statistics.median(values) if values else 0.0

    @property
    def uncertainty(self) -> float:
        values = self.p_latencies
        if len(values) < 2:
            return 0.0
        center = statistics.median(values)
        return (max(values) - min(values)) / center if center else 0.0

    @property
    def error_rate(self) -> float:
        total = sum(len(r) for r in self.repeat_latencies_s) + self.error_count
        return self.error_count / total if total else 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "mode": self.mode,
            "context_digest": self.context["context_digest"],
            "context": self.context,
            "median_p_latency": self.median_p_latency,
            "uncertainty": self.uncertainty,
            "error_rate": self.error_rate,
            "throughput_rps": self.throughput_rps,
            "contended": self.contended,
            "contention_ratio": self.contention_ratio,
            "repeats": len(self.repeat_latencies_s),
        }


def run_measurement(
    *,
    variant_id: str,
    variant: Callable[[tuple[tuple[str, float], ...], str], float],
    workload: Workload,
    protocol: MeasurementProtocol,
    mode: str = MODE_MEASURED,
    probe: Optional[Callable[[], float]] = None,
) -> Measurement:
    """Measure one variant under the frozen protocol.

    The service is agent-owned (loopback), the request sequence is the
    frozen mix, and the real implementation does the work — there is no
    synthetic sleep anywhere in the measurement.
    """
    context = evaluation_context(protocol, workload, mode=mode)
    measurement = Measurement(
        variant_id=variant_id,
        mode=mode,
        context=context,
        p_target=protocol.p_target,
    )
    if mode != MODE_MEASURED:
        # simulated mode is a separately labeled record only: it never
        # executes the measured procedure and is never comparable
        measurement.contended = False
        return measurement

    before = _calibrate(probe)
    with LoopbackService(variant, workload.items) as service:
        host, port = service.address
        import http.client  # local import keeps the module surface small

        connection = http.client.HTTPConnection(host, port, timeout=10.0)
        try:
            keys = workload.request_keys
            for i in range(protocol.warmup_requests):
                connection.request("GET", f"/query?key={keys[i % len(keys)]}")
                connection.getresponse().read()
            request_index = 0
            elapsed_total = 0.0
            for _repeat in range(protocol.repeats):
                latencies: list[float] = []
                for _ in range(protocol.requests_per_repeat):
                    key = keys[request_index % len(keys)]
                    request_index += 1
                    started = time.perf_counter_ns()
                    try:
                        connection.request("GET", f"/query?key={key}")
                        connection.getresponse().read()
                    except OSError:
                        measurement.error_count += 1
                        continue
                    latencies.append(
                        (time.perf_counter_ns() - started) / 1e9
                    )
                elapsed_total += sum(latencies)
                measurement.repeat_latencies_s.append(latencies)
        finally:
            connection.close()
    after = _calibrate(probe)

    measurement.contention_ratio = after / before if before > 0 else 1.0
    measurement.contended = measurement.contention_ratio > 1.5
    measurement.throughput_rps = (
        sum(len(r) for r in measurement.repeat_latencies_s) / elapsed_total
        if elapsed_total > 0
        else 0.0
    )
    return measurement


@dataclass(frozen=True)
class MinimizationDecision:
    """Lower-is-better with guardrails: a winner only on qualified evidence."""

    winner: Optional[str]
    reason: str
    comparable: bool
    qualified: bool
    improvement: float
    guardrails: Mapping[str, bool]


def decide_minimization(
    baseline: Measurement,
    candidate: Measurement,
    protocol: MeasurementProtocol,
) -> MinimizationDecision:
    """Select a measured improvement only when constraints and evidence pass.

    Noisy samples (uncertainty above the protocol bound), contended runs,
    incomplete repeats, guardrail failures, and incomparable contexts can
    never become a production winner.
    """
    guardrails = {
        "error_rate": candidate.error_rate <= protocol.max_error_rate,
        "throughput": candidate.throughput_rps >= protocol.min_throughput_rps,
    }
    comparable = (
        baseline.mode == candidate.mode == MODE_MEASURED
        and baseline.context["context_digest"]
        == candidate.context["context_digest"]
    )
    qualified = (
        comparable
        and not baseline.contended
        and not candidate.contended
        and len(baseline.repeat_latencies_s) == protocol.repeats
        and len(candidate.repeat_latencies_s) == protocol.repeats
        and baseline.uncertainty <= protocol.max_uncertainty
        and candidate.uncertainty <= protocol.max_uncertainty
        and all(guardrails.values())
    )
    base = baseline.median_p_latency
    improvement = (
        (base - candidate.median_p_latency) / base
        if base > 0
        else 0.0  # lower is better
    )
    if not comparable:
        return MinimizationDecision(
            winner=None,
            reason=(
                "incomparable samples: contexts or modes differ"
            ),
            comparable=False,
            qualified=qualified,
            improvement=improvement,
            guardrails=guardrails,
        )
    if not qualified:
        reasons = []
        if baseline.contended or candidate.contended:
            reasons.append("resource contention detected")
        if (
            baseline.uncertainty > protocol.max_uncertainty
            or candidate.uncertainty > protocol.max_uncertainty
        ):
            reasons.append("noisy samples exceed the uncertainty bound")
        if not all(guardrails.values()):
            reasons.append("guardrails failed")
        if len(baseline.repeat_latencies_s) != protocol.repeats or len(
            candidate.repeat_latencies_s
        ) != protocol.repeats:
            reasons.append("incomplete repeats")
        return MinimizationDecision(
            winner=None,
            reason="; ".join(reasons) or "qualification evidence incomplete",
            comparable=comparable,
            qualified=False,
            improvement=improvement,
            guardrails=guardrails,
        )
    if improvement < protocol.min_improvement:
        return MinimizationDecision(
            winner=None,
            reason=(
                f"improvement {improvement:.3f} below the minimum "
                f"{protocol.min_improvement:.3f} (or a regression)"
            ),
            comparable=comparable,
            qualified=qualified,
            improvement=improvement,
            guardrails=guardrails,
        )
    return MinimizationDecision(
        winner=candidate.variant_id,
        reason="measured improvement passes guardrails and qualification",
        comparable=comparable,
        qualified=qualified,
        improvement=improvement,
        guardrails=guardrails,
    )


class MeasurementStore:
    """Storage for measurements: JSONL keyed by context digest + variant."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def record(self, measurement: Measurement) -> None:
        row = measurement.as_dict()
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")

    def load(
        self, *, context_digest: str, variant_id: str
    ) -> Optional[dict[str, Any]]:
        if not self._path.exists():
            return None
        found = None
        for line in self._path.read_text().splitlines():
            row = json.loads(line)
            if (
                row.get("context_digest") == context_digest
                and row.get("variant_id") == variant_id
            ):
                found = row
        return found


def promote_minimized(
    *, baseline: Measurement, candidate: Measurement,
    protocol: MeasurementProtocol, store: MeasurementStore
) -> dict[str, Any]:
    """Promotion through storage: only a qualified winner is promoted."""
    decision = decide_minimization(baseline, candidate, protocol)
    stored = store.load(
        context_digest=candidate.context["context_digest"],
        variant_id=candidate.variant_id,
    )
    if stored is None:
        raise ValueError(
            "the candidate measurement is not present in storage: "
            "promotion requires stored evidence"
        )
    if decision.winner is None:
        raise ValueError(f"not promotable: {decision.reason}")
    return {
        "promoted": decision.winner,
        "improvement": decision.improvement,
        "context_digest": candidate.context["context_digest"],
        "mode": candidate.mode,
        "environment_limits": candidate.context["environment_limits"],
    }

