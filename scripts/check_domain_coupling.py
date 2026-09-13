#!/usr/bin/env python3
"""Domain-coupling guard: fail when TRAID-platform vocabulary creeps back in.

Checks src/ and ui/src (plus the Dockerfile) for tokens that couple the
service to the removed trading platform. The legacy alias layer
(src/core/legacy_alias.py) and the legacy phase-plan tables (kept only to
render historical DB rows) are exempt.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN = [
    r"\btraid\b",
    r"\bvdmc\b",
    r"ensemble_trainer",
    r"rl_trainer",
    r"mlflow[_-]service",
    r"instrument_configs",
    r"\btrading_mode\b",
    r"agent_strategy",
    r"initial_balance",
    r"\bnats_url\b",
    r"data_ingest_url",
    r"feature_service_url",
    r"admin_service_url",
    r"inference_service_url",
    r"vdmc_indicator",
    r"scripts/autotuner",
    r"pipeline_controller",
]

# legacy_alias.py + research_phase_plan.py keep the legacy model_type map and
# historical phase tables so pre-migration DB rows still render.
# state_store.py / postgres_state_store.py keep legacy columns (instrument,
# trading_mode, ...) as storage back-compat; nothing writes trading values.
EXEMPT_PATHS = (
    "src/core/legacy_alias.py",
    "src/core/research_phase_plan.py",
    "src/core/state_store.py",
    "src/core/postgres_state_store.py",
)

TARGETS = [REPO_ROOT / "src", REPO_ROOT / "ui" / "src", REPO_ROOT / "Dockerfile"]
PATTERN = re.compile("|".join(FORBIDDEN), re.IGNORECASE)


def main() -> int:
    violations: list[str] = []
    for target in TARGETS:
        files = [target] if target.is_file() else sorted(target.rglob("*"))
        for path in files:
            if not path.is_file() or path.suffix not in (".py", ".ts", ".tsx", ""):
                continue
            rel = path.relative_to(REPO_ROOT).as_posix()
            if rel in EXEMPT_PATHS:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for lineno, line in enumerate(text.splitlines(), 1):
                # Lines that STRIP legacy platform secret names are allowed
                # (defense-in-depth denylists).
                if "domain-coupling: denylist" in line:
                    continue
                if PATTERN.search(line):
                    violations.append(f"{rel}:{lineno}: {line.strip()[:100]}")
    if violations:
        print("Domain-coupling violations found:")
        for v in violations:
            print(f"  {v}")
        return 1
    print("Domain-coupling guard: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
