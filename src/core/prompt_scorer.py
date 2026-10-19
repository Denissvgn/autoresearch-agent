"""The prompt-evaluation domain: a controlled real scorer, pinned data.

The domain qualifies prompt evaluation with a declared scorer identity and
version, pinned test/holdout datasets, explicit request/result schemas,
and honest failure behavior: a scorer failure is a hard refusal and never
silently invokes a simulator. Optimization evidence (train split) and
held-out qualification evidence (holdout split) are distinguishable in
every result, held-out data is digest-protected against candidate
mutation, scorer usage is accounted in the usage ledger, and the fixed
endpoint/data configuration is pinned into the run spec so continuation
reproduces it exactly. The offline demo mode exists and is labeled as
demo — it is never qualification evidence.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping, Optional, Sequence

SCORER_CONTRACT_VERSION = "prompt-scorer.v1"

DATASET_ROLE_TRAIN = "train"
DATASET_ROLE_HOLDOUT = "holdout"


class ScorerUnavailable(Exception):
    """The declared scorer could not be reached or refused the request.

    This is a hard failure: a simulator is never invoked silently.
    """


class DatasetTampered(Exception):
    """A pinned dataset no longer matches its digest."""


@dataclass(frozen=True)
class ScorerIdentity:
    """Who scores the outputs, and at which pinned endpoint."""

    name: str
    version: str
    endpoint: str
    contract_version: str = SCORER_CONTRACT_VERSION

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PinnedDataset:
    """A digest-pinned evaluation split (train or holdout)."""

    role: str
    dataset_id: str
    digest: str
    examples: tuple[Mapping[str, str], ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "dataset_id": self.dataset_id,
            "digest": self.digest,
            "n_examples": len(self.examples),
        }


def pin_dataset(
    *, role: str, dataset_id: str, examples: Sequence[Mapping[str, str]]
) -> PinnedDataset:
    """Pin a split: every example carries nonempty input/expected strings."""
    if role not in (DATASET_ROLE_TRAIN, DATASET_ROLE_HOLDOUT):
        raise ValueError(f"unknown dataset role {role!r}")
    clean = []
    for example in examples:
        input_text = str(example.get("input") or "")
        expected = str(example.get("expected") or "")
        if not input_text or not expected:
            raise ValueError(
                "dataset examples require nonempty input and expected strings"
            )
        clean.append({"input": input_text, "expected": expected})
    digest = hashlib.sha256(
        json.dumps(clean, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return PinnedDataset(
        role=role,
        dataset_id=dataset_id,
        digest=digest,
        examples=tuple(clean),
    )


def verify_dataset(dataset: PinnedDataset) -> PinnedDataset:
    """Re-hash the split: candidate mutation of held-out data is refused."""
    recomputed = pin_dataset(
        role=dataset.role,
        dataset_id=dataset.dataset_id,
        examples=list(dataset.examples),
    )
    if recomputed.digest != dataset.digest:
        raise DatasetTampered(
            f"dataset {dataset.dataset_id!r} no longer matches its digest"
        )
    return dataset


# -- request/result schemas (the declared contract) ----------------------

SCORE_REQUEST_SCHEMA = {
    "candidate_id": "string",
    "dataset_id": "string",
    "dataset_role": "train|holdout",
    "outputs": "array of {input, output} (real model outputs)",
}

SCORE_RESULT_SCHEMA = {
    "candidate_id": "string",
    "dataset_id": "string",
    "dataset_role": "train|holdout",
    "score": "float in [0, 1]",
    "per_example": "array of {input, expected, output, match}",
    "scorer": "ScorerIdentity as dict",
    "evidence": "measured|demo",
    "usage": {"requests": "int", "examples_scored": "int"},
}


def build_score_request(
    *,
    candidate_id: str,
    dataset: PinnedDataset,
    outputs: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    """The declared request shape: real outputs keyed to dataset inputs."""
    return {
        "candidate_id": candidate_id,
        "dataset_id": dataset.dataset_id,
        "dataset_role": dataset.role,
        "outputs": [
            {"input": str(item.get("input") or ""),
             "output": str(item.get("output") or "")}
            for item in outputs
        ],
    }


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _score_outputs(
    dataset: PinnedDataset, outputs: Sequence[Mapping[str, str]]
) -> tuple[float, list[dict[str, Any]]]:
    by_input = {
        str(item.get("input") or ""): str(item.get("output") or "")
        for item in outputs
    }
    per_example = []
    matches = 0
    for example in dataset.examples:
        produced = by_input.get(example["input"], "")
        match = _normalize(produced) == _normalize(example["expected"])
        matches += 1 if match else 0
        per_example.append(
            {
                "input": example["input"],
                "expected": example["expected"],
                "output": produced,
                "match": match,
            }
        )
    score = matches / len(dataset.examples) if dataset.examples else 0.0
    return score, per_example


class ControlledLocalScorer:
    """The declared real scorer: outputs scored against pinned examples.

    This is the controlled scoring endpoint's logic. It evaluates real
    model outputs; it never invents scores and never falls back to a
    simulator — an unreachable endpoint is ``ScorerUnavailable``.
    """

    def __init__(
        self,
        *,
        name: str = "controlled-local-scorer",
        version: str = "1.0.0",
        endpoint: str = "local://controlled-scorer",
    ) -> None:
        self._identity = ScorerIdentity(
            name=name, version=version, endpoint=endpoint
        )
        self.datasets: dict[str, PinnedDataset] = {}
        self.calls = 0

    def identity(self) -> ScorerIdentity:
        return self._identity

    def register_dataset(self, dataset: PinnedDataset) -> None:
        verify_dataset(dataset)
        self.datasets[dataset.dataset_id] = dataset

    def score(self, request: Mapping[str, Any]) -> dict[str, Any]:
        dataset = self.datasets.get(str(request.get("dataset_id") or ""))
        if dataset is None:
            raise ScorerUnavailable(
                f"unknown dataset {request.get('dataset_id')!r}"
            )
        verify_dataset(dataset)
        self.calls += 1
        score, per_example = _score_outputs(
            dataset, request.get("outputs") or []
        )
        return {
            "candidate_id": request.get("candidate_id"),
            "dataset_id": dataset.dataset_id,
            "dataset_role": dataset.role,
            "score": score,
            "per_example": per_example,
            "scorer": self._identity.as_dict(),
            "evidence": "measured",
            "usage": {
                "requests": 1,
                "examples_scored": len(per_example),
            },
        }


class ScorerClient:
    """The scorer client: failures are hard refusals, never fallbacks."""

    def __init__(self, *, scorer: Any, fallback: Any = None) -> None:
        if fallback is not None:
            raise ValueError(
                "a scorer client takes no fallback: failures are refusals"
            )
        self._scorer = scorer

    def score(self, request: Mapping[str, Any]) -> dict[str, Any]:
        try:
            result = self._scorer.score(request)
        except ScorerUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 — any failure is a refusal
            raise ScorerUnavailable(
                f"declared scorer failed: {exc}"
            ) from None
        if result.get("evidence") != "measured":
            raise ScorerUnavailable(
                "declared scorer returned non-measured evidence"
            )
        return result


class OfflineDemoScorer:
    """The offline demo mode: clearly labeled, never qualification evidence."""

    mode = "demo"

    def __init__(self) -> None:
        self._identity = ScorerIdentity(
            name="offline-demo-scorer",
            version="demo",
            endpoint="demo://offline",
        )

    def score(self, request: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "candidate_id": request.get("candidate_id"),
            "dataset_id": request.get("dataset_id"),
            "dataset_role": request.get("dataset_role"),
            "score": 1.0,
            "per_example": [],
            "scorer": self._identity.as_dict(),
            "evidence": "demo",
            "usage": {"requests": 1, "examples_scored": 0},
        }


async def record_scorer_usage(
    store: Any, *, result: Mapping[str, Any]
) -> bool:
    """Account scorer usage in the usage ledger (evaluator role)."""
    from src.core.llm_provider import Usage
    from src.core.usage_ledger import UsageEvent

    usage = result.get("usage") or {}
    scorer = result.get("scorer") or {}
    event = UsageEvent(
        event_key=(
            f"scorer:{result.get('candidate_id')}:"
            f"{result.get('dataset_id')}:{result.get('dataset_role')}"
        ),
        research_id=str(result.get("candidate_id") or ""),
        role="evaluator",
        provider=str(scorer.get("name") or "scorer"),
        model=str(scorer.get("version") or "unknown"),
        usage=Usage(input_tokens=0, output_tokens=0),
        cost_status="unavailable",
        cost_usd=None,
        pricing_basis={
            "version": SCORER_CONTRACT_VERSION,
            "endpoint": scorer.get("endpoint"),
            "requests": int(usage.get("requests") or 0),
            "examples_scored": int(usage.get("examples_scored") or 0),
        },
    )
    return await store.record_usage_event(event.as_row())


def scorer_pin(
    *, identity: ScorerIdentity, datasets: Iterable[PinnedDataset]
) -> dict[str, Any]:
    """The fixed endpoint/data configuration for the run spec.

    Pinned with the spec so continuation reproduces the same scorer and
    the same splits exactly.
    """
    return {
        "scorer": identity.as_dict(),
        "datasets": [dataset.as_dict() for dataset in datasets],
        "contract_version": SCORER_CONTRACT_VERSION,
    }


def bind_promotion_to_candidate(
    *, candidate_digest: str, holdout_result: Mapping[str, Any]
) -> dict[str, Any]:
    """Candidate-bound promotion: evidence travels with its candidate."""
    if holdout_result.get("dataset_role") != DATASET_ROLE_HOLDOUT:
        raise ValueError(
            "promotion requires held-out qualification evidence"
        )
    if holdout_result.get("evidence") != "measured":
        raise ValueError("demo evidence never qualifies a promotion")
    return {
        "candidate_digest": candidate_digest,
        "holdout_dataset_id": holdout_result.get("dataset_id"),
        "holdout_score": holdout_result.get("score"),
        "scorer": holdout_result.get("scorer"),
    }
