"""Deterministic conformance evaluator (fixture skill package asset).

Stdlib only. The governed command runner executes this as the skill's
experiment command; stdout carries the skill's own iteration announcement —
both result channels: the declared marker line and the ``---`` delimited
key/value block — so every declared parser format reads the same observation.

Metrics are deterministic and come from the bound argv sequence; a per-
workspace counter file advances on each call so one workflow can observe a
scripted metric sequence. The counter path resolves inside the session
workspace, which makes resolved CWD/inputs observable in the result.
"""

from __future__ import annotations

import json
import pathlib
import sys


def _parse_flags(argv: list[str]) -> dict[str, str]:
    opts: dict[str, str] = {}
    i = 0
    while i < len(argv):
        token = argv[i]
        if token.startswith("--") and i + 1 < len(argv):
            opts[token[2:]] = argv[i + 1]
            i += 2
        else:
            i += 1
    return opts


def main() -> int:
    opts = _parse_flags(sys.argv[1:])
    sequence = [
        float(part)
        for part in (opts.get("sequence") or "").split(",")
        if part.strip()
    ]
    metric_name = opts.get("metric-name") or "primary_metric"
    status = opts.get("status") or "success"
    gates_passed = (opts.get("gates") or "pass").strip().lower() != "fail"
    echo = opts.get("echo") or ""
    threshold_sequence = [
        part.strip().lower() == "true"
        for part in (opts.get("threshold-sequence") or "true").split(",")
        if part.strip()
    ]

    # Resolved-input observability: optional staged input is read and echoed.
    input_note = ""
    input_name = opts.get("input")
    if input_name:
        candidate = pathlib.Path(input_name)
        input_note = (
            f"read:{candidate.name}:{candidate.read_text(encoding='utf-8').strip()}"
            if candidate.exists()
            else f"missing:{candidate.name}"
        )

    counter_path = pathlib.Path(opts.get("counter") or ".conformance_counter")
    index = 0
    if counter_path.exists():
        index = int(counter_path.read_text(encoding="utf-8").strip() or "0")
    counter_path.write_text(str(index + 1), encoding="utf-8")

    threshold_met = threshold_sequence[min(index, len(threshold_sequence) - 1)]

    # The declared candidate config (``config_flag``): read as the metric
    # source when no scripted sequence is bound (per-trial candidates carry
    # their own value), rewritten so the next pre-run snapshot records the
    # evolved candidate.
    target_name = opts.get("target")
    candidate_metric = None
    if target_name and pathlib.Path(target_name).exists():
        for line in pathlib.Path(target_name).read_text(
            encoding="utf-8",
        ).splitlines():
            if line.startswith("metric:"):
                candidate_metric = float(line.split(":", 1)[1].strip())
                break
    if sequence:
        metric = sequence[min(index, len(sequence) - 1)]
    elif candidate_metric is not None:
        metric = candidate_metric
    else:
        metric = 1.0
    if target_name:
        pathlib.Path(target_name).write_text(
            f"metric: {metric}\n", encoding="utf-8",
        )

    payload = {
        "status": status,
        "primary_metric": metric,
        "metric_name": metric_name,
        "training_gates_passed": gates_passed,
        "all_gates_passed": gates_passed,
        "threshold_met": threshold_met,
    }
    if echo:
        payload["bound_flags"] = echo
    if input_note:
        payload["bound_input"] = input_note

    marker = opts.get("marker") or "ITERATION_RESULT:"
    emit_format = (opts.get("emit-format") or "both").strip().lower()
    kv_lines = ["---"]
    for key in ("status", "primary_metric", "metric_name",
                "training_gates_passed", "all_gates_passed", "threshold_met",
                "bound_flags", "bound_input"):
        if key in payload:
            kv_lines.append(f"{key}: {payload[key]}")
    kv_lines.append("---")
    kv_text = "\n".join(kv_lines) + "\n"
    if emit_format in ("json", "both"):
        print(f"{marker} {json.dumps(payload, sort_keys=True)}")
    if emit_format in ("kv", "both"):
        print(kv_text, end="")
    # Marker-file channel: the KV block lands next to the candidate config
    # (trial dir for staged trials, session workspace otherwise).
    marker_dir = (
        pathlib.Path(target_name).parent if target_name else pathlib.Path(".")
    )
    (marker_dir / "result.kv").write_text(kv_text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
