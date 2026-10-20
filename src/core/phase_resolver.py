"""Phase-advancement resolver: the G1 plugin escape, executed for real.

The declarative contract carries ``phase_advancement.mode=plugin`` (the
sanctioned G1 escape for completion rules that resist declarative
expression) but the runtime previously rejected the mode outright. This
module executes the skill's ``phases.py`` plugin under the governed
``PluginRunner`` — the qualified isolation/capability rules — and returns
a hybrid verdict: the declarative evidence-key share is a necessary
condition and the plugin owns the remaining completion rule.

Every invocation is attempt-bound: the receipt records the plugin path,
capability grant, input/output digests, and the pinned plugin output
schema version. Plugin failure, timeout, capability violation, bad JSON,
or a schema/version mismatch fail closed with an explicit error — there
is never a silent fallback to the declarative share. Unsupported modes
(notably ``trial_identity.resolve: mode=plugin``) keep their existing
explicit rejection.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from src.core.plugin_runner import PluginResult, PluginRunner
from src.core.skill_manifest import PluginCaps, PluginEntry

PLUGIN_OUTPUT_SCHEMA = "phase-advancement-plugin.v1"


class PluginAdvancementError(RuntimeError):
    """Base error for plugin phase advancement (explicit, fail-closed)."""


class PluginAdvancementRejected(PluginAdvancementError):
    """The declaration itself is unsupported (explicit rejection)."""


class PluginAdvancementFailed(PluginAdvancementError):
    """The plugin ran but its verdict cannot be trusted (fail-closed)."""


@dataclass(frozen=True)
class PluginReceipt:
    """Attempt-bound evidence of one resolver invocation."""

    schema: str
    plugin_path: str
    attempt_id: str
    input_digest: str
    output_digest: str
    caps_digest: str
    plugin_schema_version: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AdvancementVerdict:
    """The hybrid phase-advancement verdict."""

    advance: bool
    source: str  # "declarative" | "hybrid"
    declarative_share: bool
    plugin_rule: Optional[str] = None
    receipt: Optional[PluginReceipt] = None
    notes: tuple[str, ...] = field(default_factory=tuple)


def _digest(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def _declarative_share(
    evidence_keys: Sequence[str], evidence: Mapping[str, Any]
) -> bool:
    return all(key in evidence for key in evidence_keys)


async def resolve_phase_advancement(
    *,
    skill_dir: Path,
    plugin_entry: Optional[PluginEntry],
    mode: str,
    phase_id: str,
    evidence_keys: Sequence[str],
    evidence: Mapping[str, Any],
    attempt_id: str,
    runner: Optional[PluginRunner] = None,
) -> AdvancementVerdict:
    """Resolve one phase's advancement under the declared mode.

    ``mode=declarative``: the existing evidence-key rule, unchanged.
    ``mode=plugin``: the hybrid rule — the declarative share must hold AND
    the plugin's completion rule must hold; the plugin runs under the
    governed capability rules and its verdict is receipt-bound.
    """
    share = _declarative_share(evidence_keys, evidence)
    if mode == "declarative":
        return AdvancementVerdict(
            advance=share,
            source="declarative",
            declarative_share=share,
        )
    if mode != "plugin":
        raise PluginAdvancementRejected(
            f"phase_advancement: unsupported mode {mode!r} is rejected "
            "explicitly (declared vocabulary: declarative, plugin)"
        )
    if plugin_entry is None or plugin_entry.kind != "phase_advancement":
        raise PluginAdvancementRejected(
            "phase_advancement: mode=plugin requires a declared plugins.entries "
            "entry of kind=phase_advancement with its path; declarations "
            "without it are rejected explicitly"
        )

    plugin_runner = runner or PluginRunner()
    caps = plugin_entry.caps or PluginCaps(
        fs_write="none", network_egress=[], env=[]
    )
    input_payload = {
        "schema": PLUGIN_OUTPUT_SCHEMA,
        "phase_id": phase_id,
        "evidence_keys": list(evidence_keys),
        "evidence": dict(evidence),
        "declarative_share": share,
    }
    result: PluginResult = await plugin_runner.run(
        skill_dir=skill_dir,
        plugin=plugin_entry.path,
        kind="phase_advancement",
        input_json=input_payload,
        caps=caps,
        timeout_s=caps.timeout_s,
    )
    if not result.ok:
        raise PluginAdvancementFailed(
            f"phase_advancement plugin failed closed: {result.error}"
        )
    output = dict(result.output or {})
    if output.get("schema") != PLUGIN_OUTPUT_SCHEMA:
        raise PluginAdvancementFailed(
            f"phase_advancement plugin emitted schema {output.get('schema')!r}; "
            f"the pinned schema is {PLUGIN_OUTPUT_SCHEMA!r} — rejected"
        )
    rule = output.get("rule")
    plugin_advance = bool(output.get("advance"))
    receipt = PluginReceipt(
        schema=PLUGIN_OUTPUT_SCHEMA,
        plugin_path=plugin_entry.path,
        attempt_id=attempt_id,
        input_digest=_digest(input_payload),
        output_digest=_digest(output),
        caps_digest=_digest(caps.model_dump(mode="json")),
        plugin_schema_version=str(output.get("schema")),
    )
    return AdvancementVerdict(
        advance=bool(share and plugin_advance),
        source="hybrid",
        declarative_share=share,
        plugin_rule=str(rule) if rule is not None else None,
        receipt=receipt,
        notes=(
            "declarative evidence-key share is necessary; the plugin owns "
            "the remaining completion rule",
        ),
    )
