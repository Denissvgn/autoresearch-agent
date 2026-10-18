"""The resolved run specification: immutable inputs, digests, secret refs.

One session's *resolved* run spec is the canonical, versioned record of what
was actually run: parameter values after defaults, the objective/comparison
policy, evaluator/dataset/package content digests, runtime identity, and the
effective nonsecret configuration. It is hashed (``spec_sha256`` covers the
nonsecret spec) and read independently of the current registry or settings —
an interrupted run stays inspectable.

Secrets never enter the spec: a secret-named parameter is recorded as a
reference (environment variable + rebinding policy) and persisted in the
separate ``session_secret_refs`` store surface, never as a credential value.
Old artifacts without a spec are *reported* as missing provenance — never
backfilled with invented current facts.
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

#: Parameter names carrying credential values. Aligned with the command
#: policy's secret vocabulary: values of such parameters are never persisted,
#: only their reference (env var + rebinding policy).
SECRET_NAME_MARKERS: Tuple[str, ...] = (
    "token", "secret", "password", "credential", "api_key", "apikey",
    "auth", "private_key",
)

#: The one rebinding policy for secret references: continuation or resume
#: re-binds the value from the named environment variable, and a missing
#: binding is an explicit operator error — never a silent default.
SECRET_REBIND_POLICY = "operator_explicit"

RUN_SPEC_SCHEMA_VERSION = "research_run_spec.v1"

#: Immutable spec sections whose absence on old artifacts is *reported*.
PROVENANCE_SECTIONS: Tuple[str, ...] = (
    "run_spec", "skill_params", "digests", "runtime_identity",
    "effective_config", "objective_policy", "secret_refs",
)


def is_secret_param_name(name: str) -> bool:
    lowered = str(name).lower()
    return any(marker in lowered for marker in SECRET_NAME_MARKERS)


def _param_env_var(name: str) -> str:
    return "SKILL_PARAM_" + "".join(
        ch if ch.isalnum() else "_" for ch in str(name).upper()
    )


def split_secret_params(
    resolved: Mapping[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Dict[str, str]]]:
    """Split resolved params into (nonsecret values, secret references).

    A secret-named parameter contributes no value to the returned values map;
    its reference names the environment variable a later rebind reads.
    """
    values: Dict[str, Any] = {}
    refs: Dict[str, Dict[str, str]] = {}
    for name in sorted(resolved):
        if is_secret_param_name(name):
            refs[name] = {
                "env_var": _param_env_var(name),
                "rebind_policy": SECRET_REBIND_POLICY,
            }
        else:
            values[name] = resolved[name]
    return values, refs


def file_digests(paths: Mapping[str, Any]) -> Dict[str, str]:
    """Content digests for declared file-valued inputs that exist on disk."""
    digests: Dict[str, str] = {}
    for name in sorted(paths):
        value = paths[name]
        if not isinstance(value, str):
            continue
        path = Path(value)
        try:
            if path.is_file():
                digests[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            continue
    return digests


def package_digests(skill_dir: Optional[str]) -> Dict[str, str]:
    """Content digests of the skill package files the run executes."""
    if not skill_dir:
        return {}
    root = Path(skill_dir)
    digests: Dict[str, str] = {}
    for relpath in ("SKILL.yaml", "SKILL.md", "bootstrap.py"):
        path = root / relpath
        if path.is_file():
            digests[relpath] = hashlib.sha256(path.read_bytes()).hexdigest()
    for sub in ("eval", "tools"):
        directory = root / sub
        if directory.is_dir():
            for path in sorted(directory.rglob("*")):
                if path.is_file():
                    rel = str(path.relative_to(root))
                    digests[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return digests


def skill_package_dir(skill_id: str) -> Optional[str]:
    """The installed skill package directory, when it resolves."""
    try:
        from src.core.skill_registry import DEFAULT_SKILLS_ROOT

        candidate = Path(DEFAULT_SKILLS_ROOT) / skill_id
        if candidate.is_dir():
            return str(candidate)
    except Exception:  # noqa: BLE001 - digests are recorded when resolvable
        return None
    return None


def runtime_identity() -> Dict[str, str]:
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": sys.platform,
    }


def canonical_spec_json(spec: Mapping[str, Any]) -> str:
    payload = dict(spec)
    payload.pop("spec_sha256", None)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def build_run_spec(
    *,
    skill_params: Mapping[str, Any],
    param_schema: Optional[Mapping[str, Any]],
    skill_id: str,
    skill_version: Optional[str],
    skill_dir: Optional[str],
    objective_policy: Mapping[str, Any],
    policy: Mapping[str, Any],
    effective_config: Mapping[str, Any],
    parent_snapshot: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Build the resolved, nonsecret run spec with its content digest."""
    from src.core.skill_params import apply_defaults

    resolved = dict(skill_params or {})
    if param_schema is not None:
        try:
            resolved = apply_defaults(param_schema, resolved)
        except Exception:  # noqa: BLE001 - record raw values if schema rejects
            resolved = dict(skill_params or {})
    defaults_applied = {
        name: value
        for name, value in resolved.items()
        if name not in (skill_params or {})
    }
    values, refs = split_secret_params(resolved)
    package = package_digests(skill_dir)
    spec: Dict[str, Any] = {
        "schema_version": RUN_SPEC_SCHEMA_VERSION,
        "skill_id": skill_id,
        "skill_version": skill_version,
        "skill_params": values,
        "param_defaults_applied": defaults_applied,
        "secret_refs": refs,
        "objective_policy": dict(objective_policy),
        "policy": dict(policy),
        "digests": {
            "skill_manifest_sha256": package.get("SKILL.yaml"),
            "skill_package": package,
            "dataset_inputs": file_digests(resolved),
        },
        "runtime_identity": runtime_identity(),
        "effective_config": dict(effective_config),
        "parent_snapshot": (
            dict(parent_snapshot) if parent_snapshot else None
        ),
    }
    spec["spec_sha256"] = hashlib.sha256(
        canonical_spec_json(spec).encode("utf-8")
    ).hexdigest()
    return spec


def verify_run_spec(spec: Mapping[str, Any]) -> bool:
    """True when the spec's recorded digest matches its nonsecret content."""
    recorded = spec.get("spec_sha256")
    if not isinstance(recorded, str) or not recorded:
        return False
    recomputed = hashlib.sha256(
        canonical_spec_json(spec).encode("utf-8")
    ).hexdigest()
    return recorded == recomputed


def provenance_report(raw_manifest: Mapping[str, Any]) -> Dict[str, Any]:
    """What a persisted artifact records, reports, and lacks — never invents.

    Unknown fields (present on the artifact, absent from the current schema)
    are reported by name; missing immutable provenance sections are reported
    as ``missing``. Nothing is backfilled with current registry or settings
    facts.
    """
    from src.core.research_manifest import ResearchSessionManifest

    known = set(ResearchSessionManifest.model_fields)
    unknown = sorted(key for key in raw_manifest if key not in known)
    missing = [
        name for name in PROVENANCE_SECTIONS
        if raw_manifest.get(name) in (None, {}, [])
    ]
    run_spec = raw_manifest.get("run_spec")
    spec_verified: Optional[bool] = None
    if isinstance(run_spec, Mapping):
        spec_verified = verify_run_spec(run_spec)
    return {
        "artifact_schema_version": raw_manifest.get("schema_version"),
        "unknown_fields": unknown,
        "missing_provenance": missing,
        "spec_digest_verified": spec_verified,
        "reported_not_backfilled": True,
    }


__all__ = [
    "PROVENANCE_SECTIONS",
    "SECRET_NAME_MARKERS",
    "SECRET_REBIND_POLICY",
    "RUN_SPEC_SCHEMA_VERSION",
    "build_run_spec",
    "canonical_spec_json",
    "file_digests",
    "is_secret_param_name",
    "package_digests",
    "provenance_report",
    "runtime_identity",
    "split_secret_params",
    "verify_run_spec",
]

