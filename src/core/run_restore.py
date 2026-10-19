"""Explicit run restore and recovery assessment.

A restore never silently re-resolves a pinned run against today's defaults.
Given the persisted run spec of a session, :func:`assess_recovery` reports
whether the original contract (scorer references, dataset inputs, model
configuration, fixed parameters, limits, objective policy) can be satisfied
exactly, and lists actionable blockers when it cannot: a missing artifact, an
unbound credential reference, registry drift, or a tampered spec all produce
an explicit recovery state (:class:`RecoveryRequired`) instead of a fresh run
disguised as a resume.

Four recovery kinds are distinguished:

* ``pause_resume``     — the same session continues in place (the harness
  process still holds its state); no contract reconstruction happens.
* ``harness_resume``   — the native harness reopens its own session state in
  place; the stored spec is verified but never re-resolved.
* ``continuation``     — a new child session is created from the parent's
  pinned spec and artifacts; parent lineage is preserved.
* ``restart_recovery`` — after a restart, in-flight effects are unknown; the
  pinned contract must be verified before a continuation may be spawned.
"""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence

RECOVERY_KINDS = (
    "pause_resume",
    "harness_resume",
    "continuation",
    "restart_recovery",
)

BLOCKER_SPEC_TAMPERED = "spec_tampered"
BLOCKER_MANIFEST_UNREADABLE = "manifest_unreadable"
BLOCKER_MISSING_ARTIFACT = "missing_artifact"
BLOCKER_MISSING_CREDENTIAL = "missing_credential"
BLOCKER_SKILL_DRIFT = "skill_drift"


@dataclass(frozen=True)
class RecoveryBlocker:
    """One reason a restore cannot satisfy the pinned contract."""

    code: str
    detail: str
    remediation: str

    def as_dict(self) -> Dict[str, str]:
        return asdict(self)


@dataclass
class RecoveryReport:
    """The assessment outcome for one restore request."""

    kind: str
    session_id: str
    ready: bool
    contract: Dict[str, Any] = field(default_factory=dict)
    lineage: Dict[str, Any] = field(default_factory=dict)
    blockers: List[RecoveryBlocker] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "session_id": self.session_id,
            "ready": self.ready,
            "contract": self.contract,
            "lineage": self.lineage,
            "blockers": [b.as_dict() for b in self.blockers],
            "notes": list(self.notes),
        }


class RecoveryRequired(RuntimeError):
    """A restore is blocked and needs explicit operator action.

    The message names every blocker with its remediation; ``report`` carries
    the structured assessment. This is an actionable recovery state, never a
    silent fresh run.
    """

    def __init__(self, report: RecoveryReport) -> None:
        self.report = report
        parts = [
            f"[{b.code}] {b.detail} (remediation: {b.remediation})"
            for b in report.blockers
        ]
        super().__init__(
            f"restore of session {report.session_id!r} as "
            f"{report.kind!r} is blocked: " + "; ".join(parts)
        )


def restore_contract(run_spec: Mapping[str, Any]) -> Dict[str, Any]:
    """The pinned contract a restore must reproduce exactly.

    Scorer references and fixed parameters come from ``skill_params``; the
    model configuration from ``effective_config``; limits and the objective
    policy from their pinned sections. Nothing here is a default: values are
    reported as recorded.
    """
    return {
        "skill_id": run_spec.get("skill_id"),
        "skill_version": run_spec.get("skill_version"),
        "skill_params": dict(run_spec.get("skill_params") or {}),
        "param_defaults_applied": dict(
            run_spec.get("param_defaults_applied") or {}
        ),
        "objective_policy": dict(run_spec.get("objective_policy") or {}),
        "policy": dict(run_spec.get("policy") or {}),
        "effective_config": dict(run_spec.get("effective_config") or {}),
        # the pinned harness/scorer endpoint and dataset configuration is
        # part of what continuation must reproduce exactly
        "harness": dict(run_spec.get("harness") or {}),
    }


def _secret_blockers(
    secret_refs: Mapping[str, Any],
    env: Mapping[str, str],
) -> List[RecoveryBlocker]:
    blockers: List[RecoveryBlocker] = []
    for name, ref in sorted(secret_refs.items()):
        env_var = str(ref.get("env_var") or "")
        value = env.get(env_var) if env_var else None
        if value is None:
            blockers.append(
                RecoveryBlocker(
                    code=BLOCKER_MISSING_CREDENTIAL,
                    detail=(
                        f"continuation requires the secret binding for "
                        f"parameter {name!r} (environment variable "
                        f"{env_var!r}); the rebinding policy "
                        f"{ref.get('rebind_policy')!r} demands an explicit "
                        f"operator-supplied value"
                    ),
                    remediation=(
                        f"bind {env_var!r} explicitly, or rebind the "
                        f"parameter through the operator rebinding surface"
                    ),
                )
            )
    return blockers


def _artifact_blockers(
    artifact_digests: Sequence[str],
    artifact_store: Any,
) -> List[RecoveryBlocker]:
    blockers: List[RecoveryBlocker] = []
    if artifact_store is None:
        return blockers
    for digest in artifact_digests:
        try:
            ok = bool(artifact_store.verify_bundle(digest))
        except Exception:  # noqa: BLE001 - unverifiable counts as missing
            ok = False
        if not ok:
            blockers.append(
                RecoveryBlocker(
                    code=BLOCKER_MISSING_ARTIFACT,
                    detail=(
                        f"the pinned artifact bundle {digest!r} is not "
                        f"present in the artifact store"
                    ),
                    remediation=(
                        "restore the content-addressed bundle from backup "
                        "or declare the run unrestorable; the restore will "
                        "not substitute a fresh run"
                    ),
                )
            )
    return blockers


def assess_recovery(
    *,
    kind: str,
    session_id: str,
    run_spec: Mapping[str, Any],
    secret_refs: Optional[Mapping[str, Any]] = None,
    artifact_digests: Sequence[str] = (),
    artifact_store: Any = None,
    current_skill_version: Optional[str] = None,
    current_skill_digest: Optional[str] = None,
    manifest_integrity: Optional[Mapping[str, Any]] = None,
    allow_skill_drift: bool = False,
    env: Optional[Mapping[str, str]] = None,
) -> RecoveryReport:
    """Assess whether a restore can satisfy the pinned contract exactly.

    ``pause_resume`` and ``harness_resume`` continue in place and never
    reconstruct a contract, so they report no blockers. ``continuation`` and
    ``restart_recovery`` require the pinned contract to be intact where one
    exists — credentials explicitly bound, artifacts resolvable, the skill pin
    matching. A legacy parent without a pinned spec is reported as a note
    (never back-filled from today's defaults); anything else is an actionable
    blocker.
    """
    if kind not in RECOVERY_KINDS:
        raise ValueError(f"unknown recovery kind {kind!r}")
    env = os.environ if env is None else env
    blockers: List[RecoveryBlocker] = []
    notes: List[str] = []
    spec = dict(run_spec or {})
    contract = restore_contract(spec) if spec else {}
    lineage = {
        "parent_session_id": session_id,
        "parent_spec_sha256": spec.get("spec_sha256"),
    }

    if kind in ("continuation", "restart_recovery"):
        integrity = dict(manifest_integrity or {})
        if integrity.get("claims_pinned_spec") and integrity.get(
            "manifest_error"
        ):
            blockers.append(
                RecoveryBlocker(
                    code=BLOCKER_MANIFEST_UNREADABLE,
                    detail=(
                        f"the persisted manifest of session {session_id!r} "
                        f"claims a pinned run spec but cannot be read "
                        f"({integrity.get('manifest_error')}); its "
                        f"checkpointed contract is unreadable"
                    ),
                    remediation=(
                        "restore the manifest artifact or start a fresh run "
                        "explicitly; an unreadable checkpoint is never "
                        "silently treated as a resume"
                    ),
                )
            )
        elif not spec:
            # A legacy parent predates pinned specs: there is no recorded
            # contract to violate, so this is reported as a note (never
            # back-filled from today's defaults), not a blocker. The B20
            # continuation contract for legacy parents holds unchanged.
            notes.append(
                f"session {session_id!r} has no pinned run spec; the "
                f"continuation reports empty parameters and never "
                f"back-fills them from today's defaults"
            )
        else:
            from src.core.run_spec import verify_run_spec

            if not verify_run_spec(spec):
                blockers.append(
                    RecoveryBlocker(
                        code=BLOCKER_SPEC_TAMPERED,
                        detail=(
                            f"the pinned run spec of session {session_id!r} "
                            f"fails its content digest check"
                        ),
                        remediation=(
                            "restore the original manifest or start a fresh "
                            "run explicitly; a tampered spec is never "
                            "silently re-resolved"
                        ),
                    )
                )
            pinned_version = spec.get("skill_version")
            pinned_digest = (spec.get("digests") or {}).get(
                "skill_manifest_sha256"
            )
            drift = (
                pinned_version is not None
                and current_skill_version is not None
                and pinned_version != current_skill_version
            ) or (
                pinned_digest is not None
                and current_skill_digest is not None
                and pinned_digest != current_skill_digest
            )
            if drift and allow_skill_drift:
                notes.append(
                    f"skill {spec.get('skill_id')!r} drifted from the pin "
                    f"(recorded version {pinned_version!r}, installed "
                    f"{current_skill_version!r}); the operator's explicit "
                    f"migration choice allows continuing — the drift is "
                    f"recorded here for review"
                )
            elif drift:
                blockers.append(
                    RecoveryBlocker(
                        code=BLOCKER_SKILL_DRIFT,
                        detail=(
                            f"skill {spec.get('skill_id')!r} has changed "
                            f"since the run was pinned (recorded version "
                            f"{pinned_version!r}, installed "
                            f"{current_skill_version!r}); continuing would "
                            f"silently re-resolve the pinned run against "
                            f"today's skill"
                        ),
                        remediation=(
                            "migrate explicitly with allow_skill_drift=True "
                            "and review the drifted inputs"
                        ),
                    )
                )
            blockers.extend(
                _secret_blockers(
                    secret_refs or spec.get("secret_refs") or {}, env
                )
            )
            blockers.extend(_artifact_blockers(artifact_digests, artifact_store))

    return RecoveryReport(
        kind=kind,
        session_id=session_id,
        ready=not blockers,
        contract=contract,
        lineage=lineage,
        blockers=blockers,
        notes=notes,
    )


def raise_unless_ready(report: RecoveryReport) -> None:
    """Raise :class:`RecoveryRequired` when the restore is blocked."""
    if not report.ready:
        raise RecoveryRequired(report)
