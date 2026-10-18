"""ARC-011 implementation review C3 (2026-08-15) — W11 anti-forgery fixes.

The review found the signed-metrics contract defeated by its own wiring:

* **KV-block bypass** — the ``---`` auto-detect path (and the marker-file
  path) called ``parse_prepare_output`` with no nonce argument, so any bash
  output containing a KV block was recorded as an iteration even for skills
  with ``require_signed_metrics=true``.
* **Silent KV forgeries** — the forged-detection branch only re-parsed
  marker-format blocks, so KV-format forgeries produced no
  ``metrics.forged`` audit.
* **Nonce readable by the adversary** — the nonce was embedded in the
  agent-readable workspace manifest artifact and injected into every
  governed subprocess env.
* **Non-constant-time compare** in ``_verify_nonce``.

These tests pin the fixes: ``_verify_kv_metrics`` (the shared verification
gate for both KV paths), ``_nonce_env_for_command`` (per-command env
narrowing), the runtime capability properties, and the out-of-band nonce.
"""
from __future__ import annotations

import asyncio
import os
import sys
import types
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

try:
    import anthropic  # noqa: F401
except ModuleNotFoundError:
    sys.modules["anthropic"] = types.SimpleNamespace(
        AsyncAnthropic=MagicMock(return_value=MagicMock()),
        APITimeoutError=TimeoutError,
        APIConnectionError=ConnectionError,
        InternalServerError=RuntimeError,
        APIStatusError=type("APIStatusError", (Exception,), {"status_code": 500}),
    )

os.environ.setdefault("ANTHROPIC_BASE_URL", "http://anthropic.invalid")
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", "test-token")
os.environ.setdefault("USE_VAULT", "false")

from src.core.orchestrator import AgentOrchestrator, _nonce_env_for_command
from src.core.skill_loader import load_skill_manifest
from src.core.skill_runtime import ManifestSkillRuntime

SKILLS_ROOT = Path(__file__).resolve().parents[1] / "skills"
_NONCE_HEX = "ab" * 32


class _FakeAgentLog:
    def __init__(self) -> None:
        self.entries: List[tuple[str, str]] = []

    async def append(self, level: str, message: str, **kw: Any) -> None:
        self.entries.append((level, message))


class _AuditStore:
    def __init__(self) -> None:
        self.audit_events: List[Dict[str, Any]] = []

    async def record_audit_event(self, **kwargs: Any) -> Dict[str, Any]:
        self.audit_events.append(kwargs)
        return kwargs


def _orch_with_store(store: _AuditStore) -> AgentOrchestrator:
    orch = AgentOrchestrator.__new__(AgentOrchestrator)
    orch._store = store  # type: ignore[attr-defined]  # noqa: SLF001
    return orch


async def _verify(
    result: Dict[str, Any],
    *,
    session_nonce: Optional[bytes],
    requires_signed: bool = True,
    source: str = "bash_output",
) -> Optional[Dict[str, Any]]:
    store = _AuditStore()
    orch = _orch_with_store(store)
    agent_log = _FakeAgentLog()
    verified = await orch._verify_kv_metrics(  # noqa: SLF001
        "res_c3",
        result,
        turn=3,
        agent_log=agent_log,  # type: ignore[arg-type]
        session_nonce=session_nonce,
        nonce_field="server_nonce",
        requires_signed=requires_signed,
        source=source,
    )
    # Expose the audit/log observations to the caller via attributes.
    _verify.last_store = store  # type: ignore[attr-defined]
    _verify.last_log = agent_log  # type: ignore[attr-defined]
    return verified


# ============================================================================
# The KV bypass is closed (both findings C3.1 + C3.2)
# ============================================================================


async def test_kv_metrics_wrong_nonce_rejected_and_audited():
    """A `---` block echoing the WRONG nonce is not recorded (previously the
    KV path never checked) and now emits the metrics.forged audit that
    marker-format forgeries already got."""
    result = {
        "status": "completed",
        "primary_metric": 0.7,
        "server_nonce": "ff" * 32,
    }
    verified = await _verify(result, session_nonce=bytes.fromhex(_NONCE_HEX))
    assert verified is None

    audits = _verify.last_store.audit_events  # type: ignore[attr-defined]
    assert len(audits) == 1
    audit = audits[0]
    assert audit["action"] == "metrics.forged"
    assert audit["outcome"] == "failure"
    assert audit["request_metadata"]["format"] == "delimited_kv"
    assert audit["request_metadata"]["source"] == "bash_output"
    assert "nonce" in (audit.get("error_message") or "")
    # The agent is told why (same guidance as the marker path).
    assert any("rejected" in msg for _, msg in _verify.last_log.entries)  # type: ignore[attr-defined]


async def test_kv_metrics_missing_nonce_rejected_and_audited():
    result = {"status": "completed", "primary_metric": 0.7}
    verified = await _verify(result, session_nonce=bytes.fromhex(_NONCE_HEX))
    assert verified is None
    assert _verify.last_store.audit_events[0]["action"] == "metrics.forged"  # type: ignore[attr-defined]


async def test_kv_metrics_correct_nonce_accepted():
    result = {
        "status": "completed",
        "primary_metric": 0.7,
        "server_nonce": _NONCE_HEX,
    }
    verified = await _verify(result, session_nonce=bytes.fromhex(_NONCE_HEX))
    assert verified is not None
    assert verified["metrics_verification"] == "metrics_verified"
    assert _verify.last_store.audit_events == []  # type: ignore[attr-defined]


async def test_kv_metrics_legacy_session_downgrades_gracefully():
    """Enforced skill, but a legacy session with no nonce (P4-005): the
    block is accepted and annotated metrics_unverified — no forged audit."""
    result = {"status": "completed", "primary_metric": 0.7}
    verified = await _verify(result, session_nonce=None)
    assert verified is not None
    assert verified["metrics_verification"] == "metrics_unverified"
    assert _verify.last_store.audit_events == []  # type: ignore[attr-defined]


async def test_kv_metrics_unenforced_passthrough_unchanged():
    """Non-enforcing skills (all ML skills today): byte-identical legacy
    behavior — no verification, no annotation, no audit."""
    result = {"status": "completed", "primary_metric": 0.7}
    verified = await _verify(
        result, session_nonce=bytes.fromhex(_NONCE_HEX), requires_signed=False,
    )
    assert verified == {"status": "completed", "primary_metric": 0.7}
    assert "metrics_verification" not in verified
    assert _verify.last_store.audit_events == []  # type: ignore[attr-defined]


# ============================================================================
# C3.3a — the nonce never enters the agent-readable manifest artifact
# ============================================================================


async def test_workspace_manifest_omits_nonce(monkeypatch, tmp_path):
    """The review's exact leak: research_manifest.json (containing the
    session_nonce in cleartext) was written into the session workspace the
    agent's read_file/grep tools can traverse. Now the artifact carries null
    and the nonce flows only through config.session_nonce in memory."""
    import src.core.session_manager as session_manager_module
    from tests.test_canonical_start_wiring import (
        FakeOrchestrator,
        _configure,
        _healthy_preflight,
    )

    _configure(monkeypatch, tmp_path)
    # ARC-012 P7-005/P7-010: a skill session derives its workspace from the
    # skill's session_path_template (runs/<skill>/<subject>/<variant> under
    # the workspace root) and must name an installed skill. P7-011: the
    # bootstrap runs at start — supply a real eval_set (fail-closed without
    # one outside demo mode).
    eval_set = tmp_path / "eval_set.jsonl"
    eval_set.write_text(
        '{"input": "What is 2+2?", "expected": "4"}\n', encoding="utf-8",
    )
    manifest_dir = (
        tmp_path / "workspace" / "runs" / "prompt-engineering" / "default"
        / "production"
    )

    fake_orchestrator = FakeOrchestrator(None)
    monkeypatch.setattr(
        session_manager_module,
        "AgentOrchestrator",
        lambda store, state_machine=None: fake_orchestrator,
    )
    monkeypatch.setattr(
        session_manager_module, "run_service_preflight", _healthy_preflight,
    )

    from src.core.results_store import ResultsStore

    store = ResultsStore(str(tmp_path / "autoresearch.sqlite"))
    await store.initialize()
    manager = session_manager_module.SessionManager(store)
    try:
        await manager.start_session(
            instrument="default",
            timeframe="production",
            model_type="",
            skill_id="prompt-engineering",
            skill_params={"eval_set": str(eval_set)},
            subject_id="default",
            variant="production",
            max_iterations=1,
        )
        await asyncio.sleep(0)
    finally:
        await manager.shutdown()

    cfg = fake_orchestrator.captured_config
    assert cfg is not None
    assert cfg.session_nonce and len(cfg.session_nonce) == 64

    # Run roots are unique per research session (the research id is the
    # final workspace segment).
    manifest_path = manifest_dir / cfg.id / "research_manifest.json"
    assert manifest_path.is_file(), "workspace manifest must still be written"
    text = manifest_path.read_text(encoding="utf-8")
    assert '"session_nonce": null' in text
    # The live nonce value must not appear anywhere in the artifact.
    assert cfg.session_nonce not in text


# ============================================================================
# C3.3b — nonce env delivery narrowed (per-skill gate + per-command)
# ============================================================================


def test_nonce_env_none_when_not_built():
    assert _nonce_env_for_command(None, "anything", None) is None


def test_nonce_env_only_for_declared_skill_scripts():
    """A governed command invoking one of the skill's manifest-declared
    scripts (its eval) receives the nonce env; anything else does not —
    previously EVERY governed subprocess of every session got the secret."""
    env = {"AUTORESEARCH_SESSION_NONCE": _NONCE_HEX}
    ext = {"allowed_scripts": {"skills/prompt-engineering/eval/run.py"}}

    eval_cmd = (
        ".venv/bin/python skills/prompt-engineering/eval/run.py "
        "--workspace /tmp/w"
    )
    assert _nonce_env_for_command(env, eval_cmd, ext) is env

    other_cmd = ".venv/bin/python scripts/autotuner/setup.py --instrument X"
    assert _nonce_env_for_command(env, other_cmd, ext) is None
    assert _nonce_env_for_command(env, eval_cmd, None) is None
    assert _nonce_env_for_command(env, None, ext) is None


# ============================================================================
# Capability properties (gate both the env delivery and the KV verification)
# ============================================================================


def test_requires_signed_metrics_capability_properties():
    pe = ManifestSkillRuntime(
        load_skill_manifest(SKILLS_ROOT / "prompt-engineering" / "SKILL.yaml"),
        orchestrator=MagicMock(),
    )
    assert pe.requires_signed_metrics is True
    assert pe.nonce_field == "server_nonce"


# ============================================================================
# C3.4 — constant-time compare (behavioral equivalence; the mechanism is
# hmac.compare_digest — pinned indirectly by accept/reject tests above and
# the existing suite in test_metrics_forgery.py).
# ============================================================================
