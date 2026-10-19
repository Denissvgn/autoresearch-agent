"""The prompt-evaluation domain: pinned data, a controlled real scorer.

Verification covers the live controlled-scorer run through a local
endpoint, deterministic endpoint fixtures, failure with no simulator
fallback, data tampering, and continuation with nondefault settings.
Offline endpoint fixtures are separate evidence — never a live
substitute.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from src.core.prompt_scorer import (
    DATASET_ROLE_HOLDOUT,
    DATASET_ROLE_TRAIN,
    SCORE_REQUEST_SCHEMA,
    SCORE_RESULT_SCHEMA,
    ControlledLocalScorer,
    DatasetTampered,
    OfflineDemoScorer,
    PinnedDataset,
    ScorerClient,
    ScorerIdentity,
    ScorerUnavailable,
    bind_promotion_to_candidate,
    build_score_request,
    pin_dataset,
    record_scorer_usage,
    scorer_pin,
    verify_dataset,
)
from src.core.significance import qualification_status
from src.core.state_store import SQLiteStateStore

TRAIN_EXAMPLES = [
    {"input": "greet alice", "expected": "hello alice"},
    {"input": "greet bob", "expected": "hello bob"},
]
HOLDOUT_EXAMPLES = [
    {"input": "summarize logs", "expected": "logs summarized"},
    {"input": "count rows", "expected": "3 rows"},
    {"input": "name the color", "expected": "blue"},
]


@pytest.fixture
def datasets():
    train = pin_dataset(
        role=DATASET_ROLE_TRAIN, dataset_id="train-v1", examples=TRAIN_EXAMPLES
    )
    holdout = pin_dataset(
        role=DATASET_ROLE_HOLDOUT,
        dataset_id="holdout-v1",
        examples=HOLDOUT_EXAMPLES,
    )
    return train, holdout


def test_pinned_datasets_and_scorer_identity(datasets):
    train, holdout = datasets
    assert train.role == "train"
    assert holdout.role == "holdout"
    assert train.digest != holdout.digest
    assert len(holdout.digest) == 64
    # the declared request/result schemas are stable product contracts
    assert set(SCORE_REQUEST_SCHEMA) == {
        "candidate_id",
        "dataset_id",
        "dataset_role",
        "outputs",
    }
    assert set(SCORE_RESULT_SCHEMA) == {
        "candidate_id",
        "dataset_id",
        "dataset_role",
        "score",
        "per_example",
        "scorer",
        "evidence",
        "usage",
    }
    identity = ScorerIdentity(
        name="controlled-local-scorer",
        version="1.0.0",
        endpoint="http://127.0.0.1:9",
    )
    assert identity.contract_version == "prompt-scorer.v1"


def test_controlled_scorer_evaluates_real_outputs(datasets):
    train, holdout = datasets
    scorer = ControlledLocalScorer()
    scorer.register_dataset(holdout)
    request = build_score_request(
        candidate_id="cand-1",
        dataset=holdout,
        outputs=[
            {"input": "summarize logs", "output": "LOGS Summarized"},
            {"input": "count rows", "output": "4 rows"},
            {"input": "name the color", "output": "blue"},
        ],
    )
    result = scorer.score(request)
    # real outputs against pinned held-out examples: 2 of 3 match
    assert result["score"] == pytest.approx(2 / 3)
    assert result["dataset_role"] == "holdout"
    assert result["evidence"] == "measured"
    assert [e["match"] for e in result["per_example"]] == [True, False, True]
    assert result["usage"] == {"requests": 1, "examples_scored": 3}


def test_live_local_endpoint_run(datasets):
    """The controlled scorer behind a real local HTTP endpoint."""
    from fastapi import FastAPI

    train, holdout = datasets
    scorer = ControlledLocalScorer(
        name="controlled-local-scorer",
        version="1.0.0",
        endpoint="http://127.0.0.1:0/score",
    )
    scorer.register_dataset(holdout)

    app = FastAPI()

    @app.post("/score")
    async def score(request: dict):
        return scorer.score(request)

    async def _run():
        transport = httpx.ASGITransport(app=app)
        client = httpx.AsyncClient(
            base_url="http://test", transport=transport, timeout=10.0
        )
        request = build_score_request(
            candidate_id="cand-live",
            dataset=holdout,
            outputs=[
                {"input": "summarize logs", "output": "logs summarized"},
                {"input": "count rows", "output": "3 rows"},
                {"input": "name the color", "output": "red"},
            ],
        )
        response = await client.post("/score", json=request)
        await client.aclose()
        return response

    response = asyncio.run(_run())
    assert response.status_code == 200
    result = response.json()
    assert result["score"] == pytest.approx(2 / 3)
    assert result["scorer"]["version"] == "1.0.0"
    assert result["evidence"] == "measured"


def test_failure_never_invokes_a_simulator(datasets):
    train, holdout = datasets

    class FailingScorer:
        def score(self, request):
            raise RuntimeError("endpoint unreachable")

    demo = OfflineDemoScorer()
    demo_called = []

    class DemoTrap:
        def score(self, request):
            demo_called.append(request)
            return demo.score(request)

    client = ScorerClient(scorer=FailingScorer())
    with pytest.raises(ScorerUnavailable):
        client.score(
            build_score_request(
                candidate_id="cand", dataset=holdout, outputs=[]
            )
        )
    # the demo path was never touched
    assert demo_called == []
    # and the client refuses to even accept a fallback
    with pytest.raises(ValueError):
        ScorerClient(scorer=FailingScorer(), fallback=DemoTrap())


def test_data_tampering_is_refused(datasets):
    train, holdout = datasets
    # a candidate mutating a held-out example is detected by the digest
    mutated_examples = list(holdout.examples)
    mutated_examples[0] = {
        "input": mutated_examples[0]["input"],
        "expected": "rigged answer",
    }
    tampered = PinnedDataset(
        role=holdout.role,
        dataset_id=holdout.dataset_id,
        digest=holdout.digest,
        examples=tuple(mutated_examples),
    )
    with pytest.raises(DatasetTampered):
        verify_dataset(tampered)
    scorer = ControlledLocalScorer()
    scorer.datasets[holdout.dataset_id] = tampered
    with pytest.raises(DatasetTampered):
        scorer.score(
            build_score_request(
                candidate_id="cand", dataset=holdout, outputs=[]
            )
        )


def test_continuation_preserves_the_pinned_configuration(datasets):
    from src.core.run_restore import assess_recovery
    from src.core.run_spec import build_run_spec, verify_run_spec

    train, holdout = datasets
    identity = ScorerIdentity(
        name="controlled-local-scorer",
        version="2.1.0",
        endpoint="http://scorer.local:8080/v1",
    )
    pin = scorer_pin(identity=identity, datasets=[train, holdout])
    spec = build_run_spec(
        skill_params={"scorer_url": "http://scorer.local:8080/v1"},
        param_schema=None,
        skill_id="prompt-engineering",
        skill_version="1.0.0",
        skill_dir=None,
        objective_policy={"metric": "score", "direction": "maximize"},
        policy={"approval_required": False},
        effective_config={"max_iterations": 4, "max_budget_usd": 9.25},
        harness=pin,
    )
    assert verify_run_spec(spec) is True
    assert spec["harness"]["scorer"]["endpoint"] == (
        "http://scorer.local:8080/v1"
    )
    assert [d["digest"] for d in spec["harness"]["datasets"]] == [
        train.digest,
        holdout.digest,
    ]
    # continuation restores the pinned configuration exactly (nondefault)
    report = assess_recovery(
        kind="continuation",
        session_id="res-scorer",
        run_spec=spec,
    )
    assert report.ready is True, report.as_dict()
    assert report.contract["harness"]["scorer"]["version"] == "2.1.0"
    assert report.contract["effective_config"]["max_budget_usd"] == 9.25


def test_optimization_and_qualification_evidence_are_distinguishable(datasets):
    train, holdout = datasets
    scorer = ControlledLocalScorer()
    scorer.register_dataset(train)
    scorer.register_dataset(holdout)
    train_result = scorer.score(
        build_score_request(
            candidate_id="cand",
            dataset=train,
            outputs=[
                {"input": e["input"], "output": e["expected"]}
                for e in train.examples
            ],
        )
    )
    assert train_result["dataset_role"] == "train"

    class Cfg:
        min_samples = 2
        planned_repeats = 2
        holdout_required = True

    # train evidence alone never satisfies holdout-required qualification
    status = qualification_status(
        candidate=[0.5, 0.6],
        config=Cfg(),
        verdict="significant",
        holdout_evidence=False,
    )
    assert status["status"] == "missing_holdout"
    holdout_result = scorer.score(
        build_score_request(
            candidate_id="cand",
            dataset=holdout,
            outputs=[
                {"input": e["input"], "output": e["expected"]}
                for e in holdout.examples
            ],
        )
    )
    assert holdout_result["dataset_role"] == "holdout"
    qualified = qualification_status(
        candidate=[0.5, 0.6],
        config=Cfg(),
        verdict="significant",
        holdout_evidence=holdout_result["evidence"] == "measured",
    )
    assert qualified["status"] == "qualified"


def test_candidate_bound_promotion_fixture(datasets):
    train, holdout = datasets
    scorer = ControlledLocalScorer()
    scorer.register_dataset(holdout)
    holdout_result = scorer.score(
        build_score_request(
            candidate_id="cand-a",
            dataset=holdout,
            outputs=[
                {"input": e["input"], "output": e["expected"]}
                for e in holdout.examples
            ],
        )
    )
    binding = bind_promotion_to_candidate(
        candidate_digest="a" * 64, holdout_result=holdout_result
    )
    assert binding["candidate_digest"] == "a" * 64
    assert binding["holdout_score"] == 1.0
    # optimization evidence and demo evidence never qualify a promotion
    with pytest.raises(ValueError):
        bind_promotion_to_candidate(
            candidate_digest="a" * 64,
            holdout_result=dict(holdout_result, dataset_role="train"),
        )
    with pytest.raises(ValueError):
        bind_promotion_to_candidate(
            candidate_digest="a" * 64,
            holdout_result=dict(holdout_result, evidence="demo"),
        )


def test_scorer_usage_is_accounted(tmp_path, datasets):
    train, holdout = datasets

    async def _run():
        store = SQLiteStateStore(str(tmp_path / "state.db"))
        await store.initialize()
        try:
            scorer = ControlledLocalScorer()
            scorer.register_dataset(holdout)
            result = scorer.score(
                build_score_request(
                    candidate_id="cand-usage",
                    dataset=holdout,
                    outputs=[],
                )
            )
            recorded = await record_scorer_usage(store, result=result)
            assert recorded is True
            events = await store.get_usage_events("cand-usage")
            assert len(events) == 1
            assert events[0]["role"] == "evaluator"
            assert events[0]["provider"] == "controlled-local-scorer"
        finally:
            await store.close()

    asyncio.run(_run())


def test_offline_demo_mode_is_separate_evidence(datasets):
    train, holdout = datasets
    demo = OfflineDemoScorer()
    assert demo.mode == "demo"
    result = demo.score(
        build_score_request(candidate_id="cand", dataset=holdout, outputs=[])
    )
    assert result["evidence"] == "demo"
    assert result["scorer"]["endpoint"] == "demo://offline"
    # demo evidence is refused by the measured-only client
    client = ScorerClient(scorer=demo)
    with pytest.raises(ScorerUnavailable):
        client.score(
            build_score_request(
                candidate_id="cand", dataset=holdout, outputs=[]
            )
        )