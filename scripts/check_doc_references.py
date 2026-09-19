#!/usr/bin/env python3
"""Referenced-doc integrity guard.

Fails when a code comment, test, script, or workflow references a
``docs/<...>.md`` file that does not exist on disk. Code prose pointing at a
design document is a contract: when the target is deleted or renamed the
reference silently rots. Run in CI so a change that deletes or renames a
doc must also fix the sites referencing it.

Exemptions: none by design — if a reference must survive without a file,
rephrase the comment so it does not carry a docs-relative markdown path (the
doc scan only matches literal path-shaped strings).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

SCAN_ROOTS = ("src", "tests", "scripts", ".github")
DOC_PATH_RE = re.compile(r"docs/[A-Za-z0-9_./-]+\.md")


def main() -> int:
    violations: list[str] = []
    seen_paths: set[str] = set()
    for root_name in SCAN_ROOTS:
        root = REPO_ROOT / root_name
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix not in (
                ".py", ".ts", ".tsx", ".yml", ".yaml", ".sh", ".toml",
            ):
                continue
            rel = path.relative_to(REPO_ROOT)
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for match in DOC_PATH_RE.finditer(text):
                referenced = match.group(0)
                seen_paths.add(referenced)
                if not (REPO_ROOT / referenced).is_file():
                    violations.append(f"{rel}: references missing {referenced}")
    if violations:
        print("Referenced-doc violations found:")
        for v in violations:
            print(f"  {v}")
        return 1
    print(f"Referenced-doc guard: clean ({len(seen_paths)} distinct docs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
