#!/usr/bin/env python3
"""Custom JSONL driver: a managed external research driver.

This program speaks the versioned JSONL transport on stdout and knows
nothing about the host's internals. It proposes candidates and requests
evaluation — its proposals are candidates (model-proposed), never
verified results or promotion approvals. Its ordinary shell activity
(digesting files here) is ordinary tool access, not evaluator execution.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys

CONTRACT_VERSION = "autoresearch_harness.v1"


def emit(event: dict) -> None:
    sys.stdout.write(json.dumps(event, sort_keys=True) + "\n")
    sys.stdout.flush()


def main() -> int:
    sequence = 0

    def next_event(event_type: str, payload: dict) -> None:
        nonlocal sequence
        sequence += 1
        emit(
            {
                "event_id": f"drv-{sequence}",
                "type": event_type,
                "sequence": sequence,
                "payload": payload,
            }
        )

    # 1. the version handshake is mandatory
    emit(
        {
            "event_id": "drv-hello",
            "type": "hello",
            "sequence": 0,
            "contract_version": CONTRACT_VERSION,
            "payload": {"driver": "jsonl-example"},
        }
    )

    # 2. ordinary shell activity: a digest computed by a shell command.
    #    This is tool access, not evaluator execution.
    result = subprocess.run(
        ["sh", "-c", "printf 'knob: 0.42\\n' | sha256sum"],
        capture_output=True,
        text=True,
        check=True,
    )
    digest = result.stdout.split()[0]

    # 3. propose a candidate (it is a proposal, not a verified result)
    next_event(
        "proposal",
        {
            "proposal_id": "prop-1",
            "kind": "candidate",
            "target": os.environ.get("AGENT_RUN_ID", "run"),
            "payload": {"digest": digest, "content": "knob: 0.42\n"},
        },
    )

    # 4. request evaluation — the trusted channel will judge it
    next_event(
        "evaluation_request",
        {"run_id": os.environ.get("AGENT_RUN_ID", "run"), "digest": digest},
    )

    # 5. done
    next_event("closed", {"status": "completed"})
    return 0


if __name__ == "__main__":
    sys.exit(main())
