"""ARC-011 X-002 parity suite.

Discovers every ``*.json`` under ``tests/parity/<category>/`` and asserts that
invoking the named source function reproduces the recorded ``expected`` output
(after normalization). Selectable via ``pytest -m parity``.

Run:  poetry run pytest tests/parity -q      # or  pytest -m parity
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from _engine import (  # type: ignore[import-not-found]  # sibling, on sys.path in prepend mode
    HOST_CONFIGS_TOKEN,
    WORKSPACE_TOKEN,
    discover_cases,
    invoke,
    load_case,
    normalize,
)

PARITY_DIR = Path(__file__).parent
CASES = discover_cases(PARITY_DIR)


@pytest.mark.parity
@pytest.mark.parametrize(
    "case_id, case_path",
    CASES,
    ids=[cid for cid, _ in CASES],
)
def test_parity_fixture(case_id: str, case_path: Path, tmp_path: Path) -> None:
    case = load_case(case_path)

    workspace = tmp_path / "ws"
    host_configs = tmp_path / "host_configs"
    workspace.mkdir()
    host_configs.mkdir()

    result = invoke(case, workspace, host_configs, tmp_path)
    mapping = {
        WORKSPACE_TOKEN: str(workspace),
        HOST_CONFIGS_TOKEN: str(host_configs),
    }
    actual = normalize(result, mapping)

    expected = case["expected"]
    if actual != expected:
        raise AssertionError(
            f"parity drift for {case_id}\n"
            f"--- expected ---\n{json.dumps(expected, indent=2, sort_keys=True)}\n"
            f"--- actual ---\n{json.dumps(actual, indent=2, sort_keys=True)}"
        )
