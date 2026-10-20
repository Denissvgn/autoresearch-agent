"""Adaptive phase-advancement plugin (motivating skill case 1).

The completion rule adapts to the evidence history: advance early when
the stage records convergence, or when the recent trend plateaus. Fixed
declarative evidence_keys cannot express "advance on early convergence
OR a plateau in the recent history" — the rule needs the values, not just
the keys. Input: JSON on stdin; output: JSON on stdout (pinned schema).
"""
import json
import sys

SCHEMA = "phase-advancement-plugin.v1"


def main() -> None:
    payload = json.load(sys.stdin)
    evidence = payload.get("evidence") or {}
    share = bool(payload.get("declarative_share"))
    history = evidence.get("trend") or []

    converged_early = bool(evidence.get("converged_early"))
    plateau = len(history) >= 3 and max(history[-3:]) - min(history[-3:]) < 0.01

    advance = share and (converged_early or plateau)
    rule = (
        "adaptive: advance on early convergence or a three-point plateau"
    )
    print(json.dumps({"schema": SCHEMA, "advance": advance, "rule": rule}))


if __name__ == "__main__":
    main()
