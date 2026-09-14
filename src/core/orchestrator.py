"""Agent orchestrator — drives Claude via the Anthropic SDK with tool use."""

from __future__ import annotations

import asyncio
import glob as glob_mod
import json
import logging
import math
import os
import re
import shlex
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, Iterable, List, Mapping, Optional

import yaml

from src.config import secret_value, settings

# P1-1 split: the tool surface lives in src/core/agent_tools.py; re-exported
# here for every existing importer (tests import _execute_tool/_tool_* /
# _load_packaged_skill_md/_nonce_env_for_command/AGENT_TOOLS from orchestrator).
from src.core.agent_tools import (  # noqa: F401
    AGENT_TOOLS,
    ToolExecutionResult,
    _config_snapshot_path_from_command,
    _execute_tool,
    _load_packaged_skill_md,
    _nonce_env_for_command,
    _normalize_command_for_plan,
    _safe_path,
    _safe_write_path,
    _tool_bash,
    _tool_glob,
    _tool_grep,
    _tool_read_file,
    _tool_write_file,
)
from src.core.artifact_reference import normalize_artifact_references_in_mapping
from src.core.command_runner import (
    CommandProcessRegistry,
    GovernedCommandRunner,
    OutputCallback,
    _build_child_env,
    redact_sensitive_text,
)
from src.core.consistency_validator import (
    ACCEPTED_ADAPTIVE_NOOP_REASONS,
    build_consistency_report,
    check_adaptive_feature_sweep,
    consistency_report_json,
)
from src.core.experiment_parser import (
    parse_iteration_marker,
    parse_prepare_output,
)
from src.core.gate_status import (
    normalize_training_gate_aliases,
    training_gates_passed_from_iteration,
)
from src.core.iteration_context import (
    ITERATION_CONTEXT_DIGEST_MARKER,
    build_iteration_context_digest,
    derive_exploration_markers,
)
from src.core.iteration_snapshot import (
    build_iteration_attempt_snapshot,
    build_trial_identity,
    canonical_config_hash,
    trial_identity_hash,
    write_iteration_attempt_snapshot,
)
from src.core.llm_provider import (
    _CLAUDE_INPUT_USD_PER_TOKEN,
    _CLAUDE_MAX_OUTPUT_TOKENS,
    _CLAUDE_OUTPUT_USD_PER_TOKEN,
    AnthropicProvider,
    ContentBlock,
    LLMProvider,
    Message,
    ProviderCapabilityMismatch,
    ProviderResponse,
    RequestBlock,
    RequiredCapabilities,
    StopReason,
    TextBlock,
    ToolDef,
    ToolResultBlock,
    ToolUseBlock,
    Usage,
    build_provider,
)
from src.core.log_writer import AgentLogWriter
from src.core.output_digest import digest_command_output
from src.core.output_parser import (
    DelimitedKVParser,
    JSONMarkerParser,
    OutputParser,
)
from src.core.research_phase_plan import (
    _PHASE_ADVANCEMENT_KEYS,
    EVIDENCE_INHERITABLE_PHASES,
    NOOP_INHERITABLE_PHASES,
    _is_rejected_duplicate,
    build_phase_state,
    incomplete_phase_ids,
    phase_cap_exceeded,
    phase_state_json,
)
from src.core.result_artifact import enrich_marker_from_result_artifact
from src.core.skill_runtime import (
    SkillConfigError,
    SkillRuntime,
    materialize_skill_runtime,
)
from src.core.state_machine import (
    IllegalTransitionError,
    SessionEvent,
    SessionState,
    SessionStateMachine,
)
from src.core.state_store import StateStore
from src.core.trial_workspace import (
    TrialContext,
    build_trial_context,
    trial_marker_candidates,
)
from src.ws.events import broadcaster

logger = logging.getLogger(__name__)



# Pricing constants (_CLAUDE_INPUT_USD_PER_TOKEN / _CLAUDE_OUTPUT_USD_PER_TOKEN /
# _CLAUDE_MAX_OUTPUT_TOKENS) moved to src.core.llm_provider (P1-002); imported
# above. They back the pre-spend budget gate and post-call cost accounting.
_COMMAND_OUTPUT_LOG_INTERVAL_S = 2.0
_COMMAND_OUTPUT_LOG_MAX_CHARS = 2000

# Phase 5.4: number of consecutive command-policy rejections after which
# the agent loop aborts as ``failed`` and waits for operator review.
_MAX_CONSECUTIVE_POLICY_REJECTIONS = 5

# AR-3: Phases that legitimately emit no config_snapshot because they do NOT
# run a fresh training command — they validate, replay, or promote an already-
# trained artefact.  _record_iteration inherits the most recent non-null
# config_snapshot from the DB for these phases so that consistency reports
# don't flag ``missing_config_snapshot`` as a blocker.
_PROMOTION_FAMILY: frozenset[str] = frozenset({"promotion_proposal"})

# Promotion gate blockers the AGENT can act on during the run (model-quality /
# data-handling). Surfaced in the iteration-context digest so the agent tunes
# for them before the terminal phase. Infra blockers (inference_*, smoke,
# signal_health, rollback, inference_parity) are resolved server-side by the
# PromotionEvidenceCollector at promotion time and are intentionally excluded —
# they are not the agent's job and would only cause it to flail.
_AGENT_ACTIONABLE_BLOCKERS: frozenset[str] = frozenset()

# Stagnation-genuineness check: phase-specific evidence keys that, when
# present in an iteration's ``metrics_json``, indicate the agent (or a
# server-side evidence collector) attempted real work in that phase — not a
# permissive ``auto_phase_evidence`` fallback. Used by
# ``_phase_advancement_is_genuine`` to decide whether to honor a phase's
# stagnation exemption.
_PHASE_SPECIFIC_AGENT_KEYS: Dict[str, frozenset[str]] = {}


# ---------------------------------------------------------------------------
# Research config dataclass
# ---------------------------------------------------------------------------


@dataclass
class ResearchConfig:
    id: str
    instrument: str
    timeframe: str
    model_type: str
    tag: str = ""
    quick_mode: bool = False
    max_iterations: int = 30
    max_budget_usd: float = 10.0
    timeout_s: int = 0  # 0 = use server default
    focus_hint: Optional[str] = None
    workspace_path: str = ""
    # ML-62: Session resume on timeout
    resumed_from: Optional[str] = None  # parent session ID when continuing
    # ML-63: Parent pipeline ID for phase sessions
    pipeline_id: Optional[str] = None
    # ARC-011 P1-023 (D3): skill identity. Empty by default for back-compat —
    # the transitional runtimes (P1-024..026) derive these from model_type.
    # Phase 2 makes them authoritative (read from the manifest / API body).
    skill_id: str = ""
    skill_version: str = ""
    # ARC-011 P2-017: canonical domain-neutral fields. Empty by default for
    # back-compat — when set, they are authoritative; the legacy
    # model_type/instrument/timeframe fields derive from them (via the legacy
    # alias registry P2-019). Callers may pass either shape: legacy
    # (instrument/timeframe/model_type) or canonical (subject_id/variant/skill_id).
    subject_id: str = ""
    variant: str = ""
    skill_params: dict = None  # type: ignore[assignment]  # set in __post_init__
    # ARC-011 P4-002: per-session anti-forgery nonce (W11). Populated by the
    # session_manager from the built session manifest before the orchestrator
    # runs, then (a) delivered to the sanctioned eval subprocess via env
    # (AUTORESEARCH_SESSION_NONCE) and (b) threaded to parse_iteration for
    # nonce verification (P4-003). Empty for legacy sessions without a nonce —
    # the parser's graceful-downgrade path handles that (metrics_unverified).
    session_nonce: str = ""

    def __post_init__(self) -> None:
        # ARC-011 P2-017: reconcile legacy and canonical shapes. Either shape is
        # accepted at construction; the canonical fields win when set.
        # skill_id derivation from model_type is intentionally NOT done here —
        # it happens at materialize_skill_runtime time so legacy sessions keep
        # the transitional runtime until the orchestrator reads are fully migrated
        # (P2-021..024). subject_id/variant are pure aliases (no routing
        # consequence) so they derive here.
        # skill_params dict: init, then mirror the flat ML fields so manifest-
        # driven runtimes read them from one place (P2-018 callers migrate to
        # skill_params.get(...); until then both surfaces stay populated).
        if self.skill_params is None:
            object.__setattr__(self, "skill_params", {})
        # Canonical subject/variant fields win; otherwise derive from legacy.
        if not self.subject_id:
            object.__setattr__(self, "subject_id", self.instrument)
        if not self.variant:
            object.__setattr__(self, "variant", self.timeframe)

    # ARC-011 P2-021: domain-neutral accessors for the legacy fields. The
    # orchestrator reaches these through ``config.domain`` / ``config.subject_id``
    # / ``config.variant`` so the Phase-2 grep guard
    # (``config\.(model_type|instrument|timeframe)``) returns zero hits. The
    # legacy fields stay as storage (back-compat for every external caller);
    # these properties are the domain-neutral read surface.
    @property
    def domain(self) -> str:
        """The research domain (legacy ``model_type`` value: direction/volatility/rl)."""
        return self.model_type


SERVER_OWNED_SETUP_INSTRUCTION = (
    "Run the setup command exactly as shown. The server has already prepared "
    "fresh-session cleanup or continuation behavior, so do not add reset flags."
)

PROMOTION_HANDOFF_INSTRUCTION = (
    "Promotion handoff: Do not promote directly. Finish with a best validated "
    "config and let the server preview/confirm."
)

# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class AgentOrchestrator:
    """Runs a Claude agent session for autonomous ML experiment tuning."""

    def __init__(
        self,
        store: StateStore,
        *,
        state_machine: Optional[SessionStateMachine] = None,
    ) -> None:
        self._store = store
        # ARC-011 P0-004: the state machine is the sole session-status writer.
        # When not injected (e.g. unit tests exercising non-lifecycle paths)
        # one is constructed bound to the shared broadcaster; production
        # injects a shared instance so SessionManager and the orchestrator
        # share one per-session lock registry (the W8 fix).
        self._sm = state_machine or SessionStateMachine(store, broadcaster)
        # ARC-011 P0-006: registry of in-flight governed subprocesses so a
        # hard-timeout / operator-stop cancel can reap the process tree from
        # outside the to_thread worker that owns the Popen handle.
        self._command_procs = CommandProcessRegistry()
        # ARC-011 P1-002/P4-010: the LLM is reached only through the LLMProvider
        # protocol. The default provider is constructed via the provider router
        # (build_provider); per-skill provider selection (P4-010) overrides it
        # per-session via _session_providers. No direct anthropic.* reference
        # remains in this file.
        self._provider: LLMProvider = build_provider("anthropic")
        # P4-010: per-session provider/model overrides (keyed by research_id).
        # Populated in run() when the skill manifest declares a non-anthropic
        # provider; _call_llm_with_retry and the insights path fall back to
        # self._provider / settings.anthropic_model when no override is set.
        self._session_providers: Dict[str, LLMProvider] = {}
        self._session_models: Dict[str, str] = {}
        # ARC-011 P1-013: experiment output is parsed only through the
        # OutputParser protocol. The two transitional implementations
        # (DelimitedKVParser for the --- block, JSONMarkerParser for the
        # ITERATION_RESULT: line) delegate to the unchanged logic; the
        # historical experiment_parser facade functions are kept for the parity
        # engine and any caller that wants the IterationMetrics dataclass.
        self._prepare_parser: OutputParser = DelimitedKVParser()
        self._marker_parser: OutputParser = JSONMarkerParser()
        self._stop_flags: Dict[str, bool] = {}
        self._pause_flags: Dict[str, bool] = {}
        # ARC-011 review C2: per-session SkillRuntime binding (registered in
        # run() at materialization; dropped in the run() finally). Out-of-loop
        # helpers (phase-plan refresh, blocker classification, promotion
        # routing) reach the session's skill through this map — mirrors
        # _session_providers / _session_models.
        self._session_skills: Dict[str, SkillRuntime] = {}
        # ARC-011 P6-004: per-session captured lock_epoch. Captured once at
        # run() entry (the owning worker holds the advisory lock for the run's
        # lifetime); threaded to the state-advancing writes in _record_iteration
        # so a stale worker whose session was deauthorized (stop/timeout landed
        # on another worker, bumping lock_epoch) has its late writes rejected
        # by the store's conditional WHERE. Refreshed after a local resume.
        self._session_epochs: Dict[str, int] = {}
        # AR-4: per-session counter tracking how many consecutive kick attempts
        # have been made for each distinct block_reason.  When the counter
        # reaches 3, the kick escalates to a forced TERMINATE_REQUEST instead
        # of re-injecting the same remediation nudge, preventing infinite
        # re-asking on an unresolvable blocker.
        self._blocker_attempt_counters: Dict[str, Dict[str, int]] = {}

    def _make_command_output_callback(
        self,
        *,
        agent_log: AgentLogWriter,
        loop: asyncio.AbstractEventLoop,
        turn: int,
        runtime_command_id: Optional[int],
    ) -> OutputCallback:
        last_emit = 0.0

        def _callback(stream: str, chunk: str) -> None:
            nonlocal last_emit
            if not chunk.strip():
                return
            now = time.monotonic()
            if (
                now - last_emit < _COMMAND_OUTPUT_LOG_INTERVAL_S
                and len(chunk) <= _COMMAND_OUTPUT_LOG_MAX_CHARS
            ):
                return
            last_emit = now
            truncated = len(chunk) > _COMMAND_OUTPUT_LOG_MAX_CHARS
            content = chunk[-_COMMAND_OUTPUT_LOG_MAX_CHARS:].rstrip()
            if not content:
                return
            meta = {
                "stream": stream,
                "runtime_command_id": runtime_command_id,
                "partial": True,
                "truncated": truncated,
            }
            asyncio.run_coroutine_threadsafe(
                agent_log.append(
                    "command_output", content, turn=turn, meta=meta,
                ),
                loop,
            )

        return _callback

    def request_stop(self, research_id: str) -> None:
        self._stop_flags[research_id] = True

    def request_pause(self, research_id: str) -> None:
        self._pause_flags[research_id] = True

    def request_resume(self, research_id: str) -> None:
        self._pause_flags.pop(research_id, None)

    # ── ML-68 / ARC-011 P1-002: Loop-owned retry ─────────────────────────
    # The transient decision now flows through provider.classify_error()
    # (R4 / spike D-retry). Backoff (30·2^n), the budget-aware skip, and the
    # transient exception set (APITimeout/APIConnection/InternalServer + HTTP
    # 429/502/503/529) are preserved verbatim — the decision is identical to
    # the pre-refactor _call_claude_with_retry; only the classification source
    # moved into AnthropicProvider.

    async def _call_llm_with_retry(
        self,
        *,
        messages: list[Message],
        system_prompt: str,
        research_id: str,
        agent_log: AgentLogWriter,
        turn: int,
        remaining_budget_s: Optional[float] = None,
    ) -> ProviderResponse:
        """Call ``provider.messages_create`` with loop-owned retry + backoff.

        Retries transient errors as classified by
        ``self._provider.classify_error`` (the same set the pre-refactor
        ``_call_claude_with_retry`` retried: connection/timeout/server errors
        and HTTP 429 / 502 / 503 / 529).

        Phase 2.3: when ``remaining_budget_s`` is provided, the loop refuses
        to start a backoff sleep that would push the next attempt past the
        session's wall-clock budget; in that case the last exception is
        re-raised immediately so the outer turn loop can fail cleanly
        instead of cancelling mid-sleep.
        """
        max_retries = settings.max_api_retries
        backoff_base = 30  # seconds
        # P4-010: use the per-session provider/model if the skill declared a
        # non-anthropic provider; fall back to the default otherwise.
        provider = self._session_providers.get(research_id, self._provider)
        model = self._session_models.get(research_id, settings.anthropic_model)

        for attempt in range(max_retries + 1):
            try:
                return await provider.messages_create(
                    model=model,
                    system=system_prompt,
                    messages=messages,
                    tools=AGENT_TOOLS,
                    max_tokens=_CLAUDE_MAX_OUTPUT_TOKENS,
                )
            except Exception as exc:
                err = provider.classify_error(exc)
                if not err.transient or attempt >= max_retries:
                    raise
                wait = backoff_base * (2 ** attempt)
                if (
                    remaining_budget_s is not None
                    and wait >= remaining_budget_s
                ):
                    status = f"HTTP {err.status_code}" if err.status_code else type(exc).__name__
                    logger.warning(
                        "Research %s turn %d: skipping retry — %s backoff %ds "
                        "exceeds remaining budget %.0fs",
                        research_id, turn, status, wait, remaining_budget_s,
                    )
                    raise
                status = f"HTTP {err.status_code}" if err.status_code else type(exc).__name__
                logger.warning(
                    "Research %s turn %d: transient API error (%s), "
                    "retry %d/%d in %ds",
                    research_id, turn, status,
                    attempt + 1, max_retries, wait,
                )
                await agent_log.append(
                    "warning",
                    f"API {status}: retry {attempt + 1}/{max_retries} "
                    f"in {wait}s — {str(exc)[:200]}",
                    turn=turn,
                )
                await asyncio.sleep(wait)

        # Unreachable but satisfies type-checkers
        raise RuntimeError("Retry loop exited without return or raise")  # pragma: no cover

    # ── ML-68: Context compaction ────────────────────────────────────────
    @staticmethod
    def _compact_messages(
        messages: list[Message],
        keep_recent: int = 40,
    ) -> list[Message]:
        """Bound retained conversation history to avoid unbounded memory growth.

        Keeps the first message (initial prompt) and the last *keep_recent*
        messages intact. Older messages are represented by one deterministic
        summary marker; detailed history remains in agent_log.jsonl and SQLite.
        """
        if len(messages) <= keep_recent + 1:
            return messages

        compacted = [messages[0]]  # preserve initial user prompt

        old_section = messages[1:-keep_recent]
        if old_section:
            assistant_count = sum(1 for msg in old_section if msg.role == "assistant")
            user_count = sum(1 for msg in old_section if msg.role == "user")
            tool_result_count = 0
            for msg in old_section:
                if isinstance(msg.content, list):
                    tool_result_count += sum(
                        1 for block in msg.content if isinstance(block, ToolResultBlock)
                    )
            content = (
                "[system] Earlier conversation compacted: "
                f"{len(old_section)} messages "
                f"({assistant_count} assistant, {user_count} user, "
                f"{tool_result_count} tool results). "
                "Use the persisted iteration records and agent log for details."
            )
            latest_digest = AgentOrchestrator._latest_iteration_context_digest(
                old_section
            )
            if latest_digest:
                content = f"{content}\n\n{latest_digest}"
            compacted.append(Message(role="user", content=content))

        compacted.extend(messages[-keep_recent:])
        return compacted

    @staticmethod
    def _latest_iteration_context_digest(
        messages: list[Message],
    ) -> Optional[str]:
        for message in reversed(messages):
            content = message.content
            if isinstance(content, str) and ITERATION_CONTEXT_DIGEST_MARKER in content:
                return content
            if not isinstance(content, list):
                continue
            for block in reversed(content):
                if (
                    isinstance(block, TextBlock)
                    and ITERATION_CONTEXT_DIGEST_MARKER in block.text
                ):
                    return block.text
        return None

    def _should_stop(self, research_id: str) -> bool:
        # Fast path: an in-process stop flag set by THIS worker's
        # SessionManager.stop_session (or request_stop). Always checked first.
        return self._stop_flags.get(research_id, False)

    async def _should_stop_cross_worker(self, research_id: str) -> bool:
        """Cross-worker stop check (ARC-011 P6-004 / H3).

        The in-process ``_stop_flags`` only reflects stops routed to THIS
        worker. Under ``WEB_CONCURRENCY > 1`` an operator's stop may land on a
        different worker, which writes ``stop_requested`` to the shared DB via
        ``SessionStateMachine.transition``. This worker (owning the running
        session) must observe that DB-side intent on its turn-loop poll and
        stop itself. SQLite (single-worker) never has cross-worker stops, but
        the check is cheap and uniform, so it runs on both backends.
        """
        if self._stop_flags.get(research_id, False):
            return True
        try:
            session = await self._store.get_session(research_id)
        except Exception:  # noqa: BLE001  (a store failure must not mask a stop)
            logger.warning("stop-check store read failed for %s", research_id,
                           exc_info=True)
            return False
        if not session:
            return False
        # The DB-side stop intent is a transitional/terminal status in the
        # stopping family. (``terminate_request_received`` is a separate flag
        # for the agent's own TERMINATE_REQUEST completion signal — NOT an
        # operator-stop signal — so it must not be treated as a cross-worker
        # stop, or normal completions get misread as stops.)
        status = str(session.get("status") or "").lower()
        return status in {"stopping", "stopped", "timed_out", "failed"}

    async def _wait_while_paused(self, research_id: str) -> None:
        """Block while the session is paused — locally OR DB-side.

        ARC-011 review C5 (P6-004 / H3): the previous loop only spun on the
        in-process ``_pause_flags``, so a pause recorded by a non-owning
        worker (DB status ``paused``) was never observed by the owner, and a
        cross-worker resume could never unstick a locally-paused owner. The
        DB status is authoritative: wait while it says ``paused``; when it
        says ``running`` again (resumed from any worker), proceed — even if a
        stale local flag is still set.
        """
        was_paused = False
        while True:
            if await self._should_stop_cross_worker(research_id):
                return
            db_paused = await self._is_paused_cross_worker(research_id)
            if not db_paused:
                if self._pause_flags.get(research_id, False):
                    # DB says running while the local flag is set — a resume
                    # was recorded elsewhere (or the local transition was
                    # outrun); honor the authoritative DB and proceed.
                    logger.info(
                        "Research %s: DB shows resumed while the local pause "
                        "flag is set — honoring the DB resume",
                        research_id,
                    )
                break
            was_paused = True
            await asyncio.sleep(2)
        # ARC-011 P6-004: a pause/resume transition bumped lock_epoch (the
        # state machine bumps on every committed transition). If we were
        # paused (locally or DB-side), refresh the captured epoch so
        # post-resume writes carry the fresh value and aren't fenced out by
        # our own transition.
        if was_paused:
            await self._refresh_session_epoch(research_id)

    async def _is_paused_cross_worker(self, research_id: str) -> bool:
        """True when the shared DB says the session is ``paused``.

        The DB-side pause may have been recorded by any worker (review C5);
        SQLite is single-worker so only the local path applies there, but
        the check is cheap and uniform on both backends.
        """
        try:
            session = await self._store.get_session(research_id)
        except Exception:  # noqa: BLE001  (a read failure must not un-pause)
            logger.warning(
                "pause-check store read failed for %s", research_id,
                exc_info=True,
            )
            # Fail closed against the local flag: a locally-paused session
            # must not un-pause merely because the DB read failed.
            return bool(self._pause_flags.get(research_id, False))
        if not session:
            return False
        return str(session.get("status") or "").lower() == "paused"

    async def _refresh_session_epoch(self, research_id: str) -> None:
        """Re-read and re-cache the session's lock_epoch after a local
        transition (resume) so subsequent writes carry the fresh value.
        No-op on SQLite (no lock_epoch column → stays None → unconditional)."""
        try:
            session = await self._store.get_session(research_id)
            self._session_epochs[research_id] = int(
                (session or {}).get("lock_epoch") or 0
            )
        except Exception:  # noqa: BLE001 — refresh must never block the run
            logger.debug("lock_epoch refresh failed for %s", research_id, exc_info=True)

    async def _load_claude_md_async(self) -> str:
        return await asyncio.to_thread(self._load_claude_md)

    async def _read_marker_file_async(
        self,
        config: ResearchConfig,
        min_mtime: Optional[float] = None,
        trial_dir: Optional[str] = None,
    ) -> Optional[str]:
        return await asyncio.to_thread(
            self._read_marker_file, config, min_mtime, trial_dir,
        )

    async def _verify_kv_metrics(
        self,
        research_id: str,
        result: Dict[str, Any],
        *,
        turn: int,
        agent_log: "AgentLogWriter",
        session_nonce: Optional[bytes],
        nonce_field: str,
        requires_signed: bool,
        source: str,
        pipeline_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """W11-verify a ``---`` KV metrics block (ARC-011 review C3).

        The KV auto-detect and marker-file paths parse with
        ``parse_prepare_output``, which has no nonce argument — review C3
        found this let any bash output containing a ``---`` block be
        recorded as an iteration even for skills with
        ``require_signed_metrics=true``. This runs the same four-state
        ``_verify_nonce`` check the marker path uses. A rejected block is
        audited as ``metrics.forged`` (previously KV-format forgeries were
        silently dropped with no audit) and returns ``None`` so the
        iteration is not recorded. Non-enforcing skills pass through
        unchanged (byte-identical legacy behavior).
        """
        if not requires_signed:
            return result

        from src.core.output_parser import _verify_nonce

        verified = _verify_nonce(
            result,
            session_nonce=session_nonce,
            nonce_field=nonce_field,
            require_signed_metrics=True,
        )
        if verified is not None:
            return verified

        logger.warning(
            "Research %s turn %d: rejected forged %s metrics block "
            "(nonce missing or mismatch) — not recorded",
            research_id, turn, source,
        )
        try:
            await agent_log.append(
                "system",
                "A `---` metrics block was rejected: the anti-forgery nonce "
                "was missing or did not match. Metrics may only be emitted by "
                "the sanctioned eval script, which receives the nonce via the "
                "AUTORESEARCH_SESSION_NONCE environment variable.",
                turn=turn,
            )
        except Exception:
            logger.debug(
                "agent log append failed for %s", research_id, exc_info=True,
            )
        try:
            await self._store.record_audit_event(
                actor_id="autoresearch-agent",
                action="metrics.forged",
                research_id=research_id,
                pipeline_id=pipeline_id,
                request_metadata={
                    "turn": turn,
                    "format": "delimited_kv",
                    "source": source,
                },
                outcome="failure",
                error_message=(
                    "KV metrics block rejected: nonce missing or "
                    "mismatch (forged)"
                ),
            )
        except Exception as exc:
            logger.warning(
                "Research %s: failed to record metrics_forged audit "
                "event: %s", research_id, exc,
            )
        return None

    def _load_claude_md(self) -> str:
        claude_md_path = os.path.join(settings.workspace_root, "CLAUDE.md")
        if os.path.exists(claude_md_path):
            return Path(claude_md_path).read_text(encoding="utf-8")
        return ""

    def _read_marker_file(
        self,
        config: ResearchConfig,
        min_mtime: Optional[float] = None,
        trial_dir: Optional[str] = None,
    ) -> Optional[str]:
        """Read and consume a marker file declared by the skill's
        ``output_parser.fallback`` section.

        The experiment command writes the marker on completion so the
        orchestrator can detect iterations even when the bash tool times
        out. When ``min_mtime`` is provided, a marker older than that
        timestamp is treated as stale (left over from a prior session)
        and ignored.

        ``trial_dir`` (P2 per-workdir state): when the command executed in
        an isolated trial directory, its marker/results files land there —
        the trial copies are checked first, the session-workspace paths
        stay as fallback (a staging-time copy is older than the command
        start and the ``min_mtime`` check discards it naturally).
        """
        skill = getattr(self, "_session_skills", {}).get(config.id)
        if skill is None:
            return None
        try:
            paths = list(skill.marker_file_paths(config))
        except Exception:
            return None
        if trial_dir:
            paths = trial_marker_candidates(trial_dir, paths)
        for marker_path in paths:
            if not marker_path.exists():
                continue
            if min_mtime is not None:
                try:
                    marker_mtime = marker_path.stat().st_mtime
                except OSError:
                    marker_mtime = None
                if marker_mtime is not None and marker_mtime < min_mtime:
                    logger.info(
                        "Ignoring stale marker file %s (mtime=%.3f < "
                        "min_mtime=%.3f)",
                        marker_path, marker_mtime, min_mtime,
                    )
                    continue
            # Rename-then-read so a concurrent writer cannot have its
            # fresh marker silently deleted by our cleanup.
            claim_path = (
                f"{marker_path}.consumed.{os.getpid()}.{int(time.time() * 1000)}"
            )
            try:
                os.replace(marker_path, claim_path)
            except FileNotFoundError:
                continue
            try:
                content = Path(claim_path).read_text(encoding="utf-8")
            except OSError as exc:
                logger.debug("Failed to read marker file %s: %s", claim_path, exc)
                content = None
            try:
                os.remove(claim_path)
            except OSError:
                logger.debug(
                    "Failed to unlink consumed marker %s", claim_path,
                    exc_info=True,
                )
            if content:
                return content
        return None

    def _load_research_resume(self, config: ResearchConfig) -> str:
        """Load the research resume for this instrument if it exists."""
        instrument_underscore = config.subject_id.replace("-", "_")
        resume_path = os.path.join(
            settings.runs_dir,
            f"{instrument_underscore}_{config.variant}",
            "research_resume.md",
        )
        content = self._read_research_resume_file(resume_path)
        if not content:
            try:
                self._generate_research_resume_file(
                    config=config,
                    resume_path=resume_path,
                )
            except Exception as exc:
                logger.warning("Research resume fallback raised: %s", exc)
            content = self._read_research_resume_file(resume_path)
        if not content:
            return ""
        return (
            "\n\n## Research Resume (prior experiments on this instrument)\n\n"
            "Use this context to avoid repeating failed experiments and "
            "build on what worked.\n\n"
            f"{content}"
        )

    @staticmethod
    def _read_research_resume_file(resume_path: str) -> str:
        try:
            if not os.path.exists(resume_path):
                return ""
            with open(resume_path, encoding="utf-8") as f:
                content = f.read()
            if not content.strip():
                return ""
            # Truncate to avoid context window bloat
            if len(content) > 12_000:
                content = content[:6000] + "\n\n*[truncated]*\n\n" + content[-6000:]
            return content
        except Exception as exc:
            logger.warning("Failed to load research resume: %s", exc)
            return ""

    def _skill_phase_plan(
        self, config: ResearchConfig,
    ) -> Optional[List[Dict[str, Any]]]:
        """ARC-011 review C2-1: the session's skill-runtime phase plan.

        Returns ``None`` for transitional sessions (empty ``skill_id`` — the
        legacy hardcoded per-model table applies) and on any registry/runtime
        failure (fail-open to the incumbent plan; a broken manifest must not
        blank the phase contract).
        """
        if not getattr(config, "skill_id", ""):
            return None
        try:
            rt = materialize_skill_runtime(self, config)
            return rt.phase_plan() or None
        except Exception:  # pragma: no cover — fail-open guard
            logger.debug(
                "skill phase plan unavailable for %s; using legacy table",
                config.id, exc_info=True,
            )
            return None

    def _build_phase_contract_block(self, config: ResearchConfig) -> str:
        """F5: render the canonical phase plan for the active model_type as a
        prompt section. The block tells the LLM:

        * which phase ids exist in order
        * the metrics-evidence key(s) each phase requires for advancement
        * the min/max iteration envelope per phase
        * how to flag a phase on an ITERATION_RESULT marker (search_phase)

        Without this, the agent was blind to the phase plan and would
        terminate after a few thousand `tabular_sweeps` iterations declaring
        the task done.
        """
        # ARC-011 review C2-1: the phase plan comes from the session's
        # skill runtime; skills without a declared plan get no contract.
        phases = self._skill_phase_plan(config)
        if not phases:
            return ""
        lines = [
            "",
            "",
            "## Phase Contract (server-tracked)",
            "",
            "Your research session is tracked against a phase plan. The "
            "orchestrator will refuse to let you terminate while phases "
            "remain incomplete and budget is available. Advance through "
            "phases by emitting the listed evidence key(s) in the "
            "`metrics_json` (or `config`) of an ITERATION_RESULT marker. "
            "Tag every ITERATION_RESULT with `search_phase: <phase_id>` "
            "so the server can attribute work correctly.",
            "",
            "| Order | Phase ID | Min iters | Max iters | Evidence key(s) | Next action |",
            "|---|---|---|---|---|---|",
        ]
        for idx, phase in enumerate(phases, start=1):
            pid = phase.get("id", "")
            keys = _PHASE_ADVANCEMENT_KEYS.get(pid, ()) or ()
            keys_str = ", ".join(keys) if keys else "—"
            lines.append(
                f"| {idx} | `{pid}` | "
                f"{phase.get('min_iterations', 0)} | "
                f"{phase.get('max_iterations', '—')} | "
                f"{keys_str} | "
                f"{phase.get('next_action', '')} |"
            )
        lines.extend([
            "",
            "**Termination rules:**",
            "* Do not emit `end_turn` while any phase is `pending` or "
            "`in_progress` and budget remains. The loop guard will reject "
            "it and inject a continuation message.",
            "* If you believe the entire plan should terminate early, "
            "reply with a single line starting `TERMINATE_REQUEST:` and a "
            "structured justification per incomplete phase.",
            "* Reaching a phase's `max_iters` ceiling triggers a system "
            "nudge to advance. Treat it as a hard signal to either emit "
            "the evidence key or move on.",
        ])
        return "\n".join(lines)

    async def _extract_session_insights(self, research_id: str) -> None:
        """ML-60: Use Claude to extract compact insights from a completed session.

        Stores a short text summary (≤500 chars) of what was learned:
        which parameter changes helped/hurt, key metric sensitivities,
        and actionable takeaways for future sessions.
        """
        try:
            session = await self._store.get_session(research_id)
            if not session:
                return
            iterations = await self._store.get_iterations(research_id)
            if not iterations:
                return

            # Build a compact iteration summary for the extraction prompt
            iter_lines = []
            for it in iterations:
                pm = it.get("primary_metric")
                metric_s = f"{pm:.4f}" if pm is not None else "—"
                decision = it.get("decision", "?")
                desc = (it.get("description") or "")[:200]
                config_snap = (it.get("config_snapshot") or "")[:300]
                iter_lines.append(
                    f"Iter {it.get('iteration', '?')}: metric={metric_s} "
                    f"decision={decision} desc={desc}"
                )
                if config_snap:
                    iter_lines.append(f"  config_diff: {config_snap}")

            iter_text = "\n".join(iter_lines)

            prompt = (
                f"You are analyzing a completed ML research session.\n"
                f"Model: {session.get('model_type', '?')} | "
                f"Instrument: {session.get('instrument', '?')} "
                f"{session.get('timeframe', '?')}\n"
                f"Tag: {session.get('tag', '?')} | "
                f"Best metric: {session.get('best_metric')}\n\n"
                f"Iterations:\n{iter_text}\n\n"
                f"Summarize KEY LEARNINGS in 3-5 bullet points (max 500 chars total).\n"
                f"Focus on: which params improved/degraded the metric, "
                f"what ranges worked, what to avoid.\n"
                f"Format: plain bullet points, no markdown headers.\n"
                f"Example:\n"
                f"- Increasing learning_rate from 3e-4 to 1e-3 degraded Sharpe by 0.15\n"
                f"- entropy_coef=0.005 with clip_range=0.15 gave best composite (1.82)\n"
                f"- gamma > 0.995 caused instability (OOS return went negative)"
            )

            # ARC-011 P1-002/P4-010: one-shot completion via the provider (replaces
            # the bare messages.create Haiku call). No tools, no retry. Uses the
            # per-session provider when the skill declared a non-anthropic one.
            insights_provider = self._session_providers.get(research_id, self._provider)
            insights = await insights_provider.complete(
                model=settings.anthropic_default_haiku_model,
                prompt=prompt,
                max_tokens=300,
            )

            # Trim to 500 chars max
            insights = insights.strip()[:500]

            if insights:
                await self._store.update_session(research_id, insights=insights)
                logger.info(
                    "ML-60: Extracted insights for session %s (%d chars)",
                    research_id[:8], len(insights),
                )
        except Exception as exc:
            logger.warning(
                "ML-60: Failed to extract insights for %s: %s",
                research_id[:8], exc,
            )

    async def _record_command_policy_rejection(
        self,
        *,
        config: ResearchConfig,
        turn: int,
        command: str,
        tool_meta: Dict[str, Any],
    ) -> None:
        reason = str(tool_meta.get("policy_reason") or "Command rejected by policy")
        try:
            await self._store.record_audit_event(
                actor_id="autoresearch-agent",
                action="command.reject",
                research_id=config.id,
                pipeline_id=config.pipeline_id,
                request_metadata={
                    "turn": turn,
                    "tool": "bash",
                    "command": redact_sensitive_text(command),
                    "operation": tool_meta.get("policy_operation"),
                },
                outcome="failure",
                error_message=reason,
            )
        except Exception as exc:
            logger.warning(
                "Research %s turn %d: failed to record command rejection audit event: %s",
                config.id,
                turn,
                exc,
                exc_info=True,
            )

    async def _guard_duplicate_training_attempt(
        self,
        *,
        config: ResearchConfig,
        turn: int,
        command: str,
        config_snapshot: Optional[str],
        planned_trial: Optional[Dict[str, Any]] = None,
        current_phase: Optional[str] = None,
    ) -> tuple[Optional[ToolExecutionResult], Optional[Dict[str, Any]]]:
        """Reject an already-attempted config/seed/mode/split identity.

        Exception: when the session is in ``baseline_capture`` phase and the
        duplicate is a cross-session attempt (a prior session's baseline of
        the same canonical config), inherit the prior baseline rather than
        rejecting. The agent's contracted next_action for this phase is to
        run the immutable promoted-config baseline, which is by definition
        identical across sessions.
        """

        identity = build_trial_identity(
            instrument=config.subject_id,
            timeframe=config.variant,
            model_type=config.domain,
            command=command,
            config_snapshot=config_snapshot,
            quick_mode=config.quick_mode,
            marker=planned_trial or {},
        )
        identity_hash = trial_identity_hash(identity)
        if not identity_hash:
            return None, None

        duplicate = await self._store.find_duplicate_trial_identity(
            research_id=config.id,
            trial_identity_hash=identity_hash,
            instrument=config.subject_id,
            timeframe=config.variant,
            model_type=config.domain,
            include_cross_session=(
                settings.autoresearch_cross_session_duplicate_check
            ),
        )
        if not duplicate:
            return None, None

        duplicate_research_id = duplicate.get("research_id")
        duplicate_iteration = duplicate.get("iteration")

        if (
            current_phase == "baseline_capture"
            and duplicate_research_id
            and duplicate_research_id != config.id
            and duplicate.get("duplicate_reason") is None
        ):
            return self._build_baseline_link(
                config=config,
                turn=turn,
                identity=identity,
                identity_hash=identity_hash,
                config_snapshot=config_snapshot,
                duplicate=duplicate,
            )

        # Issue 5: a noop-inheritable phase (e.g. adaptive_feature_sweeps)
        # advances on a config-invariant accepted noop. The only config that
        # produces it is the one already recorded, so a re-run to assert the
        # evidence dedups. Rejecting it with an evidence-stripped marker wedges
        # the phase forever. Instead, inherit the accepted evidence from the
        # completed prior iteration so the normal recording path advances the
        # phase. Strictly scoped to non-dwell-gated phases (see
        # NOOP_INHERITABLE_PHASES) so this can never skip genuine work.
        if (
            current_phase in NOOP_INHERITABLE_PHASES
            and duplicate.get("duplicate_reason") is None
        ):
            _dup_metrics = self._parse_metrics_json(duplicate.get("metrics_json"))
            _noop = str(
                _dup_metrics.get("adaptive_feature_noop_reason") or ""
            ).strip()
            if (
                _noop in ACCEPTED_ADAPTIVE_NOOP_REASONS
                and check_adaptive_feature_sweep(_dup_metrics) is None
            ):
                return self._build_phase_evidence_link(
                    config=config,
                    turn=turn,
                    identity=identity,
                    identity_hash=identity_hash,
                    config_snapshot=config_snapshot,
                    duplicate=duplicate,
                    current_phase=current_phase,
                    inherited_metrics=_dup_metrics,
                )

        # DM-1: when the dispatched config matches this session's best and
        # the active phase is in EVIDENCE_INHERITABLE_PHASES, inherit the
        # source iteration's phase-advancement evidence instead of paying
        # ~7 minutes for a re-train that will produce the identical
        # metric. Observed on res_be66790e192e: iterations 8/10/11/12 all
        # re-ran the iter-7 best config across calibration_replay_gates,
        # multi_seed_robustness, and inference_parity_replay — four wasted
        # training runs against a 50-iteration budget.
        if (
            current_phase in EVIDENCE_INHERITABLE_PHASES
            and duplicate.get("duplicate_reason") is None
            and duplicate.get("research_id") == config.id
        ):
            best = await self._store.get_best_iteration(config.id)
            best_hash = (
                best.get("canonical_config_hash") if isinstance(best, dict) else None
            )
            if (
                best_hash
                and best_hash == identity.get("canonical_config_hash")
            ):
                _dup_metrics = self._parse_metrics_json(duplicate.get("metrics_json"))
                _dup_config = (
                    _dup_metrics.get("config")
                    if isinstance(_dup_metrics.get("config"), dict)
                    else {}
                )
                _advancement_keys = _PHASE_ADVANCEMENT_KEYS.get(current_phase, ())
                # Mirror ``_has_metric``'s any-of semantics in
                # research_phase_plan._completed_phase_ids: presence of
                # the key at top level OR nested under ``config`` counts.
                if any(
                    _dup_metrics.get(key) or _dup_config.get(key)
                    for key in _advancement_keys
                ):
                    return self._build_evidence_replay_link(
                        config=config,
                        turn=turn,
                        identity=identity,
                        identity_hash=identity_hash,
                        config_snapshot=config_snapshot,
                        duplicate=duplicate,
                        current_phase=current_phase,
                        inherited_metrics=_dup_metrics,
                    )

        duplicate_reason = (
            "Duplicate training attempt rejected: the same canonical config, "
            f"seed={identity.get('seed')}, mode={identity.get('validation_mode')}, "
            f"data_split_id={identity.get('data_split_id')}, model="
            f"{config.domain}, instrument={config.subject_id}, timeframe="
            f"{config.variant} already exists in session "
            f"{duplicate_research_id} iteration {duplicate_iteration}."
        )
        marker = {
            "status": "rejected_duplicate",
            "primary_metric": None,
            "metric_name": None,
            "training_gates_passed": False,
            "all_gates_passed": False,
            "decision": "discard",
            "description": f"{duplicate_reason} (turn {turn})",
            "config_snapshot": config_snapshot,
            "canonical_config_hash": identity.get("canonical_config_hash"),
            "trial_identity": identity,
            "trial_identity_hash": identity_hash,
            "duplicate_of_research_id": duplicate_research_id,
            "duplicate_of_iteration": duplicate_iteration,
            "duplicate_reason": duplicate_reason,
        }
        return ToolExecutionResult(
            duplicate_reason,
            meta={
                "policy_allowed": False,
                "policy_reason": duplicate_reason,
                "policy_operation": "duplicate_attempt.reject",
                "normalized_command": _normalize_command_for_plan(command),
                "returncode": None,
                "timed_out": False,
                "trial_identity_hash": identity_hash,
                "duplicate_of_research_id": duplicate_research_id,
                "duplicate_of_iteration": duplicate_iteration,
            },
        ), marker

    def _build_baseline_link(
        self,
        *,
        config: ResearchConfig,
        turn: int,
        identity: Dict[str, Any],
        identity_hash: str,
        config_snapshot: Optional[str],
        duplicate: Dict[str, Any],
    ) -> tuple[ToolExecutionResult, Dict[str, Any]]:
        """Inherit a cross-session baseline instead of rejecting it.

        Builds a synthetic prepare.py-like output block carrying the prior
        baseline's metric so the orchestrator's normal recording path treats
        this as a real iteration, plus a marker tagged with
        ``baseline_linked_from_research_id`` for audit traceability.
        """

        prior_research_id = duplicate.get("research_id")
        prior_iteration = duplicate.get("iteration")
        prior_metric = duplicate.get("primary_metric")
        prior_metric_name = duplicate.get("metric_name") or (
            "composite_direction_score"
            if config.domain == "direction"
            else "primary_metric"
        )
        # ``training_gates_passed`` lives inside ``metrics_json`` (not as a row
        # column), so read both flags through the helper that parses the JSON
        # blob, falls back to the row's ``all_gates_passed`` column, and
        # collapses the legacy alias. This prevents the synthetic marker from
        # emitting a mismatched ``training_gates_passed=False / all_gates_
        # passed=True`` pair that triggers the gate-alias warning.
        prior_training_gates = training_gates_passed_from_iteration(
            duplicate, default=False,
        )
        prior_all_gates = prior_training_gates

        message = (
            f"Baseline linked from {prior_research_id} iteration "
            f"{prior_iteration} (metric={prior_metric_name}={prior_metric})."
        )

        synthetic_block = "\n".join(
            [
                "---",
                "status:             completed",
                f"primary_metric:     {prior_metric:.6f}"
                if isinstance(prior_metric, (int, float))
                else "primary_metric:     0.0",
                f"metric_name:        {prior_metric_name}",
                "direction:          higher_is_better",
                f"training_gates_passed: {str(prior_training_gates).lower()}",
                f"all_gates_passed:   {str(prior_all_gates).lower()}",
                f"baseline_linked_from_research_id: {prior_research_id}",
                f"baseline_linked_from_iteration: {prior_iteration}",
                "---",
            ]
        )

        marker = {
            "status": "completed",
            "primary_metric": prior_metric,
            "metric_name": prior_metric_name,
            "training_gates_passed": prior_training_gates,
            "all_gates_passed": prior_all_gates,
            "decision": "keep",
            "search_phase": "baseline_capture",
            "description": f"{message} (turn {turn})",
            "config_snapshot": config_snapshot,
            "canonical_config_hash": identity.get("canonical_config_hash"),
            "trial_identity": identity,
            "trial_identity_hash": identity_hash,
            "baseline_linked_from_research_id": prior_research_id,
            "baseline_linked_from_iteration": prior_iteration,
        }

        return ToolExecutionResult(
            synthetic_block,
            meta={
                "policy_allowed": True,
                "policy_operation": "baseline.linked",
                "returncode": 0,
                "timed_out": False,
                "trial_identity_hash": identity_hash,
                "baseline_linked_from_research_id": prior_research_id,
                "baseline_linked_from_iteration": prior_iteration,
            },
        ), marker

    @staticmethod
    def _parse_metrics_json(raw: Any) -> Dict[str, Any]:
        """Best-effort parse of an iteration row's metrics_json into a dict."""
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str) and raw.strip():
            try:
                parsed = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return {}
            return parsed if isinstance(parsed, dict) else {}
        return {}

    def _build_phase_evidence_link(
        self,
        *,
        config: ResearchConfig,
        turn: int,
        identity: Dict[str, Any],
        identity_hash: str,
        config_snapshot: Optional[str],
        duplicate: Dict[str, Any],
        current_phase: str,
        inherited_metrics: Dict[str, Any],
    ) -> tuple[ToolExecutionResult, Dict[str, Any]]:
        """Inherit a noop-phase's accepted evidence on a dedup hit.

        Mirrors :meth:`_build_baseline_link`, but for a ``NOOP_INHERITABLE``
        phase whose advancement evidence is config-invariant (e.g.
        ``adaptive_feature_noop_reason: adaptive_features_unavailable``). The
        re-run dedups against a completed prior iteration that already carries
        the accepted noop; rather than rejecting it with an evidence-stripped
        marker (which wedges the phase forever — see Issue 5), synthesize a
        real, phase-tagged ``completed`` iteration that carries the inherited
        evidence so the normal recording path advances the phase.
        """

        prior_research_id = duplicate.get("research_id")
        prior_iteration = duplicate.get("iteration")
        prior_metric = duplicate.get("primary_metric")
        prior_metric_name = duplicate.get("metric_name") or (
            "composite_direction_score"
            if config.domain == "direction"
            else "primary_metric"
        )
        prior_training_gates = training_gates_passed_from_iteration(
            duplicate, default=False,
        )
        prior_all_gates = prior_training_gates

        noop_reason = str(
            inherited_metrics.get("adaptive_feature_noop_reason") or ""
        ).strip()
        # Inherit the structured adaptive_features block too, when the source
        # iteration recorded one (keeps downstream consistency checks happy).
        inherited_adaptive = inherited_metrics.get("adaptive_features")

        message = (
            f"Phase evidence for '{current_phase}' inherited from "
            f"{prior_research_id} iteration {prior_iteration} "
            f"(adaptive_feature_noop_reason={noop_reason}). Re-running the "
            f"only config that produces this config-invariant noop dedups; "
            f"the accepted evidence is inherited so the phase can advance "
            f"without a research-irrelevant perturbation."
        )

        synthetic_block = "\n".join(
            [
                "---",
                "status:             completed",
                f"primary_metric:     {prior_metric:.6f}"
                if isinstance(prior_metric, (int, float))
                else "primary_metric:     0.0",
                f"metric_name:        {prior_metric_name}",
                "direction:          higher_is_better",
                f"training_gates_passed: {str(prior_training_gates).lower()}",
                f"all_gates_passed:   {str(prior_all_gates).lower()}",
                f"adaptive_feature_noop_reason: {noop_reason}",
                f"search_phase:       {current_phase}",
                f"phase_evidence_linked_from_research_id: {prior_research_id}",
                f"phase_evidence_linked_from_iteration: {prior_iteration}",
                "---",
            ]
        )

        marker: Dict[str, Any] = {
            "status": "completed",
            "primary_metric": prior_metric,
            "metric_name": prior_metric_name,
            "training_gates_passed": prior_training_gates,
            "all_gates_passed": prior_all_gates,
            "decision": "keep",
            "search_phase": current_phase,
            "adaptive_feature_noop_reason": noop_reason,
            "description": f"{message} (turn {turn})",
            "config_snapshot": config_snapshot,
            "canonical_config_hash": identity.get("canonical_config_hash"),
            "trial_identity": identity,
            "trial_identity_hash": identity_hash,
            "phase_evidence_linked_from_research_id": prior_research_id,
            "phase_evidence_linked_from_iteration": prior_iteration,
        }
        if isinstance(inherited_adaptive, dict):
            marker["adaptive_features"] = inherited_adaptive

        return ToolExecutionResult(
            synthetic_block,
            meta={
                "policy_allowed": True,
                "policy_operation": "phase_evidence.linked",
                "returncode": 0,
                "timed_out": False,
                "trial_identity_hash": identity_hash,
                "phase_evidence_linked_from_research_id": prior_research_id,
                "phase_evidence_linked_from_iteration": prior_iteration,
            },
        ), marker

    def _build_evidence_replay_link(
        self,
        *,
        config: ResearchConfig,
        turn: int,
        identity: Dict[str, Any],
        identity_hash: str,
        config_snapshot: Optional[str],
        duplicate: Dict[str, Any],
        current_phase: str,
        inherited_metrics: Dict[str, Any],
    ) -> tuple[ToolExecutionResult, Dict[str, Any]]:
        """DM-1: inherit a session-best iteration's phase evidence on dedup hit.

        When the agent dispatches the *exact* canonical config that already
        produced this session's best iteration AND the active phase is in
        :data:`EVIDENCE_INHERITABLE_PHASES`, the orchestrator returns a
        synthesised prepare.py-like block carrying the prior iteration's
        metric + phase-advancement evidence keys *without* invoking the
        training command. The marker carries
        ``evidence_replayed_from_iteration`` so
        :func:`~src.core.consistency_validator._is_synthetic_promotion_iteration`
        whitelists it instead of flagging it as a synthetic-iteration
        replay attempt.

        Mirrors :meth:`_build_phase_evidence_link` (the
        ``NOOP_INHERITABLE_PHASES`` path) — the structural difference is
        the set of keys inherited and the audit field name.
        """

        prior_research_id = duplicate.get("research_id")
        prior_iteration = duplicate.get("iteration")
        prior_metric = duplicate.get("primary_metric")
        prior_metric_name = duplicate.get("metric_name") or (
            "composite_direction_score"
            if config.domain == "direction"
            else "primary_metric"
        )
        prior_training_gates = training_gates_passed_from_iteration(
            duplicate, default=False,
        )
        prior_all_gates = prior_training_gates
        prior_mlflow_run_id = duplicate.get("mlflow_run_id") or inherited_metrics.get(
            "mlflow_run_id"
        )

        # Surface the phase-advancement evidence the inherited iteration
        # already produced. Each key is the marker's flat top-level value
        # so ``_completed_phase_ids`` sees it via ``_has_metric``.
        advancement_keys = _PHASE_ADVANCEMENT_KEYS.get(current_phase, ())
        inherited_evidence: Dict[str, Any] = {}
        for key in advancement_keys:
            value = inherited_metrics.get(key)
            if value is None and isinstance(inherited_metrics.get("config"), dict):
                value = inherited_metrics["config"].get(key)
            if value is not None:
                inherited_evidence[key] = value

        message = (
            f"Evidence for '{current_phase}' inherited from this session's "
            f"best iteration ({prior_research_id} iter {prior_iteration}, "
            f"metric={prior_metric_name}={prior_metric}). Canonical config "
            f"matches — re-running would produce the identical metric in "
            f"~7 minutes; the prior evidence is carried forward instead."
        )

        synthetic_block = "\n".join(
            [
                "---",
                "status:             completed",
                f"primary_metric:     {prior_metric:.6f}"
                if isinstance(prior_metric, (int, float))
                else "primary_metric:     0.0",
                f"metric_name:        {prior_metric_name}",
                "direction:          higher_is_better",
                f"training_gates_passed: {str(prior_training_gates).lower()}",
                f"all_gates_passed:   {str(prior_all_gates).lower()}",
                f"search_phase:       {current_phase}",
                f"evidence_replayed_from_research_id: {prior_research_id}",
                f"evidence_replayed_from_iteration: {prior_iteration}",
                "---",
            ]
        )

        marker: Dict[str, Any] = {
            "status": "completed",
            "outcome": "evidence_replayed",
            "primary_metric": prior_metric,
            "metric_name": prior_metric_name,
            "training_gates_passed": prior_training_gates,
            "all_gates_passed": prior_all_gates,
            "decision": "keep",
            "search_phase": current_phase,
            "description": f"{message} (turn {turn})",
            "config_snapshot": config_snapshot,
            "canonical_config_hash": identity.get("canonical_config_hash"),
            "trial_identity": identity,
            "trial_identity_hash": identity_hash,
            # DM-1 audit fields — also the signal _is_synthetic_promotion_
            # iteration() uses to whitelist this marker.
            "evidence_replayed_from_research_id": prior_research_id,
            "evidence_replayed_from_iteration": prior_iteration,
            # Carry the source iteration's MLflow run id so phase
            # advancement's artifact-fingerprint check finds the right
            # training.log.
            "mlflow_run_id": prior_mlflow_run_id,
            **inherited_evidence,
        }

        return ToolExecutionResult(
            synthetic_block,
            meta={
                "policy_allowed": True,
                "policy_operation": "evidence_replay.linked",
                "returncode": 0,
                "timed_out": False,
                "trial_identity_hash": identity_hash,
                "evidence_replayed_from_research_id": prior_research_id,
                "evidence_replayed_from_iteration": prior_iteration,
            },
        ), marker

    async def _promotion_readiness_advisory(
        self,
        *,
        research_id: str,
        model_type: Optional[str],
        phase_state: Optional[Dict[str, Any]],
        actionable_blockers: Optional[Iterable[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Evaluate the current best candidate against the development gate
        bundle (pure, no HTTP) and return the agent-actionable model-quality
        blockers. Lets the agent fix issues like ``signal_saturation`` during
        the run instead of discovering them only at server-side promotion.
        """
        if model_type not in ("direction", "volatility"):
            return []
        try:
            from src.core.blocker_classifier import classify_blockers
            from src.core.development_gate_bundle import (
                evaluate_development_gate_bundle,
                load_gate_bundle,
            )

            best = await self._store.get_best_iteration(research_id)
            if not best:
                return []
            bundle = load_gate_bundle(settings.workspace_root)
            evaluation = evaluate_development_gate_bundle(
                bundle=bundle, model_type=str(model_type), best_iteration=best,
            )
            # ARC-011 review C2-4: skill-provided actionable set (manifest
            # ``blocker_classification.actionable_blockers``) overrides the
            # module-level default when supplied; None keeps the default.
            allowed_actionable = (
                set(actionable_blockers)
                if actionable_blockers is not None
                else _AGENT_ACTIONABLE_BLOCKERS
            )
            actionable = [
                code
                for code in evaluation.get("blockers", [])
                if code in allowed_actionable
            ]
            if not actionable:
                return []
            return classify_blockers(
                actionable,
                checks=evaluation.get("checks"),
                metrics_payload=self._parse_metrics_json(best.get("metrics_json")),
                phase_state=phase_state or {},
            )
        except Exception:  # pragma: no cover — advisory must never break the loop
            logger.debug(
                "Promotion readiness advisory failed for %s", research_id,
                exc_info=True,
            )
            return []

    async def _build_iteration_context_digest(
        self,
        *,
        config: ResearchConfig,
        total_cost: float,
    ) -> Optional[str]:
        """Build advisory context from persisted attempts for the next turn."""

        try:
            session = await self._store.get_session(config.id) or {}
            session = dict(session)
            session.setdefault("id", config.id)
            session.setdefault("instrument", config.subject_id)
            session.setdefault("timeframe", config.variant)
            session.setdefault("model_type", config.domain)
            session.setdefault("max_iterations", config.max_iterations)
            session.setdefault("max_budget_usd", config.max_budget_usd)
            session["total_api_cost_usd"] = total_cost
            iterations = await self._store.get_iterations(config.id)
            get_hpo = getattr(self._store, "get_hpo_studies", None)
            hpo_studies = await get_hpo(config.id) if get_hpo else []
            get_planned = getattr(self._store, "get_planned_trials", None)
            planned_trials = await get_planned(config.id) if get_planned else []
            # Read persisted phase state so the digest can surface the current
            # phase action and stall warning to the LLM on every turn.
            phase_state: Optional[Dict[str, Any]] = None
            phase_state_raw = session.get("phase_state_json")
            if phase_state_raw:
                try:
                    phase_state = json.loads(phase_state_raw)
                except (json.JSONDecodeError, TypeError):
                    phase_state = None
            # Fix B/C: cross-session summary surfaces canonical hashes other
            # sessions already explored AND server-side feature gaps so the
            # agent does not waste iterations re-discovering known no-ops.
            get_cross_session = getattr(
                self._store, "get_cross_session_iteration_summary", None,
            )
            prior_session_summary: List[Dict[str, Any]] = []
            if callable(get_cross_session):
                try:
                    prior_session_summary = await get_cross_session(
                        instrument=config.subject_id,
                        timeframe=config.variant,
                        model_type=config.domain,
                        exclude_research_id=config.id,
                    )
                except Exception as exc:  # pragma: no cover — fail-open
                    logger.warning(
                        "Cross-session summary unavailable for %s: %s",
                        config.id, exc,
                    )
                    prior_session_summary = []
            # ARC-011 review C2-4: skill-declared actionable blockers
            # (manifest ``blocker_classification``) override the module-level
            # defaults so a generative skill's readiness advisory does not
            # demand ML-only evidence keys.
            skill_runtime = getattr(self, "_session_skills", {}).get(config.id)
            actionable_blockers: Optional[Iterable[str]] = None
            if skill_runtime is not None:
                try:
                    bc = skill_runtime.blocker_classification()
                    if bc.get("actionable_blockers"):
                        actionable_blockers = bc["actionable_blockers"]
                except Exception as exc:  # pragma: no cover — fail-open
                    logger.warning(
                        "Research %s: blocker_classification() unavailable — "
                        "using default actionable blockers: %s", config.id, exc,
                    )
            promotion_readiness = await self._promotion_readiness_advisory(
                research_id=config.id,
                model_type=config.domain,
                phase_state=phase_state,
                actionable_blockers=actionable_blockers,
            )
            return build_iteration_context_digest(
                session=session,
                iterations=iterations,
                hpo_studies=hpo_studies,
                planned_trials=planned_trials,
                phase_state=phase_state,
                prior_session_summary=prior_session_summary,
                promotion_readiness=promotion_readiness,
                max_chars=settings.iteration_context_max_chars,
                recent_attempts=settings.iteration_context_recent_attempts,
            )
        except Exception as exc:
            logger.warning("Failed to build iteration context digest: %s", exc)
            return None

    async def _append_iteration_context_digest(
        self,
        *,
        config: ResearchConfig,
        tool_results: list[RequestBlock],
        turn_recorded_iteration: bool,
        total_cost: float,
    ) -> None:
        if not turn_recorded_iteration or not settings.iteration_context_enabled:
            return
        digest = await self._build_iteration_context_digest(
            config=config,
            total_cost=total_cost,
        )
        if digest:
            tool_results.append(TextBlock(text=digest))

    async def run(self, config: ResearchConfig) -> None:
        """Run the autonomous research loop for a single session."""
        research_id = config.id
        workspace = config.workspace_path or os.path.join(
            settings.runs_dir,
            f"{config.subject_id}_{config.variant}",
            config.domain,
        )

        # ARC-011 P1-027: materialize the per-session SkillRuntime. Every
        # domain-specific decision the loop used to make via
        # ``if config.domain == ...`` is reachable through ``skill.*``. The
        # transitional runtimes (P1-024..026) still delegate to the current
        # hardcoded code paths (model_type is still read *inside* them, so the
        # grep count does not drop yet — AC #2). Phase 2 replaces them with
        # manifest-driven runtimes.
        skill: SkillRuntime = materialize_skill_runtime(self, config)
        # ARC-011 review C2-3: per-skill governed-command extension. The
        # manifest's ``command_policy`` section (allowed_scripts /
        # allowed_executables / copyable_files / readable_files) merges into
        # the default policy sets inside ``evaluate_command_policy``; the
        # transitional runtimes return {} (parity with the hardcoded sets).
        skill_policy_extension = skill.command_policy_extension()
        # P2 per-workdir state: the skill's parallel-trial opt-in
        # (``execution.concurrency``, default 1 = strictly sequential,
        # byte-identical behavior). Defensive against stub runtimes in tests.
        try:
            execution_concurrency = int(skill.execution_concurrency() or 1)
        except Exception:  # noqa: BLE001 — a stub runtime must not kill the run
            execution_concurrency = 1
        # ARC-011 review C2-1/C2-4: keep the runtime reachable by research_id
        # for the out-of-loop helpers (_refresh_phase_state derives the phase
        # plan from it; the readiness advisory derives actionable blockers;
        # _try_auto_promote routes through the declared promotion target).
        # Mirrors the _session_providers / _session_models pattern above
        # (initialized in __init__, dropped in the run() finally).
        self._session_skills[config.id] = skill

        # ARC-011 P6-004: capture the session's current lock_epoch. This worker
        # owns the session for the run's lifetime (the advisory lock pins it),
        # so the captured value is the authoritative "as of dispatch" epoch.
        # If a stop/timeout lands on another worker during a command, that
        # transition bumps lock_epoch; the stale captured value no longer
        # matches and the store's conditional writes (add_iteration /
        # update_session with lock_epoch=) return 0 rows → the result is
        # discarded (the H4 stale-writer fix). SQLiteStateStore.get_session
        # returns no lock_epoch (column absent) → the field stays None and the
        # writes are unconditional (single-worker, no stale writers possible).
        try:
            _run_session = await self._store.get_session(research_id)
            self._session_epochs[research_id] = int(
                (_run_session or {}).get("lock_epoch") or 0
            )
        except Exception:  # noqa: BLE001 — capture must never block the run
            logger.debug("lock_epoch capture failed for %s", research_id, exc_info=True)

        # ARC-011 P4-002 / review C3: derive the per-session anti-forgery
        # nonce material. config.session_nonce is a 64-char hex string (32
        # bytes) generated out-of-band by the session_manager (never inside
        # the agent-readable manifest artifact — review C3). nonce_bytes is
        # passed to skill.parse_iteration (P4-003) and to the KV-block
        # verification path (review C3). The *env* delivery is built only
        # when the skill actually enforces signed metrics: injecting
        # AUTORESEARCH_SESSION_NONCE into every governed subprocess of every
        # session leaked the secret to any sanctioned command, and nothing
        # consumes it for non-enforcing skills (all ML skills today).
        skill_requires_signed = bool(
            getattr(skill, "requires_signed_metrics", False),
        )
        skill_nonce_field = str(
            getattr(skill, "nonce_field", None) or "server_nonce",
        )
        nonce_extra_env: Optional[Mapping[str, str]] = None
        nonce_bytes: Optional[bytes] = None
        if config.session_nonce:
            if skill_requires_signed:
                nonce_extra_env = {"AUTORESEARCH_SESSION_NONCE": config.session_nonce}
            try:
                nonce_bytes = bytes.fromhex(config.session_nonce)
            except ValueError:
                # Malformed nonce → treat as legacy (unverified), log loudly.
                logger.warning(
                    "Research %s: session_nonce is not valid hex — "
                    "downgrading to metrics_unverified", research_id,
                )
                nonce_bytes = None

        # ARC-011 P4-010: per-skill provider selection. If the skill manifest
        # declares a non-anthropic provider, construct it via the router and
        # store it per-session. _call_llm_with_retry and the insights path read
        # from _session_providers / _session_models (falling back to the default
        # self._provider / settings.anthropic_model).
        manifest = getattr(skill, "_manifest", None)
        if manifest is not None:
            llm_cfg = manifest.llm
            if llm_cfg.provider != "anthropic":
                # ARC-011 P4-009: validate the skill's required capabilities
                # against the provider's advertisement. build_provider raises
                # ProviderCapabilityMismatch (fail-closed) if the selected
                # provider cannot serve this skill — surfacing the misconfig at
                # session start, before any LLM call.
                self._session_providers[config.id] = build_provider(
                    llm_cfg.provider,
                    required_capabilities=RequiredCapabilities.from_llm_config(llm_cfg),
                )
                self._session_models[config.id] = llm_cfg.primary_model

        # Load system prompt. The assembly (claude.md + primer) mirrors
        # ``skill.system_prompt()`` exactly; the file reads are kept off the
        # event loop via asyncio.to_thread. The ``skill`` object is
        # materialized above so every later domain branch can reach through it.
        # ARC-011 review C2-2: sessions source the domain primer from the
        # packaged ``skills/<skill_id>/`` package the manifest was loaded from.
        primer = getattr(skill, "primer_filename", None) or "SKILL.md"
        skill_content = await asyncio.to_thread(
            _load_packaged_skill_md, config.skill_id, primer,
        )
        claude_md = await self._load_claude_md_async()
        system_prompt = f"{claude_md}\n\n---\n\n{skill_content}"

        # Build initial user message. Continuation sessions get the skill
        # runtime's resume prompt; fresh sessions its directive prompt.
        if config.resumed_from:
            parent_session = await self._store.get_session(config.resumed_from)
            parent_iterations = await self._store.get_iterations(
                config.resumed_from,
            )
            user_prompt = skill.resume_prompt(
                config, parent_session or {}, parent_iterations,
            )
        else:
            user_prompt = skill.directive_prompt(config)

        messages: list[Message] = [
            Message(role="user", content=user_prompt),
        ]

        iteration_count = 0
        # duplicate_rejected_count: audit records for duplicate training
        # attempts still increment iteration_count (so each record has a
        # unique number), but they do not consume the budget cap. The
        # effective count of real training attempts is
        # (iteration_count - duplicate_rejected_count).
        duplicate_rejected_count = 0
        # Track D1 (inert-change detection): primary metrics seen this
        # session. Deterministic training means a bit-identical metric from a
        # DIFFERENT config proves the changed knob does not affect the scored
        # artifact (e.g. Option-A-inert meta/stacking knobs, no-data feature
        # lanes, non-winner roster removals) — the agent gets told explicitly
        # instead of mistaking the result for evidence.
        seen_primary_metrics: set[float] = set()
        total_cost = 0.0
        last_input_tokens = 0  # Phase 2.2: rolling estimate for budget gate
        # Phase 5.4: abort the session if the agent keeps trying to run
        # commands the policy keeps rejecting — usually a sign of a bad
        # plan/loop, and burning budget on rejected calls is wasteful.
        policy_rejections_consecutive = 0
        _policy_aborted = False
        start_time = time.monotonic()
        max_turns = config.max_iterations * 10  # ~10 turns per iteration
        # ARC-011 P0-006: absolute monotonic soft deadline. Each governed
        # command's per-command timeout is capped at the budget remaining to
        # this deadline so the command_runner's own psutil kill path fires at
        # the session boundary (cancelling asyncio.to_thread cannot interrupt
        # the worker thread). The hard wait_for in _run_and_cleanup is the
        # backstop; a cancel-handler reap covers operator stop.
        _soft_timeout_s = (
            config.timeout_s if config.timeout_s > 0
            else settings.experiment_timeout_s
        )
        _command_deadline_mono = start_time + _soft_timeout_s

        # Agent log capture
        agent_log = AgentLogWriter(
            Path(workspace) / "agent_log.jsonl", research_id,
            pipeline_id=config.pipeline_id,
            phase=config.domain if config.pipeline_id else None,
        )
        await agent_log.append(
            "system",
            f"Research session started: {config.subject_id} {config.variant} "
            f"{config.domain} tag={config.tag} max_iter={config.max_iterations}",
        )
        await self._refresh_phase_state(research_id)

        try:
            _timed_out = False  # ML-62: track timeout vs normal completion
            for turn in range(max_turns):
                # Check stop/pause conditions. ARC-011 P6-004: the cross-worker
                # variant reads DB-side stop intent so a stop on another worker
                # is observed here on the owning worker's turn poll.
                if await self._should_stop_cross_worker(research_id):
                    logger.info("Research %s: stop requested", research_id)
                    await agent_log.append("system", "Stop requested by user", turn=turn)
                    break

                await self._wait_while_paused(research_id)

                if await self._should_stop_cross_worker(research_id):
                    break

                if _policy_aborted:
                    # Phase 5.4: bail out as soon as the rejection counter
                    # tripped on the previous turn.
                    break

                # Check timeout (per-session override or server default)
                elapsed = time.monotonic() - start_time
                _timeout = (
                    config.timeout_s
                    if config.timeout_s > 0
                    else settings.experiment_timeout_s
                )
                if elapsed > _timeout:
                    logger.info("Research %s: timeout after %.0fs", research_id, elapsed)
                    await agent_log.append("system", f"Timeout after {elapsed:.0f}s", turn=turn)
                    _timed_out = True
                    break

                # Phase 2.2: pre-spend cost gate. Refuse to call Claude if
                # we are already over budget OR if the worst-case spend on
                # the next turn would exceed the budget. ``last_input_tokens``
                # tracks the last turn's input size as a proxy for the next
                # turn's input prompt; for the first turn we fall back to a
                # conservative max-context estimate.
                projected_input = max(last_input_tokens, 32_000)
                projected_turn_cost = (
                    projected_input * _CLAUDE_INPUT_USD_PER_TOKEN
                    + _CLAUDE_MAX_OUTPUT_TOKENS * _CLAUDE_OUTPUT_USD_PER_TOKEN
                )
                if total_cost >= config.max_budget_usd or (
                    total_cost + projected_turn_cost > config.max_budget_usd
                ):
                    logger.info(
                        "Research %s: budget gate triggered "
                        "(spent=$%.4f, projected_next=$%.4f, cap=$%.4f)",
                        research_id, total_cost, projected_turn_cost,
                        config.max_budget_usd,
                    )
                    await agent_log.append(
                        "system",
                        f"Budget cap reached: spent=${total_cost:.4f}, "
                        f"projected_next=${projected_turn_cost:.4f}, "
                        f"cap=${config.max_budget_usd:.4f}",
                        turn=turn,
                    )
                    break

                # Call Claude (ML-68: with retry + context compaction)
                _api_messages = self._compact_messages(
                    messages, keep_recent=settings.context_compaction_threshold // 2,
                )
                response = await self._call_llm_with_retry(
                    messages=_api_messages,
                    system_prompt=system_prompt,
                    research_id=research_id,
                    agent_log=agent_log,
                    turn=turn,
                    remaining_budget_s=max(0.0, _timeout - elapsed),
                )

                # Track cost (approximate from usage). response.usage is a
                # normalized Usage (always present post-P1-002); the truthiness
                # guard is dropped since Usage is a frozen dataclass (always truthy).
                last_input_tokens = response.usage.input_tokens
                turn_cost = (
                    response.usage.input_tokens * _CLAUDE_INPUT_USD_PER_TOKEN
                    + response.usage.output_tokens * _CLAUDE_OUTPUT_USD_PER_TOKEN
                )
                total_cost += turn_cost
                # P3: persist the running spend to the session row each turn so
                # total_api_cost_usd is visible mid-run (UI/API + any external
                # budget check) and survives a crash — the DB previously stayed
                # $0 until completion. Best-effort: a transient DB error must not
                # abort the research loop. The completion write remains the
                # authoritative final value.
                if turn_cost > 0:
                    try:
                        await self._store.update_session(
                            research_id,
                            total_api_cost_usd=round(total_cost, 4),
                        )
                    except Exception as exc:  # pragma: no cover — fail-open
                        logger.warning(
                            "Research %s: mid-run cost persist failed: %s",
                            research_id, exc,
                        )

                # Process response content blocks
                assistant_content = response.content
                tool_results = []
                agent_text = ""
                turn_recorded_iteration = False
                turn_ran_training_command = False
                # P2 per-workdir state: 1-based index of bash commands within
                # this turn (all bash blocks counted — deterministic trial
                # naming even when only some are trial-eligible).
                turn_bash_seq = 0

                for block in assistant_content:
                    if isinstance(block, TextBlock):
                        agent_text += block.text
                        if block.text.strip():
                            logger.info(
                                "Research %s turn %d: text=%s",
                                research_id, turn, block.text[:200],
                            )
                            await agent_log.append("text", block.text, turn=turn)
                    elif isinstance(block, ToolUseBlock):
                        logged_input = block.input
                        if block.name == "bash" and isinstance(block.input, dict):
                            logged_input = {
                                **block.input,
                                "command": redact_sensitive_text(
                                    str(block.input.get("command", ""))
                                ),
                            }
                        logger.info(
                            "Research %s turn %d: tool=%s input=%s",
                            research_id, turn, block.name,
                            str(logged_input)[:200],
                        )
                        await agent_log.append(
                            "tool_call", block.name, turn=turn,
                            meta={"tool_id": block.id, "input": logged_input},
                        )

                        raw_command_for_tool = (
                            str(block.input.get("command", ""))
                            if isinstance(block.input, dict)
                            else ""
                        )

                        # P2 per-workdir state: build this command's trial
                        # context BEFORE the pre-snapshot so the snapshot
                        # reads the staged trial copy (the exact config the
                        # subprocess will see). concurrency==1 (default)
                        # keeps trial_dir=None — behavior byte-identical.
                        _trial_ctx: TrialContext | None = None
                        if (
                            isinstance(block.input, dict)
                            and block.name == "bash"
                        ):
                            turn_bash_seq += 1
                            _trial_ctx = build_trial_context(
                                research_id=research_id,
                                turn=turn,
                                seq=turn_bash_seq,
                                session_workspace=workspace,
                                command=raw_command_for_tool,
                                allowed_scripts=(
                                    skill_policy_extension.get("allowed_scripts")
                                ),
                                execution_concurrency=execution_concurrency,
                            )

                        # Pre-snapshot: capture the config file a command
                        # references BEFORE running it, so the attempt has an
                        # immutable config record preserved even on crash or
                        # timeout.
                        _pending_snapshot: Optional[str] = None
                        if (
                            isinstance(block.input, dict)
                            and block.name == "bash"
                        ):
                            snapshot_path = _config_snapshot_path_from_command(
                                raw_command_for_tool,
                                settings.workspace_root,
                                workspace,
                                base_dir=(
                                    _trial_ctx.workdir
                                    if _trial_ctx is not None and _trial_ctx.is_trial
                                    else None
                                ),
                            )
                            if snapshot_path:
                                try:
                                    _pending_snapshot = Path(snapshot_path).read_text(
                                        encoding="utf-8",
                                    )
                                except OSError:
                                    logger.warning(
                                        "Research %s: could not pre-snapshot "
                                        "%s before the run",
                                        research_id,
                                        snapshot_path,
                                    )

                        duplicate_rejection: Optional[ToolExecutionResult] = None
                        duplicate_marker: Optional[Dict[str, Any]] = None
                        if (
                            isinstance(block.input, dict)
                            and block.name == "bash"
                        ):
                            _phase_for_dedup = self._active_phase_from_marker_or_session(
                                {}, await self._store.get_session(config.id),
                            )
                            (
                                duplicate_rejection,
                                duplicate_marker,
                            ) = await self._guard_duplicate_training_attempt(
                                config=config,
                                turn=turn,
                                command=raw_command_for_tool,
                                config_snapshot=_pending_snapshot,
                                current_phase=_phase_for_dedup,
                            )

                        runtime_command_id: Optional[int] = None
                        command_started_at: Optional[float] = None
                        if (
                            duplicate_rejection is None
                            and isinstance(block.input, dict)
                            and block.name == "bash"
                        ):
                            _rc_metadata: Dict[str, Any] = {"tool_id": block.id}
                            if _trial_ctx is not None and _trial_ctx.is_trial:
                                # P2 per-workdir provenance: which isolated
                                # trial directory this command ran in.
                                _rc_metadata["trial_dir"] = _trial_ctx.trial_dir
                                _rc_metadata["trial_seq"] = _trial_ctx.seq
                            runtime_command = await self._store.record_runtime_command(
                                research_id=research_id,
                                turn=turn,
                                tool_name=block.name,
                                command=redact_sensitive_text(raw_command_for_tool),
                                timeout_s=min(
                                    self._effective_tool_timeout(block.input),
                                    max(0, int(_command_deadline_mono - time.monotonic())),
                                ),
                                metadata=_rc_metadata,
                            )
                            runtime_command_id = runtime_command["id"]

                        if duplicate_rejection is not None:
                            duplicate_marker = duplicate_marker or {}
                            _is_baseline_link = (
                                duplicate_rejection.meta.get(
                                    "policy_operation"
                                ) == "baseline.linked"
                            )
                            iteration_count += 1
                            if not _is_baseline_link:
                                duplicate_rejected_count += 1
                            await self._record_iteration(
                                research_id, iteration_count,
                                duplicate_marker, total_cost,
                                workspace=workspace,
                                turn=turn,
                                command=redact_sensitive_text(raw_command_for_tool),
                            )
                            turn_recorded_iteration = True
                            tool_execution = duplicate_rejection
                            if _is_baseline_link:
                                logger.info(
                                    "Research %s turn %d: linked baseline "
                                    "from %s iteration %s (metric=%s)",
                                    research_id, turn,
                                    duplicate_marker.get(
                                        "baseline_linked_from_research_id"
                                    ),
                                    duplicate_marker.get(
                                        "baseline_linked_from_iteration"
                                    ),
                                    duplicate_marker.get("primary_metric"),
                                )
                        else:
                            command_started_at = time.time()
                            output_callback = None
                            if block.name == "bash":
                                output_callback = self._make_command_output_callback(
                                    agent_log=agent_log,
                                    loop=asyncio.get_running_loop(),
                                    turn=turn,
                                    runtime_command_id=runtime_command_id,
                                )
                            # ARC-011 review C3: the nonce env is narrowed
                            # per command — only the skill's own declared
                            # scripts (its eval) receive the secret.
                            _bash_cmd = (
                                block.input.get("command")
                                if isinstance(block.input, dict)
                                else None
                            )
                            tool_execution = await asyncio.to_thread(
                                _execute_tool,
                                block.name,
                                block.input,
                                settings.workspace_root,
                                workspace,
                                output_callback,
                                command_deadline_mono=_command_deadline_mono,
                                proc_registry=self._command_procs,
                                research_id=research_id,
                                extra_env=_nonce_env_for_command(
                                    nonce_extra_env, _bash_cmd,
                                    skill_policy_extension,
                                ),
                                policy_extension=skill_policy_extension,
                                cwd=(
                                    _trial_ctx.trial_dir
                                    if _trial_ctx is not None and _trial_ctx.is_trial
                                    else None
                                ),
                            )
                        tool_result = tool_execution.content
                        tool_meta = tool_execution.meta
                        if (
                            _trial_ctx is not None
                            and _trial_ctx.is_trial
                            and isinstance(tool_meta, dict)
                        ):
                            # P2 per-workdir provenance flows into the runtime
                            # command record, the marker, and the recorded
                            # iteration's metrics (via _attach_runtime_command_
                            # metadata consumers).
                            tool_meta = dict(tool_meta)
                            tool_meta["trial_dir"] = _trial_ctx.trial_dir
                            tool_meta["trial_seq"] = _trial_ctx.seq
                        if runtime_command_id is not None:
                            tool_meta = dict(tool_meta)
                            tool_meta["runtime_command_id"] = runtime_command_id
                            await self._store.finish_runtime_command(
                                runtime_command_id,
                                status=self._runtime_command_status(tool_meta),
                                returncode=tool_meta.get("returncode"),
                                timed_out=bool(tool_meta.get("timed_out")),
                                output_preview=tool_result[:5000],
                                metadata=tool_meta,
                            )
                        logger.info(
                            "Research %s turn %d: tool=%s result=%s",
                            research_id, turn, block.name,
                            tool_result[:200],
                        )
                        if (
                            block.name == "bash"
                            and tool_meta.get("policy_allowed") is False
                        ):
                            await self._record_command_policy_rejection(
                                config=config,
                                turn=turn,
                                command=str(block.input.get("command", "")),
                                tool_meta=tool_meta,
                            )
                            policy_rejections_consecutive += 1
                            if policy_rejections_consecutive >= _MAX_CONSECUTIVE_POLICY_REJECTIONS:
                                _policy_aborted = True
                                logger.warning(
                                    "Research %s: aborting after %d "
                                    "consecutive policy rejections",
                                    research_id,
                                    policy_rejections_consecutive,
                                )
                                await agent_log.append(
                                    "system",
                                    f"Aborting: {policy_rejections_consecutive} "
                                    "consecutive command-policy rejections. "
                                    "Operator review required.",
                                    turn=turn,
                                )
                        elif (
                            block.name == "bash"
                            and tool_meta.get("policy_allowed") is True
                        ):
                            policy_rejections_consecutive = 0
                        await agent_log.append(
                            "tool_result", tool_result[:5000], turn=turn,
                            meta={
                                "tool_id": block.id,
                                "tool_name": block.name,
                                **tool_meta,
                            },
                        )
                        # Track D2: digest large bash outputs before they enter
                        # the agent's context — the raw `tool_result` variable
                        # stays untouched for the server-side marker parsing
                        # below (ITERATION_RESULT / `---` metrics / HPO study).
                        agent_visible_result = tool_result
                        if (
                            block.name == "bash"
                            and len(tool_result) > settings.agent_output_digest_max_chars > 0
                        ):
                            _full_log_rel = None
                            try:
                                _log_dir = Path(workspace) / "command_logs"
                                _log_dir.mkdir(parents=True, exist_ok=True)
                                _log_file = _log_dir / f"turn_{turn:03d}_{block.id[-8:]}.log"
                                _log_file.write_text(tool_result, encoding="utf-8")
                                _full_log_rel = str(
                                    _log_file.relative_to(settings.workspace_root)
                                ) if str(_log_file).startswith(
                                    str(settings.workspace_root)
                                ) else str(_log_file)
                            except Exception as _log_exc:  # noqa: BLE001
                                logger.debug("Full-log persist failed: %s", _log_exc)
                            agent_visible_result = digest_command_output(
                                tool_result,
                                max_chars=settings.agent_output_digest_max_chars,
                                full_log_path=_full_log_rel,
                            )
                            logger.info(
                                "Research %s turn %d: digested bash output "
                                "%d → %d chars",
                                research_id, turn,
                                len(tool_result), len(agent_visible_result),
                            )
                        tool_results.append(ToolResultBlock(
                            tool_use_id=block.id,
                            content=agent_visible_result,
                        ))
                        _cmd_str = redact_sensitive_text(
                            str(block.input.get("command", ""))
                        )
                        # ARC-011 review C4 (P4-016): a skill's declared
                        # scripts are that skill's iteration-producing
                        # commands — a relayed marker is backed by a real run.
                        if block.name == "bash" and any(
                            str(script) in _cmd_str
                            for script in (
                                skill_policy_extension.get("allowed_scripts") or ()
                            )
                        ):
                            turn_ran_training_command = True

                        # Universal detection: scan bash output for
                        # --- delimited metrics blocks. This works regardless
                        # of LLM model since it's parsing deterministic
                        # Python script output.
                        elif (
                            block.name == "bash"
                            and not turn_recorded_iteration
                            and "---" in tool_result
                        ):
                            metrics = parse_prepare_output(tool_result)
                            # ARC-011 review C3: this auto-detect path
                            # previously bypassed W11 verification entirely
                            # (parse_prepare_output takes no nonce) — any
                            # bash output containing a `---` block was
                            # recorded as an iteration even for enforced
                            # skills. Route the parsed block through the
                            # four-state _verify_nonce check first.
                            _kv_result = (
                                metrics.to_dict()
                                if (
                                    metrics.primary_metric is not None
                                    and metrics.status in ("completed", "success")
                                )
                                else None
                            )
                            if _kv_result is not None:
                                _kv_result = await self._verify_kv_metrics(
                                    research_id,
                                    _kv_result,
                                    turn=turn,
                                    agent_log=agent_log,
                                    session_nonce=nonce_bytes,
                                    nonce_field=skill_nonce_field,
                                    requires_signed=skill_requires_signed,
                                    source="bash_output",
                                    pipeline_id=config.pipeline_id,
                                )
                            if _kv_result is not None:
                                iteration_count += 1
                                marker_from_tool = _kv_result
                                self._attach_runtime_command_metadata(
                                    marker_from_tool, tool_meta,
                                )
                                # Determine keep/discard by comparing against
                                # current session best — not just gates.
                                decision = await self._infer_decision(
                                    research_id,
                                    metrics.primary_metric,
                                    metrics.training_gates_passed,
                                )
                                marker_from_tool["decision"] = decision
                                # Attach the pre-captured snapshot so the DB
                                # is the sole source of truth for the config.
                                marker_from_tool["config_snapshot"] = _pending_snapshot
                                marker_from_tool["description"] = (
                                    f"Auto-detected from experiment output "
                                    f"(turn {turn})"
                                )
                                await self._record_iteration(
                                    research_id, iteration_count,
                                    marker_from_tool, total_cost,
                                    workspace=workspace,
                                    turn=turn,
                                    command=_cmd_str,
                                )
                                turn_recorded_iteration = True
                                logger.info(
                                    "Research %s turn %d: auto-detected "
                                    "iteration %d from bash output "
                                    "(%s=%.4f, training_gates=%s)",
                                    research_id, turn, iteration_count,
                                    metrics.metric_name,
                                    metrics.primary_metric,
                                    metrics.training_gates_passed,
                                )
                                # Track D1: bit-identical metric from a new
                                # config ⇒ the changed knob is INERT for the
                                # scored artifact. Tell the agent explicitly —
                                # otherwise it reads the rerun as evidence and
                                # keeps probing dead dimensions (observed:
                                # Option-A meta/stacking knobs, no-data
                                # lanes, non-winner roster removals).
                                _metric_val = float(metrics.primary_metric)
                                if (
                                    _metric_val in seen_primary_metrics
                                    and tool_results
                                    and isinstance(tool_results[-1], ToolResultBlock)
                                ):
                                    last = tool_results[-1]
                                    tool_results[-1] = ToolResultBlock(
                                        tool_use_id=last.tool_use_id,
                                        content=(
                                            str(last.content)
                                            + "\n\n⚠️ INERT CHANGE DETECTED: this run "
                                            f"reproduced an earlier iteration's metric "
                                            f"BIT-IDENTICALLY ({_metric_val:.6f}). "
                                            "Training is deterministic — an identical "
                                            "metric from a different config means the "
                                            "knob(s) you changed do NOT affect the "
                                            "scored artifact (e.g. Option-A-inert "
                                            "meta/stacking knobs, feature lanes with "
                                            "no data, removing non-winning roster "
                                            "members). Do NOT count this as evidence; "
                                            "switch to a different search dimension."
                                        ),
                                    )
                                    await agent_log.append(
                                        "system",
                                        f"Inert-change note injected (metric "
                                        f"{_metric_val:.6f} repeated)",
                                        turn=turn,
                                    )
                                seen_primary_metrics.add(_metric_val)
                            elif (
                                metrics.status in (
                                    "crash", "timeout", "failed", "error",
                                    "pruned",
                                )
                            ):
                                # Record failed attempts as first-class discard
                                # iterations so the full audit trail is in DB
                                # and the agent cannot revisit the same invalid
                                # config region without a recorded trace.
                                iteration_count += 1
                                crash_marker = metrics.to_dict()
                                self._attach_runtime_command_metadata(
                                    crash_marker, tool_meta,
                                )
                                crash_marker["decision"] = "discard"
                                crash_marker["config_snapshot"] = _pending_snapshot
                                crash_marker["description"] = (
                                    f"Failed ({metrics.status}) — "
                                    f"auto-detected from experiment output "
                                    f"(turn {turn})"
                                )
                                await self._record_iteration(
                                    research_id, iteration_count,
                                    crash_marker, total_cost,
                                    workspace=workspace,
                                    turn=turn,
                                    command=_cmd_str,
                                )
                                turn_recorded_iteration = True
                                logger.info(
                                    "Research %s turn %d: recorded failed "
                                    "attempt %d (%s) from bash output",
                                    research_id, turn, iteration_count,
                                    metrics.status,
                                )

                        # Fallback: if bash timed out or the output was
                        # digested, check for a marker file declared by the
                        # skill's output_parser.fallback section.
                        if (
                            block.name == "bash"
                            and not turn_recorded_iteration
                        ):
                            marker_text = await self._read_marker_file_async(
                                config, min_mtime=command_started_at,
                                trial_dir=(
                                    _trial_ctx.trial_dir
                                    if _trial_ctx is not None and _trial_ctx.is_trial
                                    else None
                                ),
                            )
                            _rc_for_marker = tool_meta.get("returncode")
                            _command_succeeded = (
                                _rc_for_marker is None
                                or (
                                    isinstance(_rc_for_marker, int)
                                    and _rc_for_marker == 0
                                )
                            )
                            if marker_text:
                                metrics = parse_prepare_output(marker_text)
                                # ARC-011 review C3: same W11 verification
                                # as the bash auto-detect path — the marker
                                # file is written by the sanctioned script
                                # and must carry the echoed nonce for
                                # enforced skills.
                                _file_result = (
                                    metrics.to_dict()
                                    if (
                                        _command_succeeded
                                        and metrics.primary_metric is not None
                                        and metrics.status in ("completed", "success")
                                    )
                                    else None
                                )
                                if _file_result is not None:
                                    _file_result = await self._verify_kv_metrics(
                                        research_id,
                                        _file_result,
                                        turn=turn,
                                        agent_log=agent_log,
                                        session_nonce=nonce_bytes,
                                        nonce_field=skill_nonce_field,
                                        requires_signed=skill_requires_signed,
                                        source="marker_file",
                                        pipeline_id=config.pipeline_id,
                                    )
                                if _file_result is not None:
                                    iteration_count += 1
                                    marker_from_file = _file_result
                                    self._attach_runtime_command_metadata(
                                        marker_from_file, tool_meta,
                                    )
                                    decision = await self._infer_decision(
                                        research_id,
                                        metrics.primary_metric,
                                        metrics.training_gates_passed,
                                    )
                                    marker_from_file["decision"] = decision
                                    # Attach snapshot for marker-file path too.
                                    marker_from_file["config_snapshot"] = _pending_snapshot
                                    marker_from_file["description"] = (
                                        f"Auto-detected from marker file "
                                        f"(turn {turn})"
                                    )
                                    await self._record_iteration(
                                        research_id, iteration_count,
                                        marker_from_file, total_cost,
                                        workspace=workspace,
                                        turn=turn,
                                        command=_cmd_str,
                                    )
                                    turn_recorded_iteration = True
                                    logger.info(
                                    "Research %s turn %d: auto-detected "
                                    "iteration %d from marker file "
                                    "(%s=%.4f, training_gates=%s)",
                                        research_id, turn, iteration_count,
                                        metrics.metric_name,
                                        metrics.primary_metric,
                                        metrics.training_gates_passed,
                                    )
                                elif metrics.status in (
                                    "crash", "timeout", "failed", "error",
                                    "pruned",
                                ):
                                    iteration_count += 1
                                    crash_marker = metrics.to_dict()
                                    self._attach_runtime_command_metadata(
                                        crash_marker, tool_meta,
                                    )
                                    crash_marker["decision"] = "discard"
                                    crash_marker["config_snapshot"] = _pending_snapshot
                                    crash_marker["description"] = (
                                        f"Failed ({metrics.status}) — "
                                        f"auto-detected from marker file "
                                        f"(turn {turn})"
                                    )
                                    await self._record_iteration(
                                        research_id, iteration_count,
                                        crash_marker, total_cost,
                                        workspace=workspace,
                                        turn=turn,
                                        command=_cmd_str,
                                    )
                                    turn_recorded_iteration = True
                                    logger.info(
                                        "Research %s turn %d: recorded failed "
                                        "attempt %d (%s) from marker file",
                                        research_id, turn, iteration_count,
                                        metrics.status,
                                    )

                        if (
                            block.name == "bash"
                            and not turn_recorded_iteration
                        ):
                            failed_status = self._infer_failed_attempt_status(
                                tool_result
                            )
                            if failed_status:
                                iteration_count += 1
                                failed_marker = {
                                    "status": failed_status,
                                    "primary_metric": None,
                                    "metric_name": None,
                                    "training_gates_passed": False,
                                    "all_gates_passed": False,
                                    "decision": "discard",
                                    "description": (
                                        f"Failed ({failed_status}) — "
                                        f"server-detected training command "
                                        f"failure (turn {turn})"
                                    ),
                                    "config_snapshot": _pending_snapshot,
                                }
                                self._attach_runtime_command_metadata(
                                    failed_marker, tool_meta,
                                )
                                await self._record_iteration(
                                    research_id, iteration_count,
                                    failed_marker, total_cost,
                                    workspace=workspace,
                                    turn=turn,
                                    command=_cmd_str,
                                )
                                turn_recorded_iteration = True
                                logger.info(
                                    "Research %s turn %d: recorded failed "
                                    "attempt %d (%s) from command status",
                                    research_id, turn, iteration_count,
                                    failed_status,
                                )

                # Secondary: check for explicit ITERATION_RESULT: markers
                # in agent text. If the model emits one, it may carry richer
                # fields (decision, description) so we prefer it over the
                # auto-detected one.  If this turn already recorded an
                # iteration from bash output, overwrite it with the richer
                # marker instead of creating a duplicate.
                #
                # ARC-011 P4-003: route through ``skill.parse_iteration`` (not
                # the bare ``parse_iteration_marker`` facade) so the W11 nonce
                # is verified for skills with ``require_signed_metrics=true``.
                # For ML skills (default false) and the transitional runtimes,
                # parse_iteration returns the same result the facade did, so
                # the X-002 parity fixtures stay byte-identical. A forged
                # marker (wrong/missing nonce) returns None here → the existing
                # ``if marker`` branch treats it as "no marker" and the
                # iteration is not recorded.
                if agent_text:
                    marker = skill.parse_iteration(
                        agent_text, session_nonce=nonce_bytes,
                    )
                    if marker:
                        # ARC-011 P4-003: record the verification outcome so a
                        # metrics_verified/unverified row is auditable. For
                        # enforced skills the key is set by _verify_nonce; its
                        # absence means the skill runs unverified (legacy /
                        # require_signed_metrics=false).
                        if "metrics_verification" in marker:
                            await self._store.record_audit_event(
                                actor_id="autoresearch-agent",
                                action="metrics.verify",
                                research_id=research_id,
                                pipeline_id=config.pipeline_id,
                                request_metadata={
                                    "turn": turn,
                                    "iteration": iteration_count,
                                    "outcome": marker["metrics_verification"],
                                },
                                outcome="success",
                            )
                        if turn_recorded_iteration:
                            # Overwrite last iteration with richer marker
                            await self._attach_consistency_report(
                                research_id, iteration_count, marker,
                            )
                            await self._store.update_iteration(
                                research_id, iteration_count, marker,
                            )
                            await self._refresh_phase_state(research_id)
                            logger.info(
                                "Research %s turn %d: overwrote iteration "
                                "%d with explicit ITERATION_RESULT marker",
                                research_id, turn, iteration_count,
                            )
                        elif not turn_ran_training_command:
                            # Reject ITERATION_RESULT markers that aren't backed
                            # by a real training run this turn. The agent
                            # sometimes emits markers after cp reverts or yaml
                            # edits, which inflates iteration counts and
                            # destabilizes phase computation.
                            logger.info(
                                "Research %s turn %d: ignoring "
                                "ITERATION_RESULT marker — no training "
                                "command was executed this turn",
                                research_id, turn,
                            )
                            await agent_log.append(
                                "system",
                                (
                                    "ITERATION_RESULT marker was ignored: "
                                    "no experiment command ran this turn. "
                                    "Emit markers only after a real "
                                    "experiment run."
                                ),
                                turn=turn,
                            )
                        else:
                            iteration_count += 1
                            # ARC-011 review C4 (P4-016): a non-ML eval
                            # marker carries no ``decision`` (the skill's
                            # scorer has no session-best context) — infer it
                            # server-side exactly like the KV auto-detect
                            # path, so ``best_iteration`` advances on
                            # gates-passing improvements. ML agents that
                            # include a decision in their richer marker are
                            # unaffected (presence-checked).
                            if not marker.get("decision"):
                                marker["decision"] = await self._infer_decision(
                                    research_id,
                                    marker.get("primary_metric"),
                                    marker.get("training_gates_passed"),
                                )
                            await self._record_iteration(
                                research_id, iteration_count, marker,
                                total_cost,
                                workspace=workspace,
                                turn=turn,
                            )
                    else:
                        # ARC-011 P4-003: marker was rejected. Distinguish a
                        # forged marker (a raw ITERATION_RESULT: block existed
                        # but failed nonce verification → require_signed_metrics
                        # is true) from a genuinely absent one. Only enforced
                        # skills can return None for a present marker, so this
                        # audit fires exclusively on real forgery attempts.
                        raw_marker_present = parse_iteration_marker(agent_text) is not None
                        if raw_marker_present:
                            logger.warning(
                                "Research %s turn %d: rejected forged "
                                "ITERATION_RESULT marker (nonce missing or "
                                "mismatch) — not recorded",
                                research_id, turn,
                            )
                            await agent_log.append(
                                "system",
                                (
                                    "ITERATION_RESULT marker was rejected: the "
                                    "anti-forgery nonce was missing or did not "
                                    "match. Emit markers only from the sanctioned "
                                    "eval script, which receives the nonce via the "
                                    "AUTORESEARCH_SESSION_NONCE environment variable."
                                ),
                                turn=turn,
                            )
                            try:
                                await self._store.record_audit_event(
                                    actor_id="autoresearch-agent",
                                    action="metrics.forged",
                                    research_id=research_id,
                                    pipeline_id=config.pipeline_id,
                                    request_metadata={"turn": turn},
                                    outcome="failure",
                                    error_message=(
                                        "Iteration marker rejected: nonce missing "
                                        "or mismatch (forged)"
                                    ),
                                )
                            except Exception as exc:
                                logger.warning(
                                    "Research %s: failed to record metrics_forged "
                                    "audit event: %s", research_id, exc,
                                )

                # Check if we've hit max iterations (real attempts only —
                # duplicate-rejected audit records do not consume budget).
                effective_iteration_count = iteration_count - duplicate_rejected_count
                if effective_iteration_count >= config.max_iterations:
                    logger.info(
                        "Research %s: max iterations (%d) reached "
                        "(effective=%d, total_records=%d, rejected=%d)",
                        research_id, config.max_iterations,
                        effective_iteration_count,
                        iteration_count,
                        duplicate_rejected_count,
                    )
                    break

                # If the model stopped (END_TURN) and no tool calls → done
                if response.stop_reason == StopReason.END_TURN and not tool_results:
                    terminate_request = self._extract_terminate_request(agent_text)
                    if terminate_request:
                        # DM-2: defer TERMINATE_REQUEST when the agent is
                        # walking away with budget still on the table AND
                        # the session-best metric is fresh (improvement
                        # within the last 5 iterations). Observed on
                        # res_be66790e192e: agent emitted TERMINATE_REQUEST
                        # at iter 12/50 (24% budget), best_gap=5 — only 5
                        # distinct hypotheses tried before quitting. The
                        # 50% floor is a hard ceiling — once half the
                        # budget is spent, termination is honored
                        # unconditionally regardless of gap.
                        deferral = await self._should_defer_terminate(
                            research_id=research_id,
                            iteration_count=iteration_count,
                            duplicate_rejected_count=duplicate_rejected_count,
                            config=config,
                        )
                        if deferral is not None:
                            logger.info(
                                "Research %s turn %d: "
                                "terminate_request_deferred — %s",
                                research_id, turn, deferral["reason"],
                            )
                            await agent_log.append(
                                "system",
                                (
                                    "Terminate request deferred: "
                                    f"{deferral['reason']}"
                                ),
                                turn=turn,
                            )
                            messages.append(Message(
                                role="assistant",
                                content=assistant_content,
                            ))
                            messages.append(Message(
                                role="user",
                                content=[TextBlock(text=deferral["text"])],
                            ))
                            continue
                        logger.info(
                            "Research %s turn %d: honoring TERMINATE_REQUEST",
                            research_id, turn,
                        )
                        await agent_log.append(
                            "system",
                            f"Terminate request accepted: {terminate_request[:1800]}",
                            turn=turn,
                        )
                        # Mark the session so _try_auto_promote knows this
                        # was an explicit, justified termination (vs. a
                        # crash, timeout, or end_turn-without-justification).
                        # Incomplete iteration-count phases are waived for
                        # promotion when this flag is set AND baseline is
                        # complete — hard gates (training, calibration,
                        # parity) still run via promoter.preview().
                        try:
                            await self._store.update_session(
                                research_id,
                                terminate_request_received=1,
                                terminate_request_body=terminate_request[:4000],
                            )
                        except Exception as exc:
                            logger.warning(
                                "Research %s: failed to persist "
                                "terminate_request flag: %s",
                                research_id, exc,
                            )
                        break

                    # F1: refuse to terminate while the phase plan has
                    # incomplete phases AND the run still has both budget and
                    # iteration headroom. The agent self-terminated run
                    # res_0efe45aaa28f at turn 305 having spent only $16.49
                    # of $100 with 158 iterations remaining and the phase
                    # plan still on tabular_sweeps. Inject a continuation
                    # nudge instead of breaking.
                    continuation_kick = await self._build_phase_continuation_kick(
                        research_id=research_id,
                        iteration_count=(iteration_count - duplicate_rejected_count),
                        total_cost=total_cost,
                        config=config,
                    )
                    if continuation_kick is None:
                        logger.info(
                            "Research %s: agent ended conversation",
                            research_id,
                        )
                        break
                    logger.info(
                        "Research %s turn %d: rejecting end_turn — %s",
                        research_id, turn, continuation_kick["reason"],
                    )
                    messages.append(Message(
                        role="assistant",
                        content=assistant_content,
                    ))
                    messages.append(Message(
                        role="user",
                        content=[TextBlock(text=continuation_kick["text"])],
                    ))
                    continue

                # Append assistant message and tool results
                messages.append(Message(role="assistant", content=assistant_content))

                if tool_results:
                    await self._append_iteration_context_digest(
                        config=config,
                        tool_results=tool_results,
                        turn_recorded_iteration=turn_recorded_iteration,
                        total_cost=total_cost,
                    )
                    # Inject orchestrator iteration count so the agent's
                    # numbering stays in sync with the DB record. The budget
                    # cap uses the effective count (real attempts only) —
                    # duplicate-rejected records consume a record number but
                    # not a budget slot.
                    _effective_for_msg = iteration_count - duplicate_rejected_count
                    tool_results.append(TextBlock(
                        text=(
                            f"[system] Orchestrator iteration count: "
                            f"{_effective_for_msg}/{config.max_iterations} "
                            f"(real attempts; {duplicate_rejected_count} duplicate-rejected). "
                            f"Use iteration={iteration_count + 1} for your "
                            f"next experiment."
                        ),
                    ))
                    # F7: warn the LLM when the active phase has saturated its
                    # iteration cap. Forces the agent to advance instead of
                    # grinding the same phase with duplicate configs.
                    phase_cap_message = await self._maybe_phase_cap_nudge(
                        research_id=research_id,
                    )
                    if phase_cap_message:
                        tool_results.append(TextBlock(text=phase_cap_message))
                    # Fix D: once all phases are complete, force a clean stop
                    # immediately rather than letting the agent grind the
                    # terminal phase until the cap/stagnation guards trip.
                    all_complete_message = (
                        await self._maybe_all_phases_complete_terminate(
                            research_id=research_id,
                        )
                    )
                    if all_complete_message:
                        tool_results.append(TextBlock(text=all_complete_message))
                    # AR-7: warn the LLM when no metric improvement has been
                    # recorded for global_stagnation_window consecutive
                    # iterations. Forces a TERMINATE_REQUEST instead of burning
                    # the rest of the budget on stagnant experiments.
                    stagnation_message = await self._maybe_global_stagnation_terminate(
                        research_id=research_id,
                        iteration_count=(iteration_count - duplicate_rejected_count),
                    )
                    if stagnation_message:
                        tool_results.append(TextBlock(text=stagnation_message))
                    messages.append(Message(role="user", content=tool_results))
                    messages = self._compact_messages(
                        messages,
                        keep_recent=settings.context_compaction_threshold // 2,
                    )
                else:
                    # Model generated text only — no more tool calls → done
                    break

            # ML-62 / hardening Phase 1.1: distinguish stop/timeout/completion.
            # ARC-011 P0-004: the terminal status is now written by the state
            # machine, which resolves any racing stop/timeout/fail under the
            # per-session lock by severity (fail > timeout > stop > complete).
            # This closes W8: a stop already in flight (status=`stopping`)
            # refuses a `complete`, so auto-promote is skipped and the session
            # ends `stopped` instead of spuriously `completed`.
            elapsed_total = time.monotonic() - start_time
            completed_at = datetime.now(timezone.utc).isoformat()
            effective_iterations = iteration_count - duplicate_rejected_count

            if _policy_aborted:
                _exit_event = SessionEvent.FAIL
                _reason_status = "failed"
            elif _timed_out:
                _exit_event = SessionEvent.TIMEOUT
                _reason_status = "timed_out"
            elif await self._should_stop_cross_worker(research_id):
                # An operator stop is in flight. Finalize it via the machine
                # (STOP_REQUESTED is a no-op backstop if stop_session already
                # wrote `stopping`; FINALIZE_STOP resolves to `stopped`).
                _exit_event = SessionEvent.FINALIZE_STOP
                _reason_status = "stopped"
            else:
                _exit_event = SessionEvent.COMPLETE
                _reason_status = "completed"

            terminal_reason = await self._derive_terminal_reason(
                research_id=research_id,
                final_status=_reason_status,
                iteration_count=effective_iterations,
                total_cost=total_cost,
                config=config,
                timed_out=_timed_out,
                policy_aborted=_policy_aborted,
            )

            # Q2 split: persist pure accounting status-free so cost is always
            # captured even if the status transition is refused by a racing
            # higher-severity event. No `status=` here (grep-clean).
            await self._store.update_session(
                research_id,
                total_api_cost_usd=round(total_cost, 4),
                effective_iteration_count=effective_iterations,
            )

            _exit_broadcast_fields = {
                "iterations": iteration_count,
                "total_cost_usd": round(total_cost, 4),
                "elapsed_s": round(elapsed_total, 1),
            }
            _exit_status_fields = {
                "completed_at": completed_at,
                "terminal_reason": terminal_reason,
            }
            _exit_result = None
            try:
                if _exit_event is SessionEvent.FINALIZE_STOP:
                    # Ensure `stopping` is recorded (idempotent if stop_session
                    # already did, or if only the flag was set e.g. by
                    # shutdown) before finalizing to `stopped`.
                    await self._sm.transition(
                        research_id, SessionEvent.STOP_REQUESTED,
                    )
                _exit_result = await self._sm.transition(
                    research_id,
                    _exit_event,
                    status_fields=_exit_status_fields,
                    broadcast_fields=_exit_broadcast_fields,
                )
            except IllegalTransitionError:
                # Our intent was refused because a stop is in flight and
                # `stopping` is the only transitional state that lingers
                # (complete/timeout/fail resolve atomically to terminal).
                # Finalize the stop so the session resolves to `stopped` with
                # no auto-promote (W8-A). Any other from-state is unexpected;
                # leave the status to its winning owner.
                try:
                    _exit_result = await self._sm.transition(
                        research_id,
                        SessionEvent.FINALIZE_STOP,
                        status_fields=_exit_status_fields,
                        broadcast_fields=_exit_broadcast_fields,
                    )
                except IllegalTransitionError:
                    _exit_result = None

            if _exit_result is not None:
                final_status = _exit_result.new_state.value
            else:
                _sess = await self._store.get_session(research_id)
                final_status = (_sess or {}).get("status", "unknown")

            logger.info(
                "Research %s %s: %d iterations, $%.4f, %.0fs",
                research_id, final_status, iteration_count, total_cost, elapsed_total,
            )
            await agent_log.append(
                "system",
                f"{final_status.replace('_', ' ').title()}: {iteration_count} iterations, "
                f"${total_cost:.4f}, {elapsed_total:.0f}s",
            )

            # ML-60: Extract compact insights before rebuilding resume
            await self._extract_session_insights(research_id)

            # ── ML-53 Fix 2.4 / ARC-011 §4.3: Auto-promote standalone sessions ──
            # Promote only on a net running→completed completion signalled by
            # the machine (``should_auto_promote`` is False when severity was
            # redirected, e.g. a racing stop refused the completion — W8).
            if (
                _exit_result is not None
                and _exit_result.should_auto_promote
                and not getattr(config, "pipeline_id", None)
            ):
                await self._try_auto_promote(research_id, config, agent_log)
            # ── end ML-53 Fix 2.4 ────────────────────────────────────────

        except asyncio.CancelledError:
            # ARC-011 P0-006: FIRST reap any in-flight governed subprocess tree.
            # Cancelling this coroutine cannot interrupt the to_thread worker
            # that owns the Popen handle, so an operator stop / hard-timeout
            # cancel would otherwise leak the training subprocess until its own
            # per-command timeout. Run the psutil kill in a worker thread so
            # its ~10s wait does not block the event loop; a kill failure must
            # not prevent the status finalize below.
            try:
                await asyncio.to_thread(self._command_procs.kill_all, research_id)
            except Exception:
                logger.exception(
                    "Research %s: failed to reap in-flight commands on cancel",
                    research_id,
                )
            # ARC-011 P0-004: persist accounting, then drive the session to
            # ``stopped`` through the state machine. A cancel with no
            # higher-severity terminal in flight means stopped: record the
            # stop intent (``running|paused → stopping``; no-op if stop_session
            # already wrote it) then finalize (``stopping → stopped``). Both
            # are no-ops against a terminal that already won (W8-B: a late
            # cancel cannot overwrite ``completed``) and refused against a more
            # severe in-flight intent (timing_out/failing resolve atomically to
            # their own terminal — those transitional states never persist, so
            # STOP_REQUESTED never collides with them).
            try:
                await self._store.update_session(
                    research_id,
                    total_api_cost_usd=round(total_cost, 4),
                    effective_iteration_count=(iteration_count - duplicate_rejected_count),
                )
            except Exception:
                logger.exception(
                    "Research %s: failed to persist accounting on cancel", research_id,
                )
            try:
                await self._sm.transition(research_id, SessionEvent.STOP_REQUESTED)
                await self._sm.transition(
                    research_id,
                    SessionEvent.FINALIZE_STOP,
                    status_fields={"completed_at": datetime.now(timezone.utc).isoformat()},
                )
            except IllegalTransitionError:
                pass
            logger.info("Research %s: cancelled", research_id)
            await agent_log.append("system", "Session cancelled")
            # ML-60: Still extract insights from partial sessions
            await self._extract_session_insights(research_id)
            raise

        except Exception as exc:
            logger.exception("Research %s failed: %s", research_id, exc)
            terminal_reason = f"error_unrecoverable:{type(exc).__name__}"
            try:
                await self._store.update_session(
                    research_id,
                    total_api_cost_usd=round(total_cost, 4),
                    effective_iteration_count=(iteration_count - duplicate_rejected_count),
                )
            except Exception:
                logger.exception(
                    "Research %s: failed to persist accounting on error", research_id,
                )
            # ARC-011 P0-004: FAIL is severity 4 (highest) — it wins any race
            # under the lock, redirecting an in-flight stopping/completing to
            # `failed` and skipping auto-promote. The machine emits the
            # `research_failed` broadcast with the merged error field.
            try:
                await self._sm.transition(
                    research_id,
                    SessionEvent.FAIL,
                    status_fields={
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                        "error_message": str(exc)[:2000],
                        "terminal_reason": terminal_reason,
                    },
                    broadcast_fields={"error": str(exc)[:500]},
                )
            except IllegalTransitionError:
                # Already terminal (e.g. a concurrent fail/complete won) — the
                # first writer owns the status. Best-effort broadcast so
                # clients still observe the error.
                try:
                    await broadcaster.broadcast({
                        "event": "research_failed",
                        "research_id": research_id,
                        "error": str(exc)[:500],
                    })
                except Exception:
                    pass
            await agent_log.append("error", str(exc)[:2000])

        finally:
            self._stop_flags.pop(research_id, None)
            self._pause_flags.pop(research_id, None)
            self._blocker_attempt_counters.pop(research_id, None)
            # ARC-011 review C2: drop the session's skill-runtime binding so a
            # long-lived orchestrator doesn't accumulate one entry per session
            # (registration happens in run(); see _session_skills[config.id]).
            self._session_skills.pop(research_id, None)

    # ── ML-53 Fix 2.4 helper ─────────────────────────────────────────────
    async def _try_auto_promote(
        self,
        research_id: str,
        config: ResearchConfig,
        agent_log: AgentLogWriter,
    ) -> None:
        """Auto-promote the best iteration if it is promotion-ready.

        Instantiates ConfigPromoter on-demand (not injected into __init__
        to avoid circular dependencies or changing the constructor).
        """
        try:
            session = await self._store.get_session(research_id)
            if not session:
                return

            best_iter = session.get("best_iteration")
            if best_iter is None:
                return

            # Fetch the best iteration record to check gates
            iterations = await self._store.get_iterations(research_id)
            best_record = None
            for it in iterations:
                if it.get("iteration") == best_iter:
                    best_record = it
                    break
            if not best_record:
                return

            if not training_gates_passed_from_iteration(best_record):
                logger.info(
                    "ML-53: Auto-promote skipped for %s - best iteration %d "
                    "did not pass training gates",
                    research_id, best_iter,
                )
                return

            # Import here to avoid circular dependency at module level
            from src.core.config_promoter import ConfigPromoter

            # ARC-011 review C2-5: route promotion through the session skill's
            # declared target (manifest ``promotion_target``) instead of the
            # implicit FilePathPromotionTarget default. Two failure modes:
            # * ``SkillConfigError`` — the skill *declares* a target kind the
            #   development-promotion machinery does not implement (e.g.
            #   ``registry_api``). Fabricating a file promotion for a skill
            #   with no config file to promote would be wrong, so the
            #   promotion is skipped (audited like every other skip). The
            #   session completes normally.
            # * any other error — an infrastructure hiccup building the
            #   target; fall back to the default file target (the incumbent
            #   behavior) with a warning, keeping ML sessions alive.
            try:
                skill_runtime = getattr(self, "_session_skills", {}).get(
                    research_id,
                )
                promotion_target = (
                    skill_runtime.promotion_target()
                    if skill_runtime is not None
                    else None
                )
            except SkillConfigError as exc:
                logger.warning(
                    "Research %s: auto-promotion skipped — %s",
                    research_id, exc,
                )
                await self._emit_auto_promotion_skipped(
                    research_id=research_id,
                    config=config,
                    agent_log=agent_log,
                    reason="unsupported_promotion_target",
                    iteration=best_iter,
                    terminal_reason=session.get("terminal_reason"),
                    incomplete_phases=[],
                    promotion_allowed=False,
                    blockers=[],
                    collection_errors={"promotion_target": str(exc)},
                )
                return
            except Exception as exc:
                logger.warning(
                    "Research %s: skill promotion_target() failed (%s) — "
                    "falling back to the default file promotion target",
                    research_id, exc,
                )
                promotion_target = None
            if promotion_target is not None:
                promoter = ConfigPromoter(self._store, target=promotion_target)
            else:
                promoter = ConfigPromoter(self._store)
            phase_state = await self._auto_promotion_phase_state(
                research_id=research_id,
                session=session,
                iterations=iterations,
            )
            # Fix B: an explicit TERMINATE_REQUEST from the agent (vs. a
            # crash, timeout, or silent end_turn) signals the agent believes
            # further exploration cannot improve the baseline. When that
            # flag is set AND baseline_capture has completed, waive incomplete
            # iteration-count phases (e.g. tabular_sweeps) so promotion can
            # proceed to gate evaluation. Hard gates (training, calibration,
            # parity) still run inside promoter.preview() and can still block.
            _terminate_received = bool(session.get("terminate_request_received"))
            _completed_phase_ids = {
                p.get("id")
                for p in phase_state.get("phases", [])
                if p.get("status") == "completed"
            }
            _baseline_complete = "baseline_capture" in _completed_phase_ids
            _waive_incomplete = _terminate_received and _baseline_complete
            raw_incomplete = [
                phase
                for phase in incomplete_phase_ids(phase_state)
                if phase != "promotion_proposal"
            ]
            incomplete_phases = [] if _waive_incomplete else raw_incomplete
            if _waive_incomplete and raw_incomplete:
                await agent_log.append(
                    "system",
                    f"Promotion gates evaluated; incomplete phases waived "
                    f"by TERMINATE_REQUEST: {', '.join(raw_incomplete)}",
                )
            if incomplete_phases:
                await self._emit_auto_promotion_skipped(
                    research_id=research_id,
                    config=config,
                    agent_log=agent_log,
                    reason="incomplete_research_phases",
                    iteration=best_iter,
                    terminal_reason=session.get("terminal_reason"),
                    incomplete_phases=incomplete_phases,
                    promotion_allowed=False,
                    blockers=[],
                )
                return

            try:
                preview = await promoter.preview(research_id)
            except ValueError as exc:
                await self._emit_auto_promotion_skipped(
                    research_id=research_id,
                    config=config,
                    agent_log=agent_log,
                    reason="promotion_preview_failed",
                    iteration=best_iter,
                    terminal_reason=session.get("terminal_reason"),
                    incomplete_phases=[],
                    promotion_allowed=False,
                    blockers=[str(exc)],
                )
                return

            promotion_allowed = bool(preview.get("promotion_allowed"))
            if not promotion_allowed:
                blockers = self._auto_promotion_preview_blockers(preview)
                await self._emit_auto_promotion_skipped(
                    research_id=research_id,
                    config=config,
                    agent_log=agent_log,
                    reason="promotion_preview_blocked",
                    iteration=best_iter,
                    terminal_reason=session.get("terminal_reason"),
                    incomplete_phases=[],
                    promotion_allowed=False,
                    blockers=blockers,
                )
                return

            result = await promoter.confirm(research_id)
            logger.info(
                "ML-53: Auto-promoted development session %s (iter=%d): %s",
                research_id, best_iter, result,
            )
            await agent_log.append(
                "system",
                f"Auto-promoted best iteration {best_iter} to development config",
            )
            await broadcaster.broadcast({
                "event": "auto_promoted",
                "research_id": research_id,
                "iteration": best_iter,
                "instrument": config.subject_id,
                "model_type": config.domain,
            })

        except Exception as exc:
            logger.warning(
                "ML-53: Auto-promotion failed for %s: %s",
                research_id, exc, exc_info=True,
            )
            await agent_log.append(
                "warning",
                f"Auto-promotion failed: {exc}",
            )
    # ── end ML-53 Fix 2.4 helper ─────────────────────────────────────────

    async def _auto_promotion_phase_state(
        self,
        *,
        research_id: str,
        session: Dict[str, Any],
        iterations: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Return phase state for auto-promotion without mutating the session."""
        raw_state = session.get("phase_state_json")
        if isinstance(raw_state, str) and raw_state.strip():
            try:
                parsed = json.loads(raw_state)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict) and isinstance(parsed.get("phases"), list):
                return parsed

        get_hpo_studies = getattr(self._store, "get_hpo_studies", None)
        hpo_studies = (
            await get_hpo_studies(research_id)
            if callable(get_hpo_studies)
            else []
        )
        list_promotions = getattr(self._store, "list_promotions", None)
        promotions = await list_promotions() if callable(list_promotions) else []
        return build_phase_state(
            session=session,
            iterations=iterations,
            hpo_studies=hpo_studies,
            promotions=[
                row for row in promotions
                if row.get("research_id") == research_id
            ],
        )

    async def _emit_auto_promotion_skipped(
        self,
        *,
        research_id: str,
        config: ResearchConfig,
        agent_log: AgentLogWriter,
        reason: str,
        iteration: Optional[int],
        terminal_reason: Optional[str],
        incomplete_phases: List[str],
        promotion_allowed: bool,
        blockers: List[str],
        collection_errors: Optional[Dict[str, str]] = None,
    ) -> None:
        """Emit structured observability for expected auto-promotion skips.

        Gap 3: ``collection_errors`` carries the underlying error reasons
        from ``PromotionEvidenceCollector`` (e.g.
        ``{"inference_preflight": "adapter_preflight_failed: ConnectTimeout"}``).
        Surfacing them next to the high-level blocker codes lets operators
        distinguish infrastructure failures (inference-service unreachable)
        from genuine model-validation failures, which were indistinguishable
        in live ``res_baf6605ce94f``.
        """
        payload = {
            "event": "auto_promotion_skipped",
            "research_id": research_id,
            "iteration": iteration,
            "instrument": config.subject_id,
            "timeframe": config.variant,
            "model_type": config.domain,
            "reason": reason,
            "terminal_reason": terminal_reason,
            "incomplete_phases": incomplete_phases,
            "promotion_allowed": promotion_allowed,
            "blockers": blockers,
        }
        if collection_errors:
            payload["collection_errors"] = collection_errors
        if collection_errors:
            logger.info(
                "ML-53: Auto-promotion skipped for %s: reason=%s iteration=%s "
                "blockers=%s collection_errors=%s",
                research_id,
                reason,
                iteration,
                blockers,
                collection_errors,
            )
        else:
            logger.info(
                "ML-53: Auto-promotion skipped for %s: reason=%s iteration=%s blockers=%s",
                research_id,
                reason,
                iteration,
                blockers,
            )
        record_audit_event = getattr(self._store, "record_audit_event", None)
        if callable(record_audit_event):
            try:
                await record_audit_event(
                    actor_id="autoresearch-agent",
                    action="promotion.auto_skip",
                    outcome="success",
                    research_id=research_id,
                    request_metadata={
                        key: value for key, value in payload.items()
                        if key != "event"
                    },
                )
            except Exception:
                logger.debug(
                    "Failed to record auto-promotion skip audit event for %s",
                    research_id,
                    exc_info=True,
                )
        try:
            log_line = f"Auto-promotion skipped: {reason}"
            if collection_errors:
                log_line += f" — collection_errors={collection_errors}"
            await agent_log.append("system", log_line)
        except Exception:
            logger.debug(
                "Failed to append auto-promotion skip to agent log for %s",
                research_id,
                exc_info=True,
            )
        try:
            await broadcaster.broadcast(payload)
        except Exception:
            logger.debug(
                "Failed to broadcast auto-promotion skip for %s",
                research_id,
                exc_info=True,
            )

    @staticmethod
    def _auto_promotion_preview_blockers(preview: Dict[str, Any]) -> List[str]:
        blockers: List[str] = []
        for key in (
            "gate_bundle_evaluation",
            "consistency_report",
            "quality_baseline_evaluation",
        ):
            container = preview.get(key)
            if not isinstance(container, dict):
                continue
            for blocker in container.get("blockers") or []:
                blocker_s = str(blocker)
                if blocker_s not in blockers:
                    blockers.append(blocker_s)
        return blockers

    async def _infer_decision(
        self,
        research_id: str,
        primary_metric: Optional[float],
        training_gates_passed: bool,
    ) -> str:
        """Determine keep/improve/discard by comparing against session best.

        ML-53: Three-way decision taxonomy:
        - 'keep'    — training gates passed AND metric improved
        - 'improve' — training gates NOT passed but metric improved
        - 'discard' — metric did not improve or is None
        """
        if primary_metric is None:
            return "discard"

        session = await self._store.get_session(research_id)
        best = session.get("best_metric") if session else None

        metric_improved = (best is None) or (
            primary_metric > best + settings.global_stagnation_epsilon
        )

        if training_gates_passed and metric_improved:
            return "keep"
        elif metric_improved:
            return "improve"
        else:
            return "discard"

    async def _record_iteration(
        self,
        research_id: str,
        iteration: int,
        marker: Dict[str, Any],
        cumulative_cost: float,
        *,
        workspace: Optional[str] = None,
        turn: Optional[int] = None,
        command: Optional[str] = None,
    ) -> None:
        """Record an iteration and broadcast the event."""
        marker = dict(marker)
        normalize_artifact_references_in_mapping(marker)
        # AR-1: coerce dict/list config_snapshot to a JSON string so all
        # downstream consumers that declare config_snapshot: Optional[str]
        # receive a valid string.  The LLM may emit a JSON object instead of
        # YAML text when self-reporting a config_snapshot on ITERATION_RESULT.
        _cs = marker.get("config_snapshot")
        if isinstance(_cs, (dict, list)):
            marker["config_snapshot"] = json.dumps(_cs, sort_keys=True)
        training_gates = normalize_training_gate_aliases(
            marker,
            logger=logger,
            context=f"{research_id} iteration {iteration}",
        )
        primary_metric = marker.get("primary_metric")
        decision = marker.get("decision", "unknown")
        description = marker.get("description", "")
        metric_name = marker.get("metric_name", "")
        training_time = marker.get("training_time_s")

        session = await self._store.get_session(research_id)
        active_phase = self._active_phase_from_marker_or_session(marker, session)
        if active_phase and not marker.get("search_phase"):
            marker["search_phase"] = active_phase

        # ARC-011 P6-004 / H4 — fencing token. The captured lock_epoch (this
        # worker's "as of dispatch" view) is threaded to the state-advancing
        # writes below. If a stop/timeout landed on another worker during the
        # command, that transition bumped lock_epoch; the captured value no
        # longer matches and the store's conditional WHERE returns 0 rows →
        # the write is rejected and the iteration is discarded (see the
        # effective-iteration-count write below). SQLiteStateStore has no
        # lock_epoch column → get_session returns None for it → the epoch is
        # None → writes are unconditional (single-worker: no stale writers).
        _fence_epoch = self._session_epochs.get(research_id)

        # AR-3: For promotion-family phases the agent does not run a fresh
        # training command and legitimately emits no config_snapshot.  Inherit
        # from the most recent iteration that recorded one so consistency
        # reports don't fire ``missing_config_snapshot`` as a blocker.
        if not marker.get("config_snapshot"):
            if active_phase in _PROMOTION_FAMILY:
                _inherited = (
                    await self._store.get_latest_iteration_with_config_snapshot(
                        research_id
                    )
                )
                if _inherited and _inherited.get("config_snapshot"):
                    marker["config_snapshot"] = _inherited["config_snapshot"]
                    marker["config_snapshot_inherited_from_iteration"] = (
                        _inherited["iteration"]
                    )

        if session:
            identity = marker.get("trial_identity")
            if not identity:
                identity = build_trial_identity(
                    instrument=str(session.get("instrument") or ""),
                    timeframe=str(session.get("timeframe") or ""),
                    model_type=str(session.get("model_type") or marker.get("model_type") or ""),
                    command=command,
                    config_snapshot=marker.get("config_snapshot"),
                    quick_mode=bool(session.get("quick_mode")),
                    marker=marker,
                )
                marker["trial_identity"] = identity
            marker["canonical_config_hash"] = (
                marker.get("canonical_config_hash")
                or identity.get("canonical_config_hash")
                or canonical_config_hash(marker.get("config_snapshot"))
            )
            marker["trial_identity_hash"] = (
                marker.get("trial_identity_hash")
                or trial_identity_hash(identity)
            )
        else:
            marker["canonical_config_hash"] = (
                marker.get("canonical_config_hash")
                or canonical_config_hash(marker.get("config_snapshot"))
            )

        if workspace:
            enrich_marker_from_result_artifact(
                marker=marker,
                workspace=workspace,
                iteration=iteration,
                logger=logger,
            )

        attempt_snapshot = None
        attempt_snapshot_path = None
        attempt_snapshot_hash = None
        if workspace and command:
            attempt_snapshot = build_iteration_attempt_snapshot(
                research_id=research_id,
                iteration=iteration,
                turn=turn if turn is not None else -1,
                command=command,
                config_snapshot=marker.get("config_snapshot"),
                workspace=workspace,
                marker=marker,
            )
            attempt_snapshot_hash = attempt_snapshot.get("snapshot_hash")
            try:
                attempt_snapshot_path = write_iteration_attempt_snapshot(
                    workspace=workspace,
                    snapshot=attempt_snapshot,
                )
            except OSError as exc:
                logger.warning(
                    "Research %s iteration %d: could not write attempt "
                    "snapshot: %s",
                    research_id,
                    iteration,
                    exc,
                )
            marker["attempt_snapshot"] = attempt_snapshot
            marker["attempt_snapshot_path"] = attempt_snapshot_path
            marker["attempt_snapshot_hash"] = attempt_snapshot_hash

        model_type = (session or {}).get("model_type") or marker.get("model_type") or ""

        # Gap 1: auto-inject phase-advancement markers (tabular_sweep_variant,
        # atr_mult_sweep_enabled, threshold_calibration_attempt_id,
        # temporal_ensemble_attempt_id) when this iter's config differs from
        # the baseline iter's config on any salient knob. Closes the fast
        # key-path of Issue 10A's narrowed advancement keys for agents that
        # don't emit the markers themselves (live: res_baf6605ce94f had 0/12
        # iters carrying tabular_sweep_variant; the >=6 cardinality fallback
        # had to carry the load).
        #
        # Skip conditions:
        # - baseline_capture iter — should NOT carry exploration markers.
        # - No config_snapshot — nothing to compare against baseline.
        # - Rejected duplicate / no training executed — the agent prepared
        #   a config that was caught by canonical-config dedup BEFORE
        #   prepare.py ran, so no genuine exploration happened. Injecting
        #   the marker here re-creates Issue 10A's false-advancement bug
        #   via a different path (live: res_99469dfc1088 iter 2 — a
        #   rejected duplicate received tabular_sweep_variant and
        #   completed tabular_sweeps with zero genuine in-phase training).
        _skip_injection = (
            active_phase == "baseline_capture"
            or not marker.get("config_snapshot")
            or marker.get("duplicate_reason")
            or marker.get("training_time_s") is None
        )
        if not _skip_injection:
            baseline_iter = (
                await self._store.get_first_iteration_with_config_snapshot(
                    research_id,
                )
            )
            if baseline_iter and baseline_iter.get("iteration") != iteration:
                try:
                    current_cfg = (
                        yaml.safe_load(marker.get("config_snapshot") or "") or {}
                    )
                    baseline_cfg = (
                        yaml.safe_load(baseline_iter.get("config_snapshot") or "")
                        or {}
                    )
                except yaml.YAMLError:
                    current_cfg = baseline_cfg = {}
                if isinstance(current_cfg, dict) and isinstance(baseline_cfg, dict):
                    injected = derive_exploration_markers(
                        model_type=model_type,
                        current_config=current_cfg,
                        baseline_config=baseline_cfg,
                    )
                    for key, value in injected.items():
                        marker.setdefault(key, value)

        consistency_report = build_consistency_report(
            research_id=research_id,
            iteration=iteration,
            model_type=model_type,
            config_snapshot=marker.get("config_snapshot"),
            metrics_payload=marker,
            attempt_snapshot=attempt_snapshot,
            search_phase=active_phase,
        )
        marker["consistency_report"] = consistency_report
        marker["consistency_report_passed"] = bool(
            consistency_report.get("passed")
        )

        # Fix F: attribute the as-yet-unrecorded portion of the cumulative API
        # cost to this iteration so per-row api_cost_usd is populated (it was
        # always 0.0 — total was only stored on the session). Summing the
        # already-persisted rows is ordering-independent: the turn's cost lands
        # on the first iteration recorded that turn, 0 on any siblings.
        per_iteration_cost = 0.0
        try:
            _prior_rows = await self._store.get_iterations(research_id)
            _prior_attributed = sum(
                float(r.get("api_cost_usd") or 0.0) for r in _prior_rows
            )
            per_iteration_cost = max(
                0.0, round(float(cumulative_cost) - _prior_attributed, 6)
            )
        except Exception:  # pragma: no cover — cost attribution must never block recording
            logger.debug(
                "Per-iteration cost attribution failed for %s", research_id,
                exc_info=True,
            )

        await self._store.add_iteration(
            research_id=research_id,
            iteration=iteration,
            primary_metric=primary_metric,
            metric_name=metric_name,
            all_gates_passed=training_gates,
            decision=decision,
            description=description,
            config_snapshot=marker.get("config_snapshot"),
            metrics_json=json.dumps(marker),
            training_time_s=training_time,
            api_cost_usd=per_iteration_cost,
            mlflow_run_id=marker.get("mlflow_run_id"),
            canonical_config_hash=marker.get("canonical_config_hash"),
            trial_identity_hash=marker.get("trial_identity_hash"),
            trial_identity_json=(
                json.dumps(marker.get("trial_identity"), sort_keys=True)
                if marker.get("trial_identity") is not None
                else marker.get("trial_identity_json")
            ),
            duplicate_of_research_id=marker.get("duplicate_of_research_id"),
            duplicate_of_iteration=marker.get("duplicate_of_iteration"),
            duplicate_reason=marker.get("duplicate_reason"),
            attempt_snapshot_json=(
                json.dumps(attempt_snapshot, sort_keys=True)
                if attempt_snapshot is not None
                else None
            ),
            attempt_snapshot_path=attempt_snapshot_path,
            attempt_snapshot_hash=attempt_snapshot_hash,
            consistency_report_json=consistency_report_json(consistency_report),
            search_phase=active_phase,
            metric_improvement_epsilon=settings.global_stagnation_epsilon,
            lock_epoch=_fence_epoch,
        )

        try:
            rows_after_record = await self._store.get_iterations(research_id)
            effective_count = sum(
                1 for row in rows_after_record if not _is_rejected_duplicate(row)
            )
            # ARC-011 P6-004: the effective-iteration-count write is the
            # state-advancing write that must be fenced. PostgresStateStore
            # returns None on a 0-row conditional update (stale epoch); that
            # means the session was deauthorized while the command ran → the
            # iteration row is still an immutable record of what ran, but it
            # must NOT advance the session's counter / trigger auto-promotion.
            updated = await self._store.update_session(
                research_id,
                effective_iteration_count=effective_count,
                lock_epoch=_fence_epoch,
            )
            if _fence_epoch is not None and updated is None:
                logger.warning(
                    "Research %s: discarding stale iteration %s result — "
                    "lock_epoch fence rejected the write (captured=%s).",
                    research_id, iteration, _fence_epoch,
                )
                await self._store.record_audit_event(
                    actor_id="system:orchestrator",
                    action="result.discarded.stale_worker",
                    outcome="info",
                    research_id=research_id,
                    request_metadata={
                        "iteration": iteration,
                        "captured_lock_epoch": _fence_epoch,
                        "primary_metric": primary_metric,
                    },
                )
                return
        except Exception:  # pragma: no cover - counter refresh must not block recording
            logger.debug(
                "Effective iteration counter refresh failed for %s",
                research_id,
                exc_info=True,
            )

        # ML-59: If this is an HPO study result, also persist to hpo_studies
        if marker.get("mode") == "hpo_study":
            top_trials = marker.get("top_trials")
            await self._store.add_hpo_study(
                research_id=research_id,
                iteration=iteration,
                n_trials=marker.get("n_trials", 0),
                completed_trials=marker.get("completed_trials", 0),
                best_composite=marker.get("best_composite"),
                training_time_s=training_time,
                top_trials_json=json.dumps(top_trials) if top_trials else None,
                study_id=marker.get("study_id"),
                max_trials=marker.get("n_trials"),
                search_space_json=json.dumps(marker.get("search_space"), sort_keys=True)
                if marker.get("search_space")
                else None,
                budget_json=json.dumps(marker.get("budget"), sort_keys=True)
                if marker.get("budget")
                else None,
                timeout_s=marker.get("timeout_s"),
            )

        await self._refresh_phase_state(research_id)

        event = {
            "event": "iteration_complete",
            "research_id": research_id,
            "iteration": iteration,
            "primary_metric": primary_metric,
            "metric_name": metric_name,
            "training_gates_passed": training_gates,
            "all_gates_passed": training_gates,
            "consistency_report_passed": bool(consistency_report.get("passed")),
            "decision": decision,
            "description": description,
            "training_time_s": training_time,
            "cumulative_api_cost_usd": round(cumulative_cost, 4),
            "search_phase": marker.get("search_phase"),
            "attempt_snapshot_hash": attempt_snapshot_hash,
            "result_artifact_path": marker.get("result_artifact_path"),
            "result_artifact_sha256": marker.get("result_artifact_sha256"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await broadcaster.broadcast(event)
        metric_display = (
            f"{primary_metric:.4f}"
            if isinstance(primary_metric, (float, int))
            else "None"
        )
        logger.info(
            "Research %s iteration %d: metric=%s training_gates=%s decision=%s — %s",
            research_id,
            iteration,
            metric_display,
            training_gates,
            decision,
            description,
        )

    async def _attach_consistency_report(
        self,
        research_id: str,
        iteration: int,
        marker: Dict[str, Any],
    ) -> None:
        """Attach/update consistency report before overwriting an iteration."""
        normalize_artifact_references_in_mapping(marker)
        session = await self._store.get_session(research_id)
        existing = await self._store.get_iteration(research_id, iteration)
        attempt_snapshot = None
        if existing and existing.get("attempt_snapshot_json"):
            try:
                attempt_snapshot = json.loads(existing["attempt_snapshot_json"])
            except (json.JSONDecodeError, TypeError):
                attempt_snapshot = None
        active_phase = self._active_phase_from_marker_or_session(
            marker,
            session,
            existing,
        )
        if active_phase and not marker.get("search_phase"):
            marker["search_phase"] = active_phase

        marker["consistency_report"] = build_consistency_report(
            research_id=research_id,
            iteration=iteration,
            model_type=(session or {}).get("model_type") or marker.get("model_type") or "",
            config_snapshot=marker.get("config_snapshot")
            or (existing or {}).get("config_snapshot"),
            metrics_payload=marker,
            attempt_snapshot=attempt_snapshot,
            search_phase=active_phase,
        )

    @staticmethod
    def _active_phase_from_marker_or_session(
        marker: Dict[str, Any],
        session: Optional[Dict[str, Any]],
        existing: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Resolve the phase used for iteration storage and validation."""
        for candidate in (
            marker.get("search_phase"),
            (existing or {}).get("search_phase"),
        ):
            if isinstance(candidate, str) and candidate.strip():
                return candidate

        phase_state_raw = (session or {}).get("phase_state_json")
        if isinstance(phase_state_raw, str) and phase_state_raw.strip():
            try:
                phase_state_obj = json.loads(phase_state_raw)
            except (json.JSONDecodeError, TypeError, AttributeError):
                return None
            if isinstance(phase_state_obj, dict):
                candidate = phase_state_obj.get("current_phase")
                if isinstance(candidate, str) and candidate.strip():
                    return candidate
        if isinstance(phase_state_raw, dict):
            candidate = phase_state_raw.get("current_phase")
            if isinstance(candidate, str) and candidate.strip():
                return candidate
        return None

    @staticmethod
    def _extract_terminate_request(agent_text: str) -> Optional[str]:
        """Return the assistant's TERMINATE_REQUEST line/body, if present."""
        if not agent_text:
            return None
        lines = agent_text.splitlines()
        for index, line in enumerate(lines):
            stripped = line.lstrip()
            if stripped.upper().startswith("TERMINATE_REQUEST:"):
                return "\n".join([stripped, *lines[index + 1 :]]).strip()
        return None

    # DM-2: deferral gate for premature TERMINATE_REQUEST.
    #
    # The agent on res_be66790e192e walked away at iteration 12 of a
    # 50-iteration budget (24% used) with last_best at iter 7 (gap=5),
    # having tried only 5 distinct configs. The previous handler
    # honoured terminate_request unconditionally. These constants tune
    # the protective floor — class-level so they can be patched in
    # tests without monkey-patching ``settings``.
    _DM2_BUDGET_DEFER_FRACTION = 0.5
    _DM2_BEST_GAP_DEFER_FLOOR = 5

    async def _should_defer_terminate(
        self,
        *,
        research_id: str,
        iteration_count: int,
        duplicate_rejected_count: int,
        config: ResearchConfig,
    ) -> Optional[Dict[str, str]]:
        """DM-2: return a deferral payload when TERMINATE_REQUEST should
        be turned into a continuation nudge instead of being honored.

        Returns ``None`` (i.e. honor the request) when any of:
          * effective iteration count >= 50% of ``config.max_iterations``
            (the budget hard floor — past this point the agent has run
            half the planned work and a terminate is honest);
          * the session has no ``best_iteration`` yet (no progress to
            protect — the agent's request to quit is informed);
          * the gap between current iteration and ``best_iteration`` is
            >= ``_DM2_BEST_GAP_DEFER_FLOOR`` (the existing global
            stagnation nudge has already had time to fire — see
            :meth:`_maybe_global_stagnation_terminate`).

        Otherwise returns ``{"reason": ..., "text": ...}`` carrying a
        short rationale (for logs) and a user-turn message that nudges
        the agent toward an unexplored lever in the current phase.
        """
        effective = max(0, iteration_count - duplicate_rejected_count)
        max_iters = max(1, int(config.max_iterations))
        budget_fraction = effective / max_iters

        # Hard floor — past half-budget, terminate is honored regardless of
        # how recently the best iteration was achieved.
        if budget_fraction >= self._DM2_BUDGET_DEFER_FRACTION:
            return None

        session = await self._store.get_session(research_id)
        best_iteration = session.get("best_iteration") if session else None
        # No qualifying iteration yet — agent's call to quit is informed.
        if best_iteration is None:
            return None

        gap = effective - int(best_iteration)
        if gap >= self._DM2_BEST_GAP_DEFER_FLOOR:
            return None

        # Compose a short reason for logs + a nudge text for the agent.
        current_phase = (
            self._active_phase_from_marker_or_session({}, session)
            if session
            else None
        )
        reason = (
            f"iters_used={effective}/{max_iters} "
            f"(< {int(self._DM2_BUDGET_DEFER_FRACTION * 100)}% floor), "
            f"best_gap={gap} (< {self._DM2_BEST_GAP_DEFER_FLOOR})"
        )
        text = (
            "TERMINATE_REQUEST_DEFERRED: "
            f"only {effective} of {max_iters} iterations used "
            f"({budget_fraction:.0%}) AND the session best was achieved "
            f"{gap} iteration(s) ago. "
            "Either threshold must be cleared before terminate is honored: "
            f"reach {int(max_iters * self._DM2_BUDGET_DEFER_FRACTION)}+ "
            "iterations OR show "
            f"{self._DM2_BEST_GAP_DEFER_FLOOR}+ iterations without metric "
            "improvement. "
            "Pick an unexplored lever in the current phase"
            + (f" '{current_phase}'" if current_phase else "")
            + " (e.g. a different `meta_model`, `sample_weight_halflife`, "
            "`direction_pct_threshold`, or `horizon_ensemble` setting) "
            "and run another experiment. Do NOT re-emit TERMINATE_REQUEST "
            "until one of the two thresholds above is met."
        )
        return {"reason": reason, "text": text}

    async def _refresh_phase_state(
        self,
        research_id: str,
        *,
        iterations_remaining: Optional[int] = None,
        phases: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """DM-14: when ``iterations_remaining`` is supplied, ``build_phase_state``
        can gate the active phase's ``next_action`` suffix on budget
        headroom. ``None`` (the default) skips the suffix gate — the
        per-phase ``headroom_hint`` field still appears on every phase
        entry regardless.

        ARC-011 review C2-1: ``phases`` lets the caller source the plan from
        the session's skill runtime (manifest-driven) instead of the
        hardcoded per-model table inside ``build_phase_state``; ``None``
        keeps the legacy derivation.
        """
        session = await self._store.get_session(research_id)
        if not session:
            return
        # ARC-011 review C2-1: source the phase plan from the session's skill
        # runtime (manifest-driven) when the caller didn't pass one. The
        # hardcoded per-model table inside ``build_phase_state`` remains only
        # as the transitional fallback (legacy sessions with no skill bound).
        if phases is None:
            skill_runtime = getattr(self, "_session_skills", {}).get(research_id)
            if skill_runtime is not None:
                try:
                    phases = skill_runtime.phase_plan()
                except Exception as exc:
                    logger.warning(
                        "Research %s: skill phase_plan() failed — falling "
                        "back to the per-model phase table: %s",
                        research_id, exc,
                    )
        iterations = await self._store.get_iterations(research_id)
        hpo_studies = await self._store.get_hpo_studies(research_id)
        promotions = await self._store.list_promotions()
        state = build_phase_state(
            session=session,
            iterations=iterations,
            hpo_studies=hpo_studies,
            promotions=[
                row for row in promotions
                if row.get("research_id") == research_id
            ],
            iterations_remaining=iterations_remaining,
            phases=phases,
        )
        await self._store.update_session(
            research_id,
            current_phase=state.get("current_phase"),
            next_action=state.get("next_action"),
            phase_state_json=phase_state_json(state),
        )
        event = {
            "event": "phase_state_updated",
            "research_id": research_id,
            "current_phase": state.get("current_phase"),
            "next_action": state.get("next_action"),
            "phase_state": state,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if session.get("pipeline_id"):
            event["pipeline_id"] = session.get("pipeline_id")
        await broadcaster.broadcast(event)

    async def _build_phase_continuation_kick(
        self,
        *,
        research_id: str,
        iteration_count: int,
        total_cost: float,
        config: ResearchConfig,
    ) -> Optional[Dict[str, str]]:
        """F1: decide whether an `end_turn` should be honored.

        Returns ``None`` when termination is acceptable (phase plan complete,
        or no headroom in budget/iterations). Returns a dict with ``reason``
        (for logs) and ``text`` (a user-turn message that re-engages the LLM
        with the outstanding phase work) when the loop should continue.

        AR-4 blocker escalation:
        When ``state["blocked"]`` is True the LLM is stuck on an unresolvable
        consistency gate.  We count how many consecutive kick attempts have
        been made for the same ``block_reason``.  On the 3rd attempt we return
        a ``blocker_unresolved_terminate`` kick that demands a
        ``TERMINATE_REQUEST`` instead of another experiment nudge, preventing
        the loop from spinning 7+ times on the same broken promotion.
        """
        # Refresh phase state so this decision uses the latest evidence.
        # DM-14: pass through the iterations-remaining count so
        # build_phase_state can gate the active phase's next_action
        # suffix on budget headroom.
        _iters_remaining = max(0, config.max_iterations - iteration_count)
        await self._refresh_phase_state(
            research_id, iterations_remaining=_iters_remaining,
        )
        session = await self._store.get_session(research_id)
        if not session:
            return None
        phase_state_raw = session.get("phase_state_json")
        if not isinstance(phase_state_raw, str) or not phase_state_raw.strip():
            return None
        try:
            state = json.loads(phase_state_raw)
        except (json.JSONDecodeError, TypeError):
            return None

        blocked = bool(state.get("blocked"))
        incomplete = incomplete_phase_ids(state)

        # When every phase is "completed" AND there is no active blocker, the
        # phase plan is genuinely done — honour end_turn.
        if not incomplete and not blocked:
            return None

        budget_remaining = max(0.0, config.max_budget_usd - total_cost)
        iterations_remaining = max(0, config.max_iterations - iteration_count)
        # If neither budget nor iteration headroom is left, allow exit.
        if budget_remaining <= 0.10 or iterations_remaining <= 0:
            return None

        # AR-4: blocker-attempt counting + escalation.
        if blocked:
            key = str(state.get("block_reason") or "")
            session_counters = self._blocker_attempt_counters.setdefault(
                research_id, {}
            )
            session_counters[key] = session_counters.get(key, 0) + 1
            attempt_count = session_counters[key]
            if attempt_count >= 3:
                logger.warning(
                    "Research %s: blocker '%s' unresolved after %d attempts — "
                    "escalating to forced TERMINATE_REQUEST",
                    research_id, key, attempt_count,
                )
                return {
                    "reason": "blocker_unresolved_terminate",
                    "text": (
                        f"BLOCKER_PERSISTED: '{key}' has not been resolved "
                        f"after {attempt_count} attempts. "
                        "Reply with a single line beginning `TERMINATE_REQUEST:` "
                        "followed by structured justification referencing each "
                        "incomplete phase id. "
                        "Do NOT silently end_turn and do NOT run another experiment."
                    ),
                }
            # First or second attempt: emit a targeted blocker-remediation nudge
            # so the LLM knows it is blocked, not just incomplete.
            current_phase = state.get("current_phase") or (incomplete[0] if incomplete else "")
            next_action = state.get("next_action") or "Resolve the consistency blocker."
            return {
                "reason": "blocker_remediation",
                "text": (
                    "[system] You issued an end_turn but the phase plan is "
                    f"blocked on phase '{current_phase}'. "
                    f"Active blocker: {key}. "
                    f"Incomplete phases remaining: "
                    f"{', '.join(incomplete) if incomplete else current_phase}. "
                    f"Budget remaining: "
                    f"${budget_remaining:.2f} of ${config.max_budget_usd:.2f}. "
                    f"Iterations remaining: "
                    f"{iterations_remaining}/{config.max_iterations}. "
                    f"Required next action: {next_action} "
                    "Resolve the consistency blocker before advancing. If the "
                    "blocker cannot be resolved, reply with a single line "
                    "beginning `TERMINATE_REQUEST:` followed by structured "
                    "justification referencing each incomplete phase id."
                ),
            }

        # No active blocker — standard phase-continuation nudge.
        current_phase = state.get("current_phase") or incomplete[0]
        next_action = state.get("next_action") or "Continue the phase plan."
        text = (
            "[system] You issued an end_turn but the phase plan is incomplete. "
            f"Current phase: {current_phase}. Incomplete phases remaining: "
            f"{', '.join(incomplete)}. Budget remaining: "
            f"${budget_remaining:.2f} of ${config.max_budget_usd:.2f}. "
            f"Iterations remaining: {iterations_remaining}/{config.max_iterations}. "
            f"Required next action: {next_action} "
            "Do NOT terminate. Run the next experiment for the current phase, "
            "or — if your evidence shows the phase is genuinely complete — "
            "emit the metrics evidence key (see SKILL.md \"Phase Advancement\") "
            "so the phase plan can advance. If you believe the entire phase "
            "plan should terminate early, reply with a single line beginning "
            "TERMINATE_REQUEST: followed by a structured justification "
            "referencing each incomplete phase id."
        )
        return {
            "reason": (
                f"phase plan incomplete ({len(incomplete)} phases, current "
                f"{current_phase}); ${budget_remaining:.2f} budget and "
                f"{iterations_remaining} iterations remaining"
            ),
            "text": text,
        }

    async def _maybe_phase_cap_nudge(
        self,
        *,
        research_id: str,
    ) -> Optional[str]:
        """F7: return a system-message text when the current phase's
        ``max_iterations`` cap has been hit without producing the phase's
        evidence key. The orchestrator injects this into the next user turn
        so the LLM moves on instead of grinding inside the same phase.
        """
        session = await self._store.get_session(research_id)
        if not session:
            return None
        phase_state_raw = session.get("phase_state_json")
        if not isinstance(phase_state_raw, str) or not phase_state_raw.strip():
            return None
        try:
            state = json.loads(phase_state_raw)
        except (json.JSONDecodeError, TypeError):
            return None
        current_id = state.get("current_phase")
        if not current_id:
            return None
        iterations = await self._store.get_iterations(research_id)
        in_phase = sum(
            1 for it in iterations
            if (it.get("search_phase") or "") == current_id
        )
        if not phase_cap_exceeded(state, in_phase):
            return None
        next_action = state.get("next_action") or "Advance the phase plan."
        return (
            f"[system] Phase '{current_id}' has reached its iteration cap "
            f"({in_phase} iterations recorded for this phase). Stop tuning "
            f"inside this phase. Emit the phase's evidence key (see SKILL.md "
            f"\"Phase Advancement\") to advance, or proceed to the next phase. "
            f"Next phase guidance: {next_action}"
        )

    async def _maybe_all_phases_complete_terminate(
        self,
        *,
        research_id: str,
    ) -> Optional[str]:
        """Fast terminal guard: once every phase is complete, instruct the
        agent to STOP and emit a TERMINATE_REQUEST immediately rather than
        running more experiments in the terminal phase. Promotion
        preview/confirm is server-owned and runs automatically on session end,
        so re-running the terminal phase only wastes budget. Fires after a
        single extra in-phase iteration — it does not wait for the phase cap.
        """
        session = await self._store.get_session(research_id)
        if not session:
            return None
        phase_state_raw = session.get("phase_state_json")
        if not isinstance(phase_state_raw, str) or not phase_state_raw.strip():
            return None
        try:
            state = json.loads(phase_state_raw)
        except (json.JSONDecodeError, TypeError):
            return None
        if not state.get("all_phases_complete") or state.get("blocked"):
            return None
        return (
            "[system] ALL RESEARCH PHASES ARE COMPLETE. Do NOT run another "
            "experiment — the terminal phase needs no further work. Reply now "
            "with a single line beginning `TERMINATE_REQUEST:` and a one-line "
            "justification. The server runs promotion preview/confirm "
            "automatically on session end."
        )

    async def _phase_advancement_is_genuine(
        self,
        research_id: str,
        current_phase: str,
        *,
        sample_size: int = 3,
    ) -> bool:
        """Return True when the current phase was reached by real agent
        exploration (not purely by auto-emitted permissive evidence).

        A phase is considered "genuine" when at least one of the most recent
        ``sample_size`` iterations whose ``search_phase`` matches the current
        phase carries an agent-explicit phase key (i.e. not just
        ``auto_phase_evidence: True``).  When every recent iteration in that
        phase is auto-evidence-only, the phase was floated up by the
        infrastructure-unavailable fallback path and stagnation exemption
        should NOT apply.
        """
        if not current_phase:
            return False
        # ARC-011 review C2-4: a manifest ``blocker_classification`` may
        # declare per-phase evidence keys; those override the module-level
        # ``_PHASE_SPECIFIC_AGENT_KEYS`` table when provided (same
        # skill-value-wins rule as the actionable-blockers override).
        phase_specific_table: Dict[str, frozenset[str]] = _PHASE_SPECIFIC_AGENT_KEYS
        skill_runtime = getattr(self, "_session_skills", {}).get(research_id)
        if skill_runtime is not None:
            try:
                bc = skill_runtime.blocker_classification()
                declared = bc.get("phase_evidence_keys") or {}
                if declared:
                    phase_specific_table = {
                        phase: frozenset(keys)
                        for phase, keys in declared.items()
                    }
            except Exception as exc:  # pragma: no cover — fail-open
                logger.warning(
                    "Research %s: blocker_classification() unavailable — "
                    "using default phase evidence keys: %s", research_id, exc,
                )
        try:
            iterations = await self._store.get_iterations(research_id)
        except Exception:
            return True  # Fail open — don't break stagnation on a store error.

        recent_in_phase = [
            row for row in iterations
            if row.get("search_phase") == current_phase
        ][-sample_size:]
        if not recent_in_phase:
            return False
        for row in recent_in_phase:
            metrics_raw = row.get("metrics_json")
            metrics: Dict[str, Any] = {}
            if isinstance(metrics_raw, str) and metrics_raw.strip():
                try:
                    parsed = json.loads(metrics_raw)
                except (json.JSONDecodeError, TypeError):
                    parsed = None
                if isinstance(parsed, dict):
                    metrics = parsed
            elif isinstance(metrics_raw, dict):
                metrics = metrics_raw

            # Any explicit (non-auto) evidence key for this phase makes the
            # iteration genuine.
            if metrics and not metrics.get("auto_phase_evidence"):
                return True

            # Even with auto_phase_evidence=True, an agent-explicit phase key
            # (e.g. tsfm_adapter, calibration_full_validation) confirms real
            # work was attempted.
            phase_specific_keys = phase_specific_table.get(
                current_phase, set(),
            )
            if any(metrics.get(k) for k in phase_specific_keys):
                return True

        return False

    async def _maybe_global_stagnation_terminate(
        self,
        *,
        research_id: str,
        iteration_count: int,
    ) -> Optional[str]:
        """AR-7: return a system-message text when global metric stagnation is
        detected.

        The check fires when the session's ``best_iteration`` recorded in the
        DB is more than ``settings.global_stagnation_window`` iterations ago,
        meaning no metric improvement has occurred across that many consecutive
        iterations.  When that condition holds the LLM is instructed to reply
        with a ``TERMINATE_REQUEST:`` line.

        Returns a warning string to be injected into the tool-results block, or
        ``None`` when the session has not stagnated.
        """
        session = await self._store.get_session(research_id)
        if not session:
            return None
        # Suppress stagnation during validation/evidence phases where metric
        # improvement is not expected (tsfm_sweeps, calibration gates, etc.),
        # but ONLY when the phase advancement was genuine. A phase entered
        # solely via auto_phase_evidence (permissive fallback keys emitted by
        # prepare.py when the server-owned infrastructure is unavailable) is
        # not real exploration and must remain subject to stagnation.
        _phase_raw = session.get("phase_state_json")
        if isinstance(_phase_raw, str) and _phase_raw.strip():
            try:
                _phase_state = json.loads(_phase_raw)
                _current_phase = _phase_state.get("current_phase") or ""
                if _current_phase in settings.stagnation_exempt_phases:
                    if await self._phase_advancement_is_genuine(
                        research_id, _current_phase,
                    ):
                        return None
            except (json.JSONDecodeError, TypeError):
                pass
        best_iteration = session.get("best_iteration")
        best_metric = session.get("best_metric")
        # No qualifying iteration yet — skip (conservative).
        if best_iteration is None or best_metric is None:
            return None
        gap = iteration_count - best_iteration
        window = settings.global_stagnation_window
        epsilon = settings.global_stagnation_epsilon
        if gap < window:
            return None
        logger.warning(
            "Research %s: global stagnation detected — %d iterations since "
            "best metric %.4f at iteration %d (window=%d, epsilon=%.1e)",
            research_id, gap, best_metric, best_iteration, window, epsilon,
        )
        return (
            f"GLOBAL_STAGNATION: {gap} iterations have produced no metric "
            f"improvement >{epsilon:.0e} above the session best of {best_metric:.4f} "
            f"(achieved at iteration {best_iteration}). "
            "Reply on the next turn with a single line beginning "
            "`TERMINATE_REQUEST:` and structured justification listing each "
            "phase still incomplete and why further training is unlikely to "
            "improve. Do NOT continue running experiments."
        )

    async def _derive_terminal_reason(
        self,
        *,
        research_id: str,
        final_status: str,
        iteration_count: int,
        total_cost: float,
        config: ResearchConfig,
        timed_out: bool,
        policy_aborted: bool,
    ) -> str:
        """F9: produce a single structured token explaining why a session
        ended. Postmortems and the UI can group runs by this value without
        re-deriving heuristics. Values are ASCII, snake_case, optionally
        suffixed with ``:<phase_id>`` when the cause is phase-scoped.

        Vocabulary (success path — called when the loop exits normally):
          policy_aborted                  — policy rejected commands too many times
          wallclock_timeout               — session reached its time limit
          operator_stopped                — user sent stop request
          error_unrecoverable             — used only by _derive_terminal_reason
                                           for legacy completions marked failed
          max_iterations_reached          — hit config.max_iterations
          budget_exhausted                — spent >=99% of max_budget_usd
          phase_plan_completed            — all phases done
          agent_self_terminated_during_phase:<phase_id>  — agent quit early

        Exception path (written directly in the except Exception handler):
          error_unrecoverable:<ExcClass>  — unhandled exception, ExcClass is
                                           the Python exception class name
                                           (e.g. error_unrecoverable:AttributeError)
        """
        if policy_aborted:
            return "policy_aborted"
        if timed_out:
            return "wallclock_timeout"
        if final_status == "stopped":
            return "operator_stopped"
        if final_status == "failed":
            return "error_unrecoverable"
        # final_status == "completed": refine.
        if iteration_count >= config.max_iterations:
            return "max_iterations_reached"
        # Compare against the *budget cap*: a run that ate >=99% of its
        # budget terminated because it ran out of money.
        if total_cost >= 0.99 * config.max_budget_usd:
            return "budget_exhausted"
        # Look at the phase state to decide between "phase plan finished"
        # and "agent self-terminated early".
        session = await self._store.get_session(research_id)
        if session:
            raw = session.get("phase_state_json")
            if isinstance(raw, str) and raw.strip():
                try:
                    state = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    state = None
                if isinstance(state, dict):
                    incomplete = incomplete_phase_ids(state)
                    if not incomplete:
                        return "phase_plan_completed"
                    current = state.get("current_phase") or incomplete[0]
                    return f"agent_self_terminated_during_phase:{current}"
        return "phase_plan_completed"

    @staticmethod
    def _infer_failed_attempt_status(tool_result: str) -> Optional[str]:
        lowered = tool_result.lower()
        if "command timed out" in lowered:
            return "timeout"
        if "trialpruned" in lowered or "trial pruned" in lowered:
            return "pruned"
        if "[exit code:" in lowered:
            return "failed"
        return None

    @staticmethod
    def _effective_tool_timeout(input_data: Dict[str, Any]) -> int:
        timeout = input_data.get("timeout_s", 7200)
        try:
            timeout = int(timeout)
        except (TypeError, ValueError):
            timeout = 7200
        return max(timeout, 900)

    @staticmethod
    def _runtime_command_status(tool_meta: Dict[str, Any]) -> str:
        if tool_meta.get("policy_allowed") is False:
            return "rejected"
        if tool_meta.get("timed_out") is True:
            return "timed_out"
        returncode = tool_meta.get("returncode")
        if isinstance(returncode, int) and returncode != 0:
            return "failed"
        return "completed"

    @staticmethod
    def _attach_runtime_command_metadata(
        marker: Dict[str, Any],
        tool_meta: Dict[str, Any],
    ) -> None:
        runtime_command_id = tool_meta.get("runtime_command_id")
        if runtime_command_id is None:
            return
        marker["runtime_command"] = {
            "id": runtime_command_id,
            "status": AgentOrchestrator._runtime_command_status(tool_meta),
            "returncode": tool_meta.get("returncode"),
            "timed_out": bool(tool_meta.get("timed_out")),
            "policy_operation": tool_meta.get("policy_operation"),
            "normalized_command": tool_meta.get("normalized_command"),
        }
