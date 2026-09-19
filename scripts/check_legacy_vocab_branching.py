#!/usr/bin/env python3
"""Legacy-vocabulary branching guard.

The service is skill-driven: sessions name an installed skill and every
domain decision (paths, phase plans, promotion targets, gate evaluation)
derives from the skill manifest. The legacy ``model_type`` vocabulary
(``direction``/``volatility``/``rl``) is frozen history — readable forever,
branched on only inside the frozen legacy surfaces listed below.

This guard fails when NEW code branches on the legacy vocabulary outside
those surfaces, so the invariant is enforced by CI rather than by
convention. To extend the allowlist, add the file with a reason string —
an extension is a design decision, not a lint fix.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Branch shapes that key runtime behavior on the legacy vocabulary.
PATTERNS = [
    re.compile(r"model_type\s*=="),
    re.compile(r'==\s*"direction"'),
    re.compile(r'==\s*"volatility"'),
    re.compile(r'==\s*"rl"'),
    re.compile(r"model_type\s+in\s*\{"),
    re.compile(r"is_known_model_type\("),
]

#: Frozen surfaces where legacy-vocabulary branching is sanctioned.
ALLOWED: dict[str, str] = {
    "src/compat/legacy_alias.py": "the alias registry itself (the translation)",
    "src/compat/legacy_phase_tables.py": "frozen historical phase tables (render-only)",
    "src/core/research_manifest.py": "documented ML-trio manifest carve-out + identity resolution",
    "src/api/research.py": "legacy request translation at the API boundary",
    "src/core/consistency_validator.py": "ML serving-era evidence evaluation (frozen)",
    "src/core/research_state.py": "legacy ML session-state reconstruction (frozen)",
    "src/core/research_phase_plan.py": "transitional fallback phase tables",
    "src/core/orchestrator.py": "legacy config.domain paths awaiting transitional-runtime removal",
    "src/core/state_store.py": "legacy RL query branch (frozen)",
    "src/core/postgres_state_store.py": "legacy RL query branch (frozen)",
    "src/core/config_promoter.py": "ML gate-bundle evaluation (frozen)",
    "src/core/development_gate_bundle.py": "ML gate bundles (frozen)",
    "src/core/output_parser.py": "legacy delimited-KV metric-key parsing",
    "src/core/skill_runtime.py": "docstring prose documenting the removed pattern",
    "src/core/skill_manifest.py": "docstring prose documenting the removed pattern",
}


def main() -> int:
    src_root = REPO_ROOT / "src"
    violations: list[str] = []
    for path in sorted(src_root.rglob("*.py")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        in_compat = rel.startswith("src/compat/")
        allowed = in_compat or rel in ALLOWED
        if allowed:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(lines, 1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            for pattern in PATTERNS:
                if pattern.search(line):
                    violations.append(
                        f"{rel}:{lineno}: {stripped.strip()[:90]}"
                    )
                    break
    if violations:
        print("Legacy-vocabulary branching outside the frozen surfaces:")
        for v in violations:
            print(f"  {v}")
        print(
            "\nNew code must key on the skill manifest, not the legacy\n"
            "model_type vocabulary. Extending the allowlist is a design\n"
            "decision — add the file with a reason in this script."
        )
        return 1
    print(
        "Legacy-vocabulary branching guard: clean "
        f"({len(ALLOWED)} frozen surfaces allowlisted)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
