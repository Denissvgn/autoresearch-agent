"""Compiled promotion policy: scope graph and domain evidence requirements.

The skill's declared ``promotion_target.scopes`` compile into a validated
scope graph: declared prior-scope dependencies, per-scope domain evidence
requirements, and mandatory operator-approval flags. The compile is strict —
undeclared prior references, unknown evidence names, and cyclic dependencies
are explicit errors, never silently dropped.

Historical sessions whose skill declares no scopes keep the legacy policy
path unchanged; a non-ML skill that declares its scopes needs no fabricated ML
evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Optional


class ScopePolicyError(ValueError):
    """Raised for invalid or unimplementable scope declarations."""


#: Named scope-evidence validators: declaration name -> the evidence key the
#: evidence collector produces. Every name here has an implementing check in
#: the scoped promotion metadata builder.
SCOPE_EVIDENCE_VALIDATORS: dict[str, str] = {
    "paper_validation": "paper_validation",
    "model_card": "model_card",
    "feature_readiness": "feature_readiness",
    "inference_parity_reload": "inference_parity_reload",
    "canary_validation": "canary_validation",
    "live_risk_limits": "live_risk_limits",
    "monitoring_alerts": "monitoring_alerts",
    "rl_oos_provenance": "rl_oos",
    "rl_economic_replay": "rl_economic_replay",
}


@dataclass(frozen=True)
class ScopeNode:
    """One compiled scope: its approval constraint, dependencies, evidence."""

    id: str
    approval_required: bool = False
    prior_scopes: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()


def compile_scope_graph(
    scopes: Iterable[Any],
) -> dict[str, ScopeNode]:
    """Compile declared scope declarations into a validated graph.

    Raises :class:`ScopePolicyError` for duplicate ids, undeclared prior
    references, unknown evidence names, and cyclic dependencies — a policy
    that cannot be enforced must never be silently approximated.
    """
    graph: dict[str, ScopeNode] = {}
    for scope in scopes or ():
        scope_id = str(getattr(scope, "id", "") or "")
        if not scope_id:
            raise ScopePolicyError("promotion scope requires a non-empty id")
        if scope_id in graph:
            raise ScopePolicyError(f"duplicate promotion scope id {scope_id!r}")
        priors = tuple(str(p) for p in (getattr(scope, "prior_scopes", None) or ()))
        evidence = tuple(str(e) for e in (getattr(scope, "evidence", None) or ()))
        for name in evidence:
            if name not in SCOPE_EVIDENCE_VALIDATORS:
                raise ScopePolicyError(
                    f"scope {scope_id!r} declares unknown evidence {name!r}; "
                    f"known: {sorted(SCOPE_EVIDENCE_VALIDATORS)}"
                )
        graph[scope_id] = ScopeNode(
            id=scope_id,
            approval_required=bool(getattr(scope, "approval_required", False)),
            prior_scopes=priors,
            evidence=evidence,
        )

    for node in graph.values():
        for prior in node.prior_scopes:
            if prior not in graph:
                raise ScopePolicyError(
                    f"scope {node.id!r} declares undeclared prior scope {prior!r}"
                )

    # Cycle detection (DFS with a path stack): a cyclic scope graph can never
    # be satisfied and must be rejected, not guessed.
    state: dict[str, int] = {}

    def visit(scope_id: str, path: tuple[str, ...]) -> None:
        mark = state.get(scope_id, 0)
        if mark == 2:
            return
        if mark == 1:
            cycle = " -> ".join(path + (scope_id,))
            raise ScopePolicyError(f"cyclic scope dependencies: {cycle}")
        state[scope_id] = 1
        for prior in graph[scope_id].prior_scopes:
            visit(prior, path + (scope_id,))
        state[scope_id] = 2

    for scope_id in graph:
        visit(scope_id, ())
    return graph


def scope_requirements(
    graph: Mapping[str, ScopeNode], scope: str,
) -> Optional[ScopeNode]:
    """The compiled requirements for one scope, or None when undeclared."""
    return graph.get(scope)


__all__ = [
    "SCOPE_EVIDENCE_VALIDATORS",
    "ScopeNode",
    "ScopePolicyError",
    "compile_scope_graph",
    "scope_requirements",
]
