from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, NamedTuple

import pytest

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FIXTURES_DIR = Path(__file__).parent / "fixtures"

from src.core.results_store import ResultsStore


@pytest.fixture(autouse=True)
async def close_initialized_results_stores(
    monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest,
):
    """Close long-lived SQLite connections created by tests.

    Skipped for ``@pytest.mark.postgres`` tests: those create their own
    Postgres pools (not ResultsStore instances) and manage their own lifecycle
    via the ``pg_store`` fixture; the monkeypatch on ResultsStore.initialize
    interacts badly with asyncpg-pool teardown across the session.
    """

    if "postgres" in request.keywords or "distributed" in request.keywords:
        yield
        return
    stores: list[ResultsStore] = []
    original_initialize = ResultsStore.initialize

    async def tracked_initialize(self: ResultsStore) -> None:
        await original_initialize(self)
        stores.append(self)

    monkeypatch.setattr(ResultsStore, "initialize", tracked_initialize)
    yield
    for store in reversed(stores):
        await store.close()


# --- ARC-011 Phase 6: skip Postgres-dependent tests when no DSN is set -----
def _phase6_postgres_dsn() -> str | None:
    raw = os.getenv("AUTORESEARCH_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not raw:
        return None
    low = raw.lower()
    if not (
        low.startswith("postgresql://") or low.startswith("postgresql+asyncpg://")
    ):
        return None
    return raw.replace("postgresql+asyncpg://", "postgresql://")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip ``@pytest.mark.postgres`` / ``distributed`` tests when no Postgres DSN.

    The default CI run has no Postgres service (confirmed); a dedicated job
    (ARC-011 P6-007) wires one and runs ``-m "postgres or distributed"`` with
    the DSN set.
    """
    if _phase6_postgres_dsn() is not None:
        return
    skip = pytest.mark.skip(reason="AUTORESEARCH_DATABASE_URL unset; live Postgres required")
    for item in items:
        if "postgres" in item.keywords or "distributed" in item.keywords:
            item.add_marker(skip)


# ---------------------------------------------------------------------------
# AR-9: replay_iterations fixture
# ---------------------------------------------------------------------------


class ReplayContext(NamedTuple):
    """Result of seeding a ResultsStore from a JSON fixture file.

    Attributes:
        store:       Initialized ResultsStore backed by a tmp_path SQLite file.
        session_id:  The research session ID used for all seeded rows.
        session:     The full session dict as returned by store.get_session().
        iterations:  Full DB row dicts (all columns) for all seeded iterations,
                     ordered by iteration number.  Equivalent to
                     store.get_iterations(session_id).
        raw:         The raw parsed JSON fixture dict, for accessing extra fields
                     like ``config_snapshot_as_dict`` on individual iterations.
    """

    store: ResultsStore
    session_id: str
    session: Dict[str, Any]
    iterations: List[Dict[str, Any]]
    raw: Dict[str, Any]


@pytest.fixture
def replay_iterations(tmp_path: Path):
    """Factory fixture: seed a ResultsStore from a JSON fixture file.

    Returns an async callable that accepts an optional ``fixture_name``
    (default ``"res_a1ba6cbd520f_minimal"``) and resolves to a
    :class:`ReplayContext`.

    Usage::

        @pytest.mark.asyncio
        async def test_something(replay_iterations):
            ctx = await replay_iterations()
            # ctx.store  — ready-to-use ResultsStore
            # ctx.session_id, ctx.session, ctx.iterations

        # Different fixture file:
        async def test_other(replay_iterations):
            ctx = await replay_iterations("my_other_fixture")

    The seeded ``ResultsStore`` is automatically closed by the
    ``close_initialized_results_stores`` autouse fixture at the end of the test.

    JSON fixture format::

        {
          "session": {
            "id": "...",
            "instrument": "DOGE_USDT",
            "timeframe": "15m",
            "model_type": "direction",
            "tag": "...",
            "max_iterations": 110,
            "max_budget_usd": 50.0
          },
          "iterations": [
            {
              "iteration": 85,
              "search_phase": "baseline_capture",
              "primary_metric": 0.58,
              "metric_name": "auc",
              "all_gates_passed": true,
              "decision": "keep",
              "training_time_s": 95.2,
              "config_snapshot": "agent_strategy: BALA\\n",
              "mlflow_run_id": "run-baseline-85-ab1c",
              "description": "...",
              "metrics": { ... }
            },
            ...
          ]
        }

    Each iteration entry is written to the DB via
    ``store.add_iteration(**fields)``.  The ``metrics`` sub-object is
    JSON-serialized and stored in ``metrics_json``.  Extra keys (e.g.
    ``config_snapshot_as_dict``, ``_note``) are preserved in
    :attr:`ReplayContext.raw` but are not written to the DB.
    """

    async def _load(fixture_name: str = "res_a1ba6cbd520f_minimal") -> ReplayContext:
        fixture_path = FIXTURES_DIR / f"{fixture_name}.json"
        raw = json.loads(fixture_path.read_text())

        session_cfg = raw["session"]
        session_id = session_cfg["id"]

        store = ResultsStore(str(tmp_path / f"{fixture_name}.sqlite"))
        await store.initialize()

        await store.create_session(
            session_id=session_id,
            instrument=session_cfg["instrument"],
            timeframe=session_cfg["timeframe"],
            model_type=session_cfg["model_type"],
            tag=session_cfg["tag"],
            quick_mode=False,
            max_iterations=session_cfg["max_iterations"],
            max_budget_usd=session_cfg["max_budget_usd"],
            focus_hint=None,
            workspace_path="/ws/replay",
        )

        for it in raw["iterations"]:
            await store.add_iteration(
                research_id=session_id,
                iteration=it["iteration"],
                primary_metric=it.get("primary_metric"),
                metric_name=it.get("metric_name", "auc"),
                all_gates_passed=bool(it.get("all_gates_passed", False)),
                decision=it.get("decision", "keep"),
                description=it.get("description", ""),
                config_snapshot=it.get("config_snapshot"),
                metrics_json=json.dumps(it.get("metrics", {})),
                training_time_s=it.get("training_time_s"),
                mlflow_run_id=it.get("mlflow_run_id"),
                search_phase=it.get("search_phase"),
            )

        session = await store.get_session(session_id)
        iterations = await store.get_iterations(session_id)
        return ReplayContext(
            store=store,
            session_id=session_id,
            session=session,
            iterations=iterations,
            raw=raw,
        )

    return _load
