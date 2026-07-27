"""``PromotionTarget`` protocol + ``FilePathPromotionTarget`` implementation
(ARC-011 P1-015 / P1-016).

This module introduces the ``PromotionTarget`` protocol — the abstraction over
*where* a promoted config gets written and *how* the path is derived. It
formalizes the file-write surface that previously lived as ``@staticmethod`` /
module-level helpers on ``ConfigPromoter``:

* ``target_path``            ← ``ConfigPromoter._get_target_path``
* ``metadata_sidecar_path``  ← ``ConfigPromoter._metadata_sidecar_path``
* ``rollback_snapshot_path`` ← ``ConfigPromoter._rollback_snapshot_path``
* ``rollback_metadata_sidecar_path`` ← ``ConfigPromoter._rollback_metadata_sidecar_path``
* ``extract_strategy_market``← ``ConfigPromoter._extract_strategy_market``
* ``write`` (atomic)         ← ``ConfigPromoter._write_text_file`` /
  module-level ``_atomic_write_text``

``ConfigPromoter`` keeps its three public methods (``preview`` / ``confirm`` /
``rollback``) — the gate-evaluation logic stays there. P1-017 makes
``ConfigPromoter`` accept an injected ``PromotionTarget`` (defaulting to
``FilePathPromotionTarget()``) and delegate the file writes to it.

Scope (D5): ``PromotionEvidenceCollector`` is intentionally **outside** this
protocol — it is a separate infra-probing resolver that writes to the DB
iteration row (not the host config path), and its own docstring frames it as
feeding ``ConfigPromoter.preview`` rather than being part of the write surface.

The extraction is **behavior-identical**: every path-derivation string and the
atomic-write (tmp+fsync+``os.replace`` + directory fsync) body are unchanged.
The X-002 parity fixture ``promotion_preview/development_scope_basic.json``
bakes ``target_path: "<host_configs>/instrument_configs/DOGE_USDT_15m.yaml"``,
so the derivation must stay byte-identical. Mirrors the P1-010..012
``OutputParser`` and P1-006/007 ``StateStore`` precedents.

Design decisions baked in here:

* **Not ``@runtime_checkable``.** Typing-time contract only — mirrors
  ``LLMProvider`` / ``StateStore`` / ``OutputParser``.
* **``write`` is async.** The atomic write is dispatched via
  ``asyncio.to_thread`` (it does blocking fsync + os.replace); the protocol
  keeps it async so the caller (``ConfigPromoter``, already async) awaits it.
* **Path methods are sync.** They are pure string derivation; no I/O.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol

from src.config import settings


class PromotionTarget(Protocol):
    """Where a promoted config is written and how its path is derived
    (ARC-011 P1-015).

    A concrete target (``FilePathPromotionTarget`` in P1-016) implements this
    surface. ``ConfigPromoter`` (P1-017) is wired to accept any
    ``PromotionTarget`` and delegates the file writes to it while keeping the
    gate-evaluation logic (``preview`` / ``confirm`` / ``rollback``).
    """

    def target_path(
        self,
        *,
        model_type: str,
        instrument: str,
        timeframe: str,
        strategy: str = "BALA",
        market_type: str = "stock",
    ) -> str:
        """Derive the host config file path for a promoted config."""
        ...

    def metadata_sidecar_path(
        self,
        target_path: str,
        iteration: int,
        *,
        scope: str = "development",
    ) -> str:
        """Derive the JSON sidecar path recording this promotion's metadata."""
        ...

    def rollback_snapshot_path(
        self,
        *,
        target_path: str,
        research_id: str,
        iteration: int,
    ) -> str:
        """Derive the path of the pre-promotion YAML snapshot used for rollback."""
        ...

    def rollback_metadata_sidecar_path(
        self, target_path: str, promotion_id: int
    ) -> str:
        """Derive the JSON sidecar path recording a rollback's metadata."""
        ...

    def extract_strategy_market(self, yaml_str: str) -> tuple:
        """Extract ``(agent_strategy, trading_mode)`` from a YAML config string
        (used to derive the RL production path). Defaults ``("BALA", "stock")``."""
        ...

    async def write(self, path: str, content: str) -> None:
        """Atomically write ``content`` to ``path`` (tmp → fsync → os.replace)."""
        ...


def _atomic_write_text(path: str, content: str) -> None:
    """Sync helper: tmp+fsync+os.replace atomic write.

    Moved verbatim (P1-016) from ``config_promoter._atomic_write_text``. Phase
    3.1 hardening for config/metadata promotion durability.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=str(target.parent),
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, str(target))
        # fsync the directory entry so the rename survives a power loss
        dir_fd = os.open(str(target.parent), os.O_DIRECTORY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except BaseException:
        # Best-effort cleanup of the tmp file if the rename never happened
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        raise


class FilePathPromotionTarget:
    """Write promoted configs to the host filesystem (ARC-011 P1-016).

    The single concrete ``PromotionTarget`` today. All methods are extracted
    verbatim from the ``ConfigPromoter`` ``@staticmethod`` / module-level
    helpers; behavior is identical. Future targets (e.g. a git-ops target, an
    object-store target) will implement the same protocol.
    """

    def target_path(
        self,
        *,
        model_type: str,
        instrument: str,
        timeframe: str,
        strategy: str = "BALA",
        market_type: str = "stock",
    ) -> str:
        """Determine the host config file path for promotion.

        Moved verbatim from ``ConfigPromoter._get_target_path``. ML-67: RL
        configs include strategy + market_type in the filename.
        """
        host_configs = settings.host_configs_path
        if model_type in ("direction", "volatility"):
            return os.path.join(
                host_configs,
                "instrument_configs",
                f"{instrument}_{timeframe}.yaml",
            )
        elif model_type == "rl":
            strat = strategy.upper()
            mkt = market_type.lower()
            return os.path.join(
                host_configs,
                "rl",
                f"{instrument}_{timeframe}_{strat}_{mkt}_production.yaml",
            )
        else:
            raise ValueError(f"Unknown model type: {model_type}")

    def metadata_sidecar_path(
        self,
        target_path: str,
        iteration: int,
        *,
        scope: str = "development",
    ) -> str:
        """Moved verbatim from ``ConfigPromoter._metadata_sidecar_path``."""
        path = Path(target_path)
        return str(
            path.with_name(
                f"{path.name}.{scope}-promotion.iter-{iteration}.json"
            )
        )

    def rollback_snapshot_path(
        self,
        *,
        target_path: str,
        research_id: str,
        iteration: int,
    ) -> str:
        """Moved verbatim from ``ConfigPromoter._rollback_snapshot_path``."""
        path = Path(target_path)
        safe_research_id = "".join(
            char if char.isalnum() or char in {"-", "_"} else "_"
            for char in research_id
        )
        return str(
            path.with_name(
                f"{path.name}.development-rollback."
                f"{safe_research_id}.iter-{iteration}.yaml"
            )
        )

    def rollback_metadata_sidecar_path(
        self, target_path: str, promotion_id: int
    ) -> str:
        """Moved verbatim from ``ConfigPromoter._rollback_metadata_sidecar_path``."""
        path = Path(target_path)
        return str(
            path.with_name(
                f"{path.name}.development-rollback.promotion-{promotion_id}.json"
            )
        )

    def extract_strategy_market(self, yaml_str: str) -> tuple:
        """Extract agent_strategy and trading_mode from a YAML config string.

        Moved verbatim from ``ConfigPromoter._extract_strategy_market``. Returns
        ``(strategy, market_type)`` with defaults if not found.
        """
        try:
            import yaml as _yaml
            cfg = _yaml.safe_load(yaml_str)
            if not isinstance(cfg, dict):
                return "BALA", "stock"
            strategy = (cfg.get("agent_strategy") or "BALA").upper()
            env = cfg.get("environment") or {}
            market = (env.get("trading_mode") or cfg.get("trading_mode") or "stock").lower()
            return strategy, market
        except Exception:
            return "BALA", "stock"

    async def write(self, path: str, content: str) -> None:
        """Atomic write: tmp file → fsync → os.replace.

        Moved verbatim (P1-016) from ``ConfigPromoter._write_text_file``. Phase
        3.1: durability hardening. A crash mid-write previously could leave a
        half-written config or metadata sidecar at the target path; the
        tmp+rename pattern guarantees readers either see the old complete
        content or the new complete content. The directory is also fsync'd so
        the rename itself survives a power loss.
        """
        await asyncio.to_thread(_atomic_write_text, path, content)


class SkillRegistryPromotionTarget:
    """Promote a draft skill into the live registry (ARC-011 P5-011).

    The Phase-1 ``PromotionTarget`` protocol is a *file-write* surface for config
    promotion; skill promotion is a different shape (a directory move +
    lifecycle transition), so this target does NOT implement that protocol.
    Instead it is consumed directly by the ``POST /skills/{id}/promote/confirm``
    endpoint (P5-012), which orchestrates the move + lifecycle update + audit.

    The move is atomic per skill: ``skills/_drafts/<id>/`` → ``skills/<id>/``
    via ``shutil.move`` (a rename when on the same filesystem, else a copy
    tree). The caller wraps this in the lifecycle machine's per-skill lock and
    writes the audit row from the returned ``SkillPromotionResult``.

    Reuses the P0-020 production-approval machinery: skill → stable is a
    production-scope act (X-004 D1 — production sessions require ``stable``), so
    the API endpoint gate-keeps the approval signature before calling this.
    """

    def __init__(self, *, skills_root: Optional[Path] = None) -> None:
        from src.core.skill_registry import DEFAULT_SKILLS_ROOT, DRAFTS_SUBDIR

        self._skills_root = Path(skills_root) if skills_root is not None else DEFAULT_SKILLS_ROOT
        self._drafts_subdir = DRAFTS_SUBDIR

    def draft_path(self, skill_id: str) -> Path:
        return self._skills_root / self._drafts_subdir / skill_id

    def stable_path(self, skill_id: str) -> Path:
        return self._skills_root / skill_id

    def draft_exists(self, skill_id: str) -> bool:
        return (self.draft_path(skill_id) / "SKILL.yaml").is_file()

    def stable_exists(self, skill_id: str) -> bool:
        return (self.stable_path(skill_id) / "SKILL.yaml").is_file()

    async def promote(self, skill_id: str) -> "SkillPromotionResult":
        """Move ``skills/_drafts/<id>/`` → ``skills/<id>/`` atomically.

        Returns a ``SkillPromotionResult``; raises ``SkillPromotionError`` on
        any precondition failure (missing draft, existing stable, IO error).
        The caller handles audit + lifecycle transition.
        """
        draft = self.draft_path(skill_id)
        stable = self.stable_path(skill_id)
        if not draft.is_dir():
            raise SkillPromotionError(
                f"draft not found: {draft} (skill {skill_id!r} has no _drafts/ package)"
            )
        if stable.exists():
            raise SkillPromotionError(
                f"a skill package already exists at {stable} "
                f"(remove it before promoting draft {skill_id!r})"
            )
        import shutil

        try:
            await asyncio.to_thread(shutil.move, str(draft), str(stable))
        except OSError as exc:
            raise SkillPromotionError(
                f"failed to move {draft} → {stable}: {exc}"
            ) from exc
        return SkillPromotionResult(
            skill_id=skill_id,
            draft_path=str(draft),
            stable_path=str(stable),
        )

    async def rollback(self, skill_id: str) -> None:
        """Best-effort move a just-promoted skill back to ``_drafts/``.

        Used when a post-move step (lifecycle transition, audit) fails after
        the file move succeeded. No-op if the stable path is already gone.
        """
        import shutil

        stable = self.stable_path(skill_id)
        draft = self.draft_path(skill_id)
        if not stable.is_dir():
            return
        draft.parent.mkdir(parents=True, exist_ok=True)
        try:
            await asyncio.to_thread(shutil.move, str(stable), str(draft))
        except OSError:
            # Best-effort; the caller has already logged the primary failure.
            pass


@dataclass(frozen=True)
class SkillPromotionResult:
    """Outcome of a successful ``SkillRegistryPromotionTarget.promote`` call."""

    skill_id: str
    draft_path: str
    stable_path: str


class SkillPromotionError(ValueError):
    """Raised when a skill promotion precondition fails (P5-011)."""


__all__ = [
    "FilePathPromotionTarget",
    "PromotionTarget",
    "SkillPromotionError",
    "SkillPromotionResult",
    "SkillRegistryPromotionTarget",
]
