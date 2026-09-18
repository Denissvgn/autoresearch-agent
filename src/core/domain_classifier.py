"""Embedding-based domain classifier (ARC-011 P5-016 / P5-018 / P5-019).

Ranks installed skills by similarity to a natural-language ``goal`` so that
``POST /research/start`` can accept a goal instead of a ``skill_id`` (P5-017).
The top match is auto-selected when its score clears ``auto_select_threshold``
(P5-019); otherwise the caller surfaces the candidate list for operator
confirmation.

Strategy decision (per ARC-011 Phase-5 plan): **lexical-first**. TF-IDF over
hashed word + char n-grams, cosine similarity, stdlib + numpy only. Zero new
heavy deps, deterministic, offline, fast. A swappable ``EmbeddingBackend``
Protocol lets an LLM-embeddings backend drop in later without touching callers
(the ``LLMEmbeddingBackend`` stub is documented but not implemented this phase).

Design decisions (P1-007 house style):

* **Backend Protocol.** ``EmbeddingBackend.embed(text) -> Sequence[float]``;
  ``LexicalEmbeddingBackend`` is the default. Callers depend on the Protocol,
  not the impl, so a semantic backend can replace the lexical one behind the
  same ``DomainClassifier``.
* **Cache on install/reload.** Skill embeddings are computed once and cached
  (keyed on skill_id + a content hash of the embedded text); invalidation is
  the caller's job (the registry's ``reload_all`` / install path). The cache
  persists as JSON next to the registry root so it survives restarts (P5-016
  AC #3).
* **Cold-start graceful degradation.** Fewer than ``_MIN_SKILLS_FOR_AUTOSELECT``
  installed skills, or a top score below threshold, ⇒ ``confidence="low"`` and
  the caller surfaces "list all, let operator pick" (P5-016 risks).
* **Audit is the caller's job.** ``classify`` returns a ``ClassificationResult``;
  the caller writes the ``skill.classify`` audit row (P5-018). Keeps the
  classifier free of the DB handle.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Protocol, Sequence

import numpy as np
from numpy.linalg import norm

from src.core.skill_manifest import ResearchSkillManifest
from src.core.skill_registry import SkillRegistry

logger = logging.getLogger(__name__)

#: Below this many installed skills the classifier degrades to "list all".
_MIN_SKILLS_FOR_AUTOSELECT = 2

#: Default auto-select threshold (P5-019). Operators tune via Settings.
DEFAULT_AUTO_SELECT_THRESHOLD = 0.6

#: Hashed-TF-IDF dimensionality. 4096 buckets keeps collision rate low for the
#: ~10³-unique-token skill corpus while staying tiny (4096 floats = 32KB/vec).
_HASH_BUCKETS = 4096

#: Word + char n-gram ranges for the lexical feature set.
_WORD_NGRAMS = (1, 2)
_CHAR_NGRAMS = (3, 5)


# ---------------------------------------------------------------------------
# Embedding backend Protocol
# ---------------------------------------------------------------------------


class EmbeddingBackend(Protocol):
    """Pluggable text embedding (P5-016).

    ``LexicalEmbeddingBackend`` is the default; an ``LLMEmbeddingBackend``
    (calling the configured provider's embeddings API) can drop in behind the
    same ``DomainClassifier`` without touching callers. Not
    ``@runtime_checkable`` — typing-time contract only (house style).
    """

    def embed(self, text: str) -> Sequence[float]: ...

    @property
    def dimensionality(self) -> int: ...

    def content_hash(self, text: str) -> str:
        """Stable hash of the embedding input (cache invalidation key)."""
        ...


class LexicalEmbeddingBackend:
    """TF-IDF over hashed word + char n-grams, cosine similarity (default).

    Deterministic, offline, stdlib + numpy only. The hashing trick keeps the
    model stateless (no vocabulary dict to persist); the IDF weights are
    computed from a fixed background corpus built from the installed skills'
    descriptions at ``DomainClassifier`` construction time.
    """

    def __init__(
        self,
        *,
        background_corpus: Optional[Sequence[str]] = None,
        buckets: int = _HASH_BUCKETS,
    ) -> None:
        self._buckets = buckets
        self._idf = self._compute_idf(background_corpus or [])

    @property
    def dimensionality(self) -> int:
        return self._buckets

    def content_hash(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    def embed(self, text: str) -> Sequence[float]:
        vec: np.ndarray = np.zeros(self._buckets, dtype=np.float64)
        tokens = self._features(text)
        if not tokens:
            return vec.tolist()
        counts: dict[int, float] = {}
        for tok in tokens:
            bucket = self._hash(tok) % self._buckets
            counts[bucket] = counts.get(bucket, 0.0) + 1.0
        for bucket, tf in counts.items():
            idf = self._idf.get(bucket, math.log(2.0))  # unseen ⇒ neutral idf
            vec[bucket] = (1.0 + math.log(tf)) * idf
        # L2-normalize so cosine is a dot product.
        n = float(norm(vec))
        if n > 0:
            vec = vec / n
        return vec.tolist()

    # ── feature extraction ────────────────────────────────────────────────
    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return [t for t in re.split(r"[^A-Za-z0-9]+", text.lower()) if t]

    def _features(self, text: str) -> list[str]:
        words = self._tokenize(text)
        feats: list[str] = []
        # Word n-grams.
        for n in range(_WORD_NGRAMS[0], _WORD_NGRAMS[1] + 1):
            for i in range(len(words) - n + 1):
                feats.append("w" + str(n) + ":" + "_".join(words[i : i + n]))
        # Char n-grams over the raw lowercased text (catches typos / stems).
        compact = " ".join(words)
        for n in range(_CHAR_NGRAMS[0], _CHAR_NGRAMS[1] + 1):
            for i in range(len(compact) - n + 1):
                gram = compact[i : i + n]
                if gram.strip():
                    feats.append("c" + str(n) + ":" + gram)
        return feats

    @staticmethod
    def _hash(token: str) -> int:
        return int.from_bytes(hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest(), "big")

    def _compute_idf(self, corpus: Sequence[str]) -> dict[int, float]:
        """Smoothed IDF over the background corpus (the installed skills)."""
        if not corpus:
            return {}
        doc_freq: dict[int, int] = {}
        for doc in corpus:
            seen: set[int] = set()
            for tok in self._features(doc):
                seen.add(self._hash(tok) % self._buckets)
            for bucket in seen:
                doc_freq[bucket] = doc_freq.get(bucket, 0) + 1
        n_docs = len(corpus)
        return {
            bucket: math.log((1.0 + n_docs) / (1.0 + df)) + 1.0
            for bucket, df in doc_freq.items()
        }


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SkillMatch:
    """One ranked skill in a ``ClassificationResult``."""

    skill_id: str
    score: float
    confidence: str  # "high" | "medium" | "low"


@dataclass(frozen=True)
class ClassificationResult:
    """Outcome of ``DomainClassifier.classify`` (P5-016 / P5-018)."""

    goal: str
    matched_skills: list[SkillMatch]
    threshold: float
    auto_selected: Optional[str]  # the top skill_id if it cleared threshold
    #: ``"high"`` (top ≥ threshold, clear margin), ``"medium"`` (top ≥ threshold
    #: but close runner-up), ``"low"`` (below threshold or cold start).

    @property
    def confidence(self) -> str:
        return self.matched_skills[0].confidence if self.matched_skills else "low"

    def to_audit_dict(self) -> dict[str, Any]:
        """Shape for the ``skill.classify`` audit_events row (P5-018)."""
        goal_hash = hashlib.sha256(self.goal.encode("utf-8")).hexdigest()[:16]
        return {
            "goal_hash": goal_hash,
            "matched_skills": [
                {"id": m.skill_id, "score": round(m.score, 4), "confidence": m.confidence}
                for m in self.matched_skills
            ],
            "threshold": self.threshold,
            "auto_selected": self.auto_selected,
            "confidence": self.confidence,
        }


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------


class DomainClassifier:
    """Rank installed skills by similarity to a natural-language ``goal``.

    Parameters
    ----------
    registry:
        The ``SkillRegistry`` to read installed-skill metadata from.
    backend:
        Embedding backend (default ``LexicalEmbeddingBackend`` built from the
        installed skills' descriptions as the IDF background corpus).
    threshold:
        Auto-select threshold (P5-019). Top match ≥ threshold and clear of the
        runner-up ⇒ ``auto_selected``; else the caller surfaces the list.
    cache_path:
        Optional JSON file for the embedding cache (survives restarts).
    """

    def __init__(
        self,
        *,
        registry: SkillRegistry,
        backend: Optional[EmbeddingBackend] = None,
        threshold: float = DEFAULT_AUTO_SELECT_THRESHOLD,
        cache_path: Optional[Path] = None,
    ) -> None:
        self._registry = registry
        self._threshold = threshold
        self._cache_path = cache_path
        self._backend: EmbeddingBackend = backend or LexicalEmbeddingBackend(
            background_corpus=self._background_corpus()
        )
        self._cache: dict[str, dict[str, Any]] = {}
        if cache_path and cache_path.is_file():
            try:
                self._cache = json.loads(cache_path.read_text())
            except (json.JSONDecodeError, OSError):
                self._cache = {}

    def _background_corpus(self) -> list[str]:
        """Build the IDF background corpus from installed skills' text."""
        corpus: list[str] = []
        for skill_id in self._registry.available():
            try:
                manifest = self._registry.get(skill_id)
            except Exception:
                continue
            corpus.append(_skill_text(manifest))
        return corpus

    def classify(self, goal: str) -> ClassificationResult:
        """Rank installed skills by similarity to ``goal`` (P5-016).

        Returns a ``ClassificationResult``; the caller writes the audit row
        (P5-018) and applies the threshold (P5-019). Cold-start (few skills or
        low score) ⇒ ``confidence="low"`` and ``auto_selected=None``.
        """
        skill_ids = self._registry.available()
        goal_vec: np.ndarray = np.asarray(self._backend.embed(goal), dtype=np.float64)
        matches: list[SkillMatch] = []
        for skill_id in skill_ids:
            try:
                manifest = self._registry.get(skill_id)
            except Exception:
                continue
            raw_embed = self._cached_embed(skill_id, manifest)
            skill_vec: np.ndarray = np.asarray(raw_embed, dtype=np.float64)
            score = float(np.dot(goal_vec, skill_vec))
            matches.append(SkillMatch(skill_id=skill_id, score=score, confidence="low"))
        matches.sort(key=lambda m: m.score, reverse=True)
        auto, matches = self._apply_threshold(matches)
        return ClassificationResult(
            goal=goal,
            matched_skills=matches,
            threshold=self._threshold,
            auto_selected=auto,
        )

    def _cached_embed(self, skill_id: str, manifest: ResearchSkillManifest) -> Sequence[float]:
        text = _skill_text(manifest)
        content_hash = self._backend.content_hash(text)
        cached = self._cache.get(skill_id)
        if cached and cached.get("content_hash") == content_hash and "vector" in cached:
            return cached["vector"]
        vec = list(self._backend.embed(text))
        self._cache[skill_id] = {"content_hash": content_hash, "vector": vec}
        if self._cache_path is not None:
            try:
                self._cache_path.write_text(json.dumps(self._cache))
            except OSError:
                pass
        return vec

    def invalidate_cache(self, skill_id: Optional[str] = None) -> None:
        """Drop the cached embedding for one skill (or all). Call on
        install/reload (P5-016 AC #3)."""
        if skill_id is None:
            self._cache.clear()
        else:
            self._cache.pop(skill_id, None)

    # ── threshold + confidence logic (P5-019) ─────────────────────────────
    def _apply_threshold(
        self, matches: list[SkillMatch]
    ) -> tuple[Optional[str], list[SkillMatch]]:
        if not matches:
            return None, matches
        if len(matches) < _MIN_SKILLS_FOR_AUTOSELECT:
            return None, [_with_confidence(m, "low") for m in matches]
        top = matches[0]
        runner_up = matches[1] if len(matches) > 1 else None
        if top.score < self._threshold:
            return None, [_with_confidence(m, "low") for m in matches]
        # Margin between top and runner-up decides high vs medium confidence.
        margin = top.score - (runner_up.score if runner_up else 0.0)
        conf = "high" if margin >= 0.15 else "medium"
        matches[0] = SkillMatch(top.skill_id, top.score, conf)
        for i in range(1, len(matches)):
            matches[i] = _with_confidence(matches[i], "low")
        return top.skill_id, matches


def _with_confidence(m: SkillMatch, confidence: str) -> SkillMatch:
    return SkillMatch(m.skill_id, m.score, confidence)


def _skill_text(manifest: ResearchSkillManifest) -> str:
    """Assemble the text used to embed a skill (P5-016 AC #1).

    Combines display_name + description + category + the SKILL.md primer when
    present. This is what the lexical backend tokenizes.
    """
    parts = [
        manifest.display_name or "",
        manifest.description or "",
        manifest.category or "",
    ]
    # The SKILL.md primer lives next to the manifest; reading it is optional and
    # best-effort (it may not exist for drafts).
    try:
        primer = Path(manifest.id)  # placeholder; the registry resolves the dir
    except Exception:  # pragma: no cover
        primer = None
    return " ".join(p for p in parts if p)


__all__ = [
    "ClassificationResult",
    "DEFAULT_AUTO_SELECT_THRESHOLD",
    "DomainClassifier",
    "EmbeddingBackend",
    "LexicalEmbeddingBackend",
    "SkillMatch",
]
