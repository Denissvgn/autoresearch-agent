"""Machine-readable support matrix for manifest declarations.

Schema parsing is never proof that a skill can execute: every accepted
manifest feature maps here to its implementing handler and its conformance
case. Declarations outside the supported sets are rejected before launch with
a specific unsupported-capability reason; declarations that are accepted but
have no independent behavior are published as ``accepted_advisory`` so they
are visible rather than silently inert.

This module validates and describes only — it never grants execution
authority. Toolchain checks inspect availability (path lookup) and change
nothing about what may run.
"""

from __future__ import annotations

import shutil
from typing import Any, Mapping

#: Vocabulary name -> (supported values, handler, conformance case).
SUPPORT_MATRIX: dict[str, dict[str, Any]] = {
    "output_parser.format": {
        "supported": ["delimited_kv", "json_marker"],
        "handler": "experiment_parser.DelimitedKVParser/JSONMarkerParser",
        "conformance": "tests/test_output_parser.py",
    },
    "command_policy.allowed_executables": {
        "supported": "SUPPORTED_EXECUTABLE_BINDINGS",
        "handler": "command_policy runner contract",
        "conformance": "tests/test_command_policy.py",
    },
    "trial_identity.resolve.mode": {
        "supported": ["declarative"],
        "rejected": {"plugin": "no qualified plugin identity runner exists"},
        "handler": "iteration_snapshot.build_trial_identity",
        "conformance": "tests/test_observation_identity.py",
    },
    "phase_advancement.mode": {
        "supported": ["declarative"],
        "rejected": {"plugin": "no qualified phase-plugin runner exists"},
        "handler": "skill_runtime.ManifestSkillRuntime.phase_advancement_rule",
        "conformance": "tests/test_goal_phase_semantics.py",
    },
    "metric_schema.goal": {
        "supported": ["optimize", "satisfice"],
        "handler": "goal_semantics.goal_decision/goal_outcome",
        "conformance": "tests/test_goal_phase_semantics.py",
    },
    "promotion_target.kind": {
        "supported": ["file_path", "registry_api", "webhook"],
        "rejected": {
            "artifact_store": "artifact-store targets are unimplemented",
            "git_branch": "git-branch targets are unimplemented",
        },
        "handler": "promotion_target.promotion_target_from_manifest",
        "conformance": "tests/test_preflight_support_matrix.py",
    },
    "preflight.kind": {
        "supported": ["http_health", "tcp", "local_file"],
        "handler": "preflight.HTTPHealthCheck/TCPConnectCheck/LocalFileCheck",
        "conformance": "tests/test_preflight_support_matrix.py",
    },
}

#: Accepted by the schema but carrying no independent behavior of its own.
ACCEPTED_ADVISORY: dict[str, str] = {
    "output_parser.nonce_field": (
        "parsed and echoed; forgery rejection is governed by "
        "require_signed_metrics, not by the field name"
    ),
}


def _declared(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(v) for v in value]
    return [str(value)]



def validate_manifest_support(manifest: Any) -> list[Mapping[str, Any]]:
    """Specific unsupported-capability diagnostics for one manifest.

    An empty list means every declared feature is supported (or explicitly
    advisory). Anything else must fail before side effects with the given
    reason — never silently ignored.
    """
    diagnostics: list[Mapping[str, Any]] = []

    def reject(feature: str, declared: str, reason: str, remedy: str) -> None:
        diagnostics.append({
            "feature": feature,
            "declared": declared,
            "reason": reason,
            "remedy": remedy,
            "status": "unsupported",
        })

    metric_schema = getattr(manifest, "metric_schema", None)
    goal = getattr(metric_schema, "goal", None)
    if goal is not None and goal not in SUPPORT_MATRIX["metric_schema.goal"]["supported"]:
        reject("metric_schema.goal", str(goal), "unsupported goal semantics",
               "declare goal=optimize or goal=satisfice")

    output_parser = getattr(manifest, "output_parser", None)
    fmt = getattr(output_parser, "format", None)
    if fmt is not None and fmt not in SUPPORT_MATRIX["output_parser.format"]["supported"]:
        reject("output_parser.format", str(fmt), "no parser handler implements this format",
               "declare delimited_kv or json_marker")

    promotion = getattr(manifest, "promotion_target", None)
    primary = getattr(promotion, "primary", None)
    kind = getattr(primary, "kind", None)
    rejected_kinds = SUPPORT_MATRIX["promotion_target.kind"].get("rejected", {})
    if kind is not None and kind in rejected_kinds:
        reject("promotion_target.kind", str(kind), rejected_kinds[kind],
               "use file_path, registry_api, or webhook until the target is qualified")

    trial_identity = getattr(manifest, "trial_identity", None)
    resolve = getattr(trial_identity, "resolve", None)
    mode = getattr(resolve, "mode", None)
    rejected_modes = SUPPORT_MATRIX["trial_identity.resolve.mode"].get("rejected", {})
    if mode is not None and mode in rejected_modes:
        reject("trial_identity.resolve.mode", str(mode), rejected_modes[mode],
               "declare mode=declarative with hash_fields")

    advancement = getattr(manifest, "phase_advancement", None)
    adv_mode = getattr(advancement, "mode", None)
    rejected_adv = SUPPORT_MATRIX["phase_advancement.mode"].get("rejected", {})
    if adv_mode is not None and adv_mode in rejected_adv:
        reject("phase_advancement.mode", str(adv_mode), rejected_adv[adv_mode],
               "declare mode=declarative with per-phase evidence_keys")
    for phase in getattr(manifest, "phase_plan", None) or []:
        override = getattr(phase, "advancement", None)
        override_mode = getattr(override, "mode", None)
        if override_mode is not None and override_mode in rejected_adv:
            reject(
                f"phase_advancement.mode:{getattr(phase, 'id', '?')}",
                str(override_mode),
                rejected_adv[override_mode],
                "declare mode=declarative with evidence_keys",
            )

    return diagnostics


def toolchain_diagnostics(
    manifest: Any, *, which: Any = shutil.which,
) -> list[Mapping[str, Any]]:
    """Availability diagnostics for declared toolchain names.

    Pure path lookup — this never broadens base execution authority; it only
    reports whether the declared toolchain exists on the host.
    """
    out: list[Mapping[str, Any]] = []
    policy = getattr(manifest, "command_policy", None)
    for name in _declared(getattr(policy, "allowed_executables", None)):
        resolved = which(name)
        out.append({
            "name": name,
            "kind": "executable",
            "available": resolved is not None,
            "resolved_path": resolved,
        })
    for name in _declared(getattr(policy, "allowed_python", None)):
        out.append({
            "name": name,
            "kind": "python_binding",
            "available": True,
            "resolved_path": None,
        })
    return out


def support_descriptor(manifest: Any, *, which: Any = shutil.which) -> Mapping[str, Any]:
    """The machine-readable support/diagnostics descriptor for one skill."""
    diagnostics = validate_manifest_support(manifest)
    toolchain = toolchain_diagnostics(manifest, which=which)
    declared: dict[str, Any] = {
        "output_parser.format": getattr(
            getattr(manifest, "output_parser", None), "format", None
        ),
        "metric_schema.goal": getattr(
            getattr(manifest, "metric_schema", None), "goal", None
        ),
        "promotion_target.kind": getattr(
            getattr(getattr(manifest, "promotion_target", None), "primary", None),
            "kind",
            None,
        ),
    }
    return {
        "schema_version": "skill_support_descriptor.v1",
        "matrix": SUPPORT_MATRIX,
        "accepted_advisory": ACCEPTED_ADVISORY,
        "declared": declared,
        "diagnostics": diagnostics,
        "toolchain": toolchain,
        "supported": not diagnostics,
    }


__all__ = [
    "ACCEPTED_ADVISORY",
    "SUPPORT_MATRIX",
    "support_descriptor",
    "toolchain_diagnostics",
    "validate_manifest_support",
]
