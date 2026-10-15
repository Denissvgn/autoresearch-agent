"""Versioned research and execution contracts.

Authoritative Pydantic v2 value contracts for the universal research control
plane. They define *what* crosses the kernel boundary — run specifications,
execution requests, candidate and observation identity, evaluator-owned
verified results, objective policy, and capability descriptors — as plain
JSON-serializable value types shared by every integration direction.

Contract rules:

* Every top-level contract carries a ``schema_version`` naming its contract
  family (``research_<name>.v1``); an unknown version fails with an explicit
  error instead of degrading silently.
* Kernel contracts never embed harness SDK types. No provider clients,
  message classes, or vendor payloads appear here; harness-specific settings
  travel as scalar ``effective_config`` entries only.
* Credentials never appear as values. Contracts carry :class:`SecretReference`
  records, or the ``secret://<name>`` wire form inside parameter maps, and
  resolution to real values happens outside these contracts.
* Mutable candidate data stays outside resolved contracts: run specifications
  bind candidates by content digest (:class:`CandidateIdentity`), never by an
  inline payload.

Input layers resolve deterministically (see :func:`resolve_run_inputs`):
explicit run inputs, then skill defaults, then harness preferences, then
system defaults — with operator constraints bounding every step. Harness
preferences fill remaining gaps and can never widen authority.

Compatibility with pre-contract session artifacts and start-request shapes is
explicit: :data:`LEGACY_COMPATIBILITY` classifies each legacy surface as
preserved or rejected-incomplete, and the legacy readers raise
:class:`ContractMigrationError` when a rejected feature is actually requested.
Nothing the mapping classifies as preserved is silently dropped.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, ClassVar, Literal, Mapping, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.compat.legacy_alias import model_type_to_skill_id

# ---------------------------------------------------------------------------
# Versioning
# ---------------------------------------------------------------------------

#: Current version of each contract family. Bump the suffix when a contract's
#: shape changes incompatibly; readers of older shapes live in the legacy
#: reader section below with explicit migration errors.
RUN_SPEC_SCHEMA_VERSION = "research_run_spec.v1"
EXECUTION_REQUEST_SCHEMA_VERSION = "research_execution_request.v1"
CANDIDATE_IDENTITY_SCHEMA_VERSION = "research_candidate_identity.v1"
OBSERVATION_IDENTITY_SCHEMA_VERSION = "research_observation_identity.v1"
VERIFIED_RESULT_SCHEMA_VERSION = "research_verified_result.v1"
OBJECTIVE_POLICY_SCHEMA_VERSION = "research_objective_policy.v1"
CAPABILITY_DESCRIPTOR_SCHEMA_VERSION = "research_capability_descriptor.v1"
LEGACY_RUN_INPUTS_SCHEMA_VERSION = "research_legacy_run_inputs.v1"

CONTRACT_VERSIONS: dict[str, str] = {
    "run_spec": RUN_SPEC_SCHEMA_VERSION,
    "execution_request": EXECUTION_REQUEST_SCHEMA_VERSION,
    "candidate_identity": CANDIDATE_IDENTITY_SCHEMA_VERSION,
    "observation_identity": OBSERVATION_IDENTITY_SCHEMA_VERSION,
    "verified_result": VERIFIED_RESULT_SCHEMA_VERSION,
    "objective_policy": OBJECTIVE_POLICY_SCHEMA_VERSION,
    "capability_descriptor": CAPABILITY_DESCRIPTOR_SCHEMA_VERSION,
    "legacy_run_inputs": LEGACY_RUN_INPUTS_SCHEMA_VERSION,
}


class VersionedContract(BaseModel):
    """Base for top-level contracts: pins ``schema_version`` to its family.

    Subclasses declare their expected version as a class attribute and give
    ``schema_version`` the matching default. Any other version — a newer
    writer or a corrupted artifact — fails explicitly at parse time.
    """

    EXPECTED_SCHEMA_VERSION: ClassVar[str] = ""
    schema_version: str

    @model_validator(mode="after")
    def _check_schema_version(self) -> "VersionedContract":
        if self.schema_version != type(self).EXPECTED_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported schema_version {self.schema_version!r}; expected "
                f"{type(self).EXPECTED_SCHEMA_VERSION!r}"
            )
        return self


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ContractError(ValueError):
    """Base error for contract validation and resolution failures."""


class UnsupportedCapabilityError(ContractError):
    """Raised before work starts when a capability is unknown or unsupported.

    Unknown or unsupported capabilities fail explicitly; nothing silently
    falls back to weaker semantics.
    """


class ContractMigrationError(ContractError):
    """Raised when a legacy payload requests a rejected incomplete feature.

    Carries one entry per offending legacy field so a migration failure names
    every problem at once instead of the first one only.
    """

    def __init__(
        self, message: str, *, issues: Optional[list[Mapping[str, str]]] = None
    ) -> None:
        super().__init__(message)
        self.issues: list[Mapping[str, str]] = list(issues) if issues else []


# ---------------------------------------------------------------------------
# Secret references
# ---------------------------------------------------------------------------

SECRET_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
SECRET_WIRE_PREFIX = "secret://"

#: Parameter keys that must hold a secret reference wire form, never a raw
#: value. Segment-bounded so ordinary keys (``max_tokens``) do not match.
_SECRET_PARAM_KEY_RE = re.compile(
    r"(?:^|[_-])(?:api[_-]?key|token|secret|password|passwd|credentials?)(?:$|[_-])",
    re.IGNORECASE,
)


class SecretReference(BaseModel):
    """A named reference to a credential; never the credential itself.

    ``role`` records why the credential exists and ``scope`` how narrowly it
    is bound. Attached (external-agent) integrations may only reference
    ``harness``/``evaluator`` roles: operator bearer tokens and approver
    secrets are never handed to a driver.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    provider: Literal["env", "vault", "operator"] = "env"
    role: Literal["harness", "evaluator", "operator", "approver"] = "harness"
    scope: Literal["run", "attempt"] = "run"

    @field_validator("name")
    @classmethod
    def _name_shape(cls, value: str) -> str:
        if not SECRET_NAME_RE.match(value):
            raise ValueError(
                "secret reference name must be lowercase alphanumeric with "
                "'.', '_' or '-' separators"
            )
        return value

    def wire_form(self) -> str:
        """Serialize this reference for use as a parameter map value."""
        return f"{SECRET_WIRE_PREFIX}{self.name}"

    @classmethod
    def parse(cls, value: str, **kwargs: Any) -> "SecretReference":
        """Parse the ``secret://<name>`` wire form into a reference."""
        if not isinstance(value, str) or not value.startswith(SECRET_WIRE_PREFIX):
            raise ContractError(f"not a secret reference wire form: {value!r}")
        return cls(name=value[len(SECRET_WIRE_PREFIX):], **kwargs)


def is_secret_reference(value: Any) -> bool:
    """Whether ``value`` is a secret reference wire form (not a raw secret)."""
    return isinstance(value, str) and value.startswith(SECRET_WIRE_PREFIX)


def reject_raw_secret_parameters(parameters: Mapping[str, Any], where: str) -> None:
    """Reject credential-shaped parameter keys that hold raw values."""
    for key, value in parameters.items():
        if _SECRET_PARAM_KEY_RE.search(key) and not is_secret_reference(value):
            raise ContractError(
                f"{where}.{key}: credential-shaped parameters must hold a "
                f"{SECRET_WIRE_PREFIX}<name> reference, never a raw value"
            )


def validate_secret_list(secrets: list[SecretReference], integration: str) -> None:
    """Reject duplicate names and authority-widening roles for attached runs."""
    seen: set[str] = set()
    for ref in secrets:
        if ref.name in seen:
            raise ContractError(f"duplicate secret reference {ref.name!r}")
        seen.add(ref.name)
        if integration == "attached" and ref.role in ("operator", "approver"):
            raise ContractError(
                f"attached integrations cannot reference {ref.role!r} credentials "
                f"({ref.name!r}); operator and approval authority stay server-side"
            )


# ---------------------------------------------------------------------------
# Digests and identity
# ---------------------------------------------------------------------------

DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def canonical_digest(payload: Mapping[str, Any]) -> str:
    """Content digest of a mapping under canonical JSON encoding."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _check_digest(value: str) -> str:
    if not DIGEST_RE.match(value):
        raise ValueError(f"digest must match sha256:<64 hex>, got {value!r}")
    return value


class ArtifactRef(BaseModel):
    """An immutable artifact location bound by content digest."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1)
    digest: str
    path: Optional[str] = None

    @field_validator("digest")
    @classmethod
    def _digest_shape(cls, value: str) -> str:
        return _check_digest(value)


class CandidateIdentity(VersionedContract):
    """Immutable identity of a proposed candidate.

    Identity is the content digest: mutable candidate data may change on
    disk, but every contract that binds a candidate references this digest,
    never the payload.
    """

    model_config = ConfigDict(extra="forbid")

    EXPECTED_SCHEMA_VERSION = CANDIDATE_IDENTITY_SCHEMA_VERSION
    schema_version: str = CANDIDATE_IDENTITY_SCHEMA_VERSION

    candidate_id: str = Field(..., min_length=1)
    digest: str
    parent_digest: Optional[str] = None
    artifacts: list[ArtifactRef] = Field(default_factory=list)

    @field_validator("digest", "parent_digest")
    @classmethod
    def _digest_shape(cls, value: Optional[str]) -> Optional[str]:
        return _check_digest(value) if value is not None else value


class CandidateData(BaseModel):
    """The mutable candidate payload — deliberately outside run contracts.

    Only :class:`CandidateIdentity` (digests and immutable artifact refs)
    enters :class:`RunSpec` / :class:`ExecutionRequest`; payloads live in the
    writable candidate tree and are bound at attempt start.
    """

    model_config = ConfigDict(extra="forbid")

    payload: dict[str, Any]

    def identity(self, candidate_id: str) -> CandidateIdentity:
        """Derive the immutable identity for this payload's current content."""
        return CandidateIdentity(
            candidate_id=candidate_id,
            digest=canonical_digest(self.payload),
        )


class ScorerRef(BaseModel):
    """Identity of the scorer that produced an observation."""

    model_config = ConfigDict(extra="forbid")

    scorer_id: str = Field(..., min_length=1)
    version: str = Field(..., min_length=1)
    digest: Optional[str] = None

    @field_validator("digest")
    @classmethod
    def _digest_shape(cls, value: Optional[str]) -> Optional[str]:
        return _check_digest(value) if value is not None else value


class ObservationIdentity(VersionedContract):
    """Identity of one measured observation of a candidate.

    The evaluation context (scorer, datasets, fidelity) is part of identity
    so results from different contexts can never be compared as if they
    measured the same thing.
    """

    model_config = ConfigDict(extra="forbid")

    EXPECTED_SCHEMA_VERSION = OBSERVATION_IDENTITY_SCHEMA_VERSION
    schema_version: str = OBSERVATION_IDENTITY_SCHEMA_VERSION

    observation_id: str = Field(..., min_length=1)
    candidate_digest: str
    subject_id: str = Field(..., min_length=1)
    variant: str = Field(..., min_length=1)
    seed: Optional[int] = None
    scorer: ScorerRef
    dataset_digests: list[str] = Field(..., min_length=1)
    fidelity: Literal["measured", "simulated"]

    @field_validator("candidate_digest")
    @classmethod
    def _digest_shape(cls, value: str) -> str:
        return _check_digest(value)

    @field_validator("dataset_digests")
    @classmethod
    def _dataset_digests_shape(cls, value: list[str]) -> list[str]:
        for item in value:
            _check_digest(item)
        return value

    def context_digest(self) -> str:
        """Digest of the evaluation context — the comparability key.

        Two observations are comparable only when their context digests
        match; simulated fidelity is a different context from measured.
        """
        return canonical_digest(
            {
                "scorer": self.scorer.model_dump(mode="json"),
                "dataset_digests": list(self.dataset_digests),
                "fidelity": self.fidelity,
            }
        )


# ---------------------------------------------------------------------------
# Objective policy
# ---------------------------------------------------------------------------

ObjectiveDirection = Literal["minimize", "maximize"]
ObjectiveGoal = Literal["optimize", "satisfice"]


class MetricConstraint(BaseModel):
    """A guardrail threshold an eligible result must satisfy."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    metric_field: str = Field(..., min_length=1)
    comparator: Literal["<=", ">=", "<", ">", "=="]
    threshold: float
    required: bool = True


class ObjectivePolicy(VersionedContract):
    """What counts as better, and what must hold for a result to be eligible.

    ``direction`` is authoritative for winner selection and ranking; ties
    within ``tie_tolerance`` are ties, not silent wins for either side.
    """

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    EXPECTED_SCHEMA_VERSION = OBJECTIVE_POLICY_SCHEMA_VERSION
    schema_version: str = OBJECTIVE_POLICY_SCHEMA_VERSION

    metric_field: str = Field(..., min_length=1)
    direction: ObjectiveDirection
    goal: ObjectiveGoal = "optimize"
    constraints: list[MetricConstraint] = Field(default_factory=list)
    tie_tolerance: float = Field(default=0.0, ge=0.0)


def objective_policy_from_skill_metric(
    *,
    metric_field: str,
    direction: Literal["higher_is_better", "lower_is_better"],
    goal: ObjectiveGoal = "optimize",
) -> ObjectivePolicy:
    """Map a skill manifest metric declaration to its objective policy.

    Skill descriptors express direction as ``higher_is_better`` /
    ``lower_is_better``; kernel contracts express it as winner-selection
    direction. This helper is the single place that knows both vocabularies.
    """
    return ObjectivePolicy(
        metric_field=metric_field,
        direction="maximize" if direction == "higher_is_better" else "minimize",
        goal=goal,
    )


# ---------------------------------------------------------------------------
# Capabilities and isolation boundary
# ---------------------------------------------------------------------------

IntegrationDirection = Literal["managed", "attached"]

#: Capability vocabulary. A descriptor may only name these identifiers;
#: anything unknown is an explicit error, never an ignored extra.
KNOWN_CAPABILITIES: frozenset[str] = frozenset(
    {
        "start",
        "event_stream",
        "cancel",
        "close",
        "pause",
        "resume",
        "mid_run_input",
        "usage_reporting",
        "os_isolation",
        "immutable_artifacts",
    }
)

#: What every usable harness/executor must support before work starts.
MINIMUM_SUPPORTED_CAPABILITIES: frozenset[str] = frozenset(
    {
        "start",
        "event_stream",
        "cancel",
        "close",
        "os_isolation",
        "immutable_artifacts",
    }
)


class CapabilityDescriptor(VersionedContract):
    """What a harness/driver can do — with explicit gaps, never silent ones.

    ``capabilities`` names what is supported; ``unsupported`` names what is
    not, with a reason. Optional behaviors (pause, resume, mid-run input)
    are absent from ``capabilities`` unless genuinely available: an
    unsupported pause must not be equated with killing the process.
    """

    model_config = ConfigDict(extra="forbid")

    EXPECTED_SCHEMA_VERSION = CAPABILITY_DESCRIPTOR_SCHEMA_VERSION
    schema_version: str = CAPABILITY_DESCRIPTOR_SCHEMA_VERSION

    integration: IntegrationDirection
    adapter_id: str = Field(..., min_length=1)
    protocol_version: str = Field(..., min_length=1)
    capabilities: list[str] = Field(default_factory=list)
    unsupported: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _capability_vocabulary(self) -> "CapabilityDescriptor":
        named = set(self.capabilities)
        unknown = (named | set(self.unsupported)) - KNOWN_CAPABILITIES
        if unknown:
            raise ValueError(f"unknown capability identifier(s): {sorted(unknown)}")
        if len(self.capabilities) != len(named):
            raise ValueError("capabilities must not contain duplicates")
        overlap = named & set(self.unsupported)
        if overlap:
            raise ValueError(
                f"capabilities both claimed and reported unsupported: {sorted(overlap)}"
            )
        return self


def ensure_minimum_capabilities(
    descriptor: CapabilityDescriptor, *, required: frozenset[str] = MINIMUM_SUPPORTED_CAPABILITIES
) -> None:
    """Fail before work starts when required capabilities are unavailable."""
    missing = required - set(descriptor.capabilities)
    if missing:
        reasons = {
            name: descriptor.unsupported.get(name, "not provided") for name in sorted(missing)
        }
        raise UnsupportedCapabilityError(
            f"harness {descriptor.adapter_id!r} lacks required capabilities: "
            f"{sorted(missing)} ({reasons})"
        )


def ensure_capabilities_allowed(
    descriptor: CapabilityDescriptor, *, allowed: frozenset[str]
) -> None:
    """Fail when a descriptor claims capabilities beyond the allowed set.

    Operator constraints grant authority; no driver or preference layer can
    widen it by claiming extra capabilities.
    """
    unknown = allowed - KNOWN_CAPABILITIES
    if unknown:
        raise ContractError(f"operator allowance names unknown capabilities: {sorted(unknown)}")
    excess = set(descriptor.capabilities) - allowed
    if excess:
        raise UnsupportedCapabilityError(
            f"harness {descriptor.adapter_id!r} claims capabilities outside the "
            f"operator allowance: {sorted(excess)}"
        )


class IsolationBoundary(BaseModel):
    """Declared enforcement boundary for untrusted execution.

    The qualified boundary is Linux with operating-system enforcement.
    Application-only checks do not confine hostile code and are rejected
    wherever an enforced boundary is required.
    """

    model_config = ConfigDict(extra="forbid")

    platform: Literal["linux"]
    enforcement: Literal["os", "application"]
    process_isolation: bool
    filesystem_confinement: bool
    network_policy: bool
    resource_limits: bool


#: The qualified isolation boundary: Linux with OS-level enforcement of
#: process, filesystem, network, and resource policy.
LINUX_ISOLATION_BOUNDARY = IsolationBoundary(
    platform="linux",
    enforcement="os",
    process_isolation=True,
    filesystem_confinement=True,
    network_policy=True,
    resource_limits=True,
)


def ensure_isolation_boundary(boundary: IsolationBoundary) -> None:
    """Reject any boundary weaker than the qualified OS-enforced one."""
    gaps = [
        name
        for name, ok in (
            ("process_isolation", boundary.process_isolation),
            ("filesystem_confinement", boundary.filesystem_confinement),
            ("network_policy", boundary.network_policy),
            ("resource_limits", boundary.resource_limits),
        )
        if not ok
    ]
    if boundary.enforcement != "os" or gaps:
        raise UnsupportedCapabilityError(
            f"isolation boundary not enforced by the operating system "
            f"(enforcement={boundary.enforcement!r}, missing={gaps}); "
            "application-only checks cannot confine untrusted execution"
        )


# ---------------------------------------------------------------------------
# Verified results
# ---------------------------------------------------------------------------


class FailureRecord(BaseModel):
    """Structured failure detail for an attempt that produced no metrics."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., min_length=1)
    message: str
    stage: Literal["staging", "execution", "evaluation", "ingestion"]
    retryable: bool = False


class ResultReceipt(BaseModel):
    """Replay protection and ownership for a result envelope.

    The receipt binds a result to one evaluator run in one ownership epoch;
    a replayed or stale receipt is detectable without trusting the sender's
    claims about metrics.
    """

    model_config = ConfigDict(extra="forbid")

    receipt_id: str = Field(..., min_length=1)
    nonce: str = Field(..., min_length=1)
    ownership_epoch: int = Field(..., ge=1)
    sequence: int = Field(..., ge=0)
    envelope_digest: str

    @field_validator("envelope_digest")
    @classmethod
    def _digest_shape(cls, value: str) -> str:
        return _check_digest(value)


class VerifiedResult(VersionedContract):
    """An evaluator-owned measurement of one candidate in one context.

    Authoritative metrics arrive through this envelope from the trusted
    evaluator channel. Model output may propose candidates and annotate
    results, but it never fills this contract. Third-party results carry
    ``provenance="imported"`` and stay ``unverified_imported`` until
    independently validated.
    """

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    EXPECTED_SCHEMA_VERSION = VERIFIED_RESULT_SCHEMA_VERSION
    schema_version: str = VERIFIED_RESULT_SCHEMA_VERSION

    result_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    attempt_id: str = Field(..., min_length=1)
    candidate: CandidateIdentity
    observation: ObservationIdentity
    status: Literal["succeeded", "failed", "timeout", "rejected"]
    metrics: dict[str, float] = Field(default_factory=dict)
    failure: Optional[FailureRecord] = None
    evaluator_digest: str
    receipt: ResultReceipt
    produced_at: str = Field(..., min_length=1)
    provenance: Literal["evaluator_owned", "imported"]
    verification: Literal["verified", "unverified_imported"]

    @field_validator("evaluator_digest")
    @classmethod
    def _digest_shape(cls, value: str) -> str:
        return _check_digest(value)

    @model_validator(mode="after")
    def _status_consistency(self) -> "VerifiedResult":
        if self.status == "succeeded":
            if not self.metrics:
                raise ValueError("succeeded results must carry metrics")
            if self.failure is not None:
                raise ValueError("succeeded results must not carry a failure record")
        else:
            if self.metrics:
                raise ValueError(
                    f"status {self.status!r} must not claim metrics; only a "
                    "succeeded evaluation produces authoritative values"
                )
            if self.failure is None:
                raise ValueError(f"status {self.status!r} requires a failure record")
        if self.provenance == "imported" and self.verification != "unverified_imported":
            raise ValueError(
                "imported third-party results must stay unverified_imported "
                "until independently validated"
            )
        if self.provenance == "evaluator_owned" and self.verification != "verified":
            raise ValueError(
                "evaluator-owned results are verified by construction; use "
                "provenance='imported' for anything else"
            )
        return self


# ---------------------------------------------------------------------------
# Execution request
# ---------------------------------------------------------------------------


class WorkspaceBounds(BaseModel):
    """Where an attempt may write and what it may only read."""

    model_config = ConfigDict(extra="forbid")

    writable_roots: list[str] = Field(..., min_length=1)
    read_only_roots: list[str] = Field(default_factory=list)


class NetworkPolicy(BaseModel):
    """Network authority for one attempt; deny is the default posture."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["deny", "allowlist"] = "deny"
    allowed_hosts: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _allowlist_consistency(self) -> "NetworkPolicy":
        if self.mode == "deny" and self.allowed_hosts:
            raise ValueError("deny network policy must not list allowed hosts")
        return self


class ResourceLimits(BaseModel):
    """OS-enforced resource ceilings for one attempt."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    wall_clock_s: int = Field(..., ge=1)
    memory_mb: int = Field(..., ge=1)
    max_processes: int = Field(..., ge=1)


class ExecutionRequest(VersionedContract):
    """One approved attempt: what the experiment executor may execute.

    The executor resolves this request against the pinned run specification,
    stages inputs, enforces the declared policy, executes, and collects
    artifacts. A harness that runs its own shell still faces this contract;
    it cannot bypass trusted evaluation.
    """

    model_config = ConfigDict(extra="forbid")

    EXPECTED_SCHEMA_VERSION = EXECUTION_REQUEST_SCHEMA_VERSION
    schema_version: str = EXECUTION_REQUEST_SCHEMA_VERSION

    request_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    attempt_id: str = Field(..., min_length=1)
    integration: IntegrationDirection
    run_spec_digest: str
    candidate: CandidateIdentity
    evaluator_digest: str
    dataset_digests: list[str] = Field(..., min_length=1)
    environment_digest: str
    workspace: WorkspaceBounds
    network: NetworkPolicy
    resources: ResourceLimits
    secrets: list[SecretReference] = Field(default_factory=list)

    @field_validator("run_spec_digest", "evaluator_digest", "environment_digest")
    @classmethod
    def _digest_shape(cls, value: str) -> str:
        return _check_digest(value)

    @field_validator("dataset_digests")
    @classmethod
    def _dataset_digests_shape(cls, value: list[str]) -> list[str]:
        for item in value:
            _check_digest(item)
        return value

    @model_validator(mode="after")
    def _secret_rules(self) -> "ExecutionRequest":
        validate_secret_list(self.secrets, self.integration)
        return self


# ---------------------------------------------------------------------------
# Run specification
# ---------------------------------------------------------------------------


class SkillPackageRef(BaseModel):
    """The exact skill package a run executes."""

    model_config = ConfigDict(extra="forbid")

    skill_id: str = Field(..., min_length=1)
    version: str = Field(..., min_length=1)
    digest: str

    @field_validator("digest")
    @classmethod
    def _digest_shape(cls, value: str) -> str:
        return _check_digest(value)


class HarnessConfig(BaseModel):
    """Harness identity and effective configuration.

    ``effective_config`` and ``model_roles`` hold scalar values only — no
    harness SDK objects enter a kernel contract.
    """

    model_config = ConfigDict(extra="forbid")

    adapter_id: str = Field(..., min_length=1)
    protocol_version: str = Field(..., min_length=1)
    effective_config: dict[str, str] = Field(default_factory=dict)
    model_roles: dict[str, str] = Field(default_factory=dict)


class EnvironmentIdentity(BaseModel):
    """Pinned execution environment: image or dependency-lock digest."""

    model_config = ConfigDict(extra="forbid")

    image_digest: Optional[str] = None
    dependency_lock_digest: Optional[str] = None

    @model_validator(mode="after")
    def _at_least_one(self) -> "EnvironmentIdentity":
        if self.image_digest is None and self.dependency_lock_digest is None:
            raise ValueError("environment identity requires an image or lock digest")
        return self

    @field_validator("image_digest", "dependency_lock_digest")
    @classmethod
    def _digest_shape(cls, value: Optional[str]) -> Optional[str]:
        return _check_digest(value) if value is not None else value

    def digest(self) -> str:
        """Single digest covering whichever identities were pinned."""
        return canonical_digest(self.model_dump(mode="json"))


class BudgetDimensions(BaseModel):
    """Spend ceilings for a run; every dimension is explicit."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    max_iterations: int = Field(..., ge=1)
    max_budget_usd: float = Field(..., ge=0.0)
    timeout_s: int = Field(..., ge=1)
    max_concurrency: int = Field(default=1, ge=1)


class RunInputs(BaseModel):
    """Pinned input identities: what the run evaluates against."""

    model_config = ConfigDict(extra="forbid")

    candidate_input_digests: list[str] = Field(default_factory=list)
    evaluator_digest: str
    dataset_digests: list[str] = Field(..., min_length=1)
    environment: EnvironmentIdentity

    @field_validator("candidate_input_digests", "dataset_digests")
    @classmethod
    def _digests_shape(cls, value: list[str]) -> list[str]:
        for item in value:
            _check_digest(item)
        return value

    @field_validator("evaluator_digest")
    @classmethod
    def _digest_shape(cls, value: str) -> str:
        return _check_digest(value)


class RunLineage(BaseModel):
    """Continuation provenance: where this run came from and how to resume."""

    model_config = ConfigDict(extra="forbid")

    parent_run_id: Optional[str] = None
    checkpoint_refs: list[str] = Field(default_factory=list)
    focus_hint: Optional[str] = None


class RunSpec(VersionedContract):
    """The persisted, fully resolved run specification.

    Everything needed to reproduce and audit a run is pinned here: skill
    package identity and validated nonsecret parameters, harness identity
    and scalar effective configuration, input digests and environment
    identity, capability and policy versions, budget dimensions, objective
    policy, continuation lineage, and immutable artifact locations.

    Mutable candidate data never appears inline — candidates are bound by
    digest. Credentials appear only as :class:`SecretReference` records.
    """

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    EXPECTED_SCHEMA_VERSION = RUN_SPEC_SCHEMA_VERSION
    schema_version: str = RUN_SPEC_SCHEMA_VERSION

    run_id: str = Field(..., min_length=1)
    integration: IntegrationDirection
    skill: SkillPackageRef
    parameters: dict[str, Any] = Field(default_factory=dict)
    harness: HarnessConfig
    inputs: RunInputs
    capabilities: CapabilityDescriptor
    isolation: IsolationBoundary
    policy_version: str = Field(..., min_length=1)
    budget: BudgetDimensions
    objective: ObjectivePolicy
    lineage: RunLineage = Field(default_factory=RunLineage)
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    secrets: list[SecretReference] = Field(default_factory=list)

    @model_validator(mode="after")
    def _contract_consistency(self) -> "RunSpec":
        reject_raw_secret_parameters(self.parameters, "parameters")
        validate_secret_list(self.secrets, self.integration)
        if self.capabilities.integration != self.integration:
            raise ValueError(
                "capability descriptor integration "
                f"{self.capabilities.integration!r} must match run integration "
                f"{self.integration!r}"
            )
        return self

    def spec_digest(self) -> str:
        """Canonical digest of the resolved specification.

        Execution requests reference this digest so an attempt can only run
        against exactly this resolved configuration.
        """
        return canonical_digest(self.model_dump(mode="json"))


def ensure_request_matches_run_spec(request: "ExecutionRequest", spec: RunSpec) -> None:
    """Verify an execution request is bound to exactly this run specification.

    The digest reference is authoritative, but a mismatch in any pinned input
    identity is also a binding failure: an attempt may not run against a
    different evaluator, dataset, environment, or integration direction than
    the resolved specification approved.
    """
    mismatches: list[str] = []
    if request.run_spec_digest != spec.spec_digest():
        mismatches.append("run_spec_digest")
    if request.run_id != spec.run_id:
        mismatches.append("run_id")
    if request.integration != spec.integration:
        mismatches.append("integration")
    if request.evaluator_digest != spec.inputs.evaluator_digest:
        mismatches.append("evaluator_digest")
    if request.dataset_digests != spec.inputs.dataset_digests:
        mismatches.append("dataset_digests")
    if request.environment_digest != spec.inputs.environment.digest():
        mismatches.append("environment_digest")
    if mismatches:
        raise ContractError(
            f"execution request {request.request_id!r} is not bound to run "
            f"specification {spec.run_id!r}: mismatched {sorted(mismatches)}"
        )


# ---------------------------------------------------------------------------
# Input layers and precedence
# ---------------------------------------------------------------------------

#: Conservative system defaults — the lowest-precedence value source. One
#: iteration, no spend, one hour, strictly sequential.
SYSTEM_DEFAULTS: dict[str, Any] = {
    "max_iterations": 1,
    "max_budget_usd": 0.0,
    "timeout_s": 3600,
    "max_concurrency": 1,
}

#: Budget fields whose value sources participate in precedence.
_RESOLVABLE_BUDGET_FIELDS = (
    "max_iterations",
    "max_budget_usd",
    "timeout_s",
    "max_concurrency",
)


class OperatorConstraints(BaseModel):
    """Authority bounds. Every resolved value falls inside these limits.

    Constraints are ceilings, not values: they never supply defaults and no
    lower-precedence layer (nor a harness preference) can widen them.
    """

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    max_iterations: Optional[int] = Field(default=None, ge=1)
    max_budget_usd: Optional[float] = Field(default=None, ge=0.0)
    timeout_s: Optional[int] = Field(default=None, ge=1)
    max_concurrency: Optional[int] = Field(default=None, ge=1)
    allowed_capabilities: list[str] = Field(default_factory=list)
    allowed_integrations: list[IntegrationDirection] = Field(
        default_factory=lambda: ["managed", "attached"]
    )

    @field_validator("allowed_capabilities")
    @classmethod
    def _capability_vocabulary(cls, value: list[str]) -> list[str]:
        unknown = set(value) - KNOWN_CAPABILITIES
        if unknown:
            raise ValueError(f"unknown capability identifier(s): {sorted(unknown)}")
        return value


class SkillDefaults(BaseModel):
    """Defaults declared by the skill package (domain behavior)."""

    model_config = ConfigDict(extra="forbid")

    parameters: dict[str, Any] = Field(default_factory=dict)
    budget: dict[str, Any] = Field(default_factory=dict)
    model_roles: dict[str, str] = Field(default_factory=dict)


class HarnessPreferences(BaseModel):
    """Harness-level convenience defaults. Advisory only.

    Preferences fill gaps that no higher layer resolved and can never widen
    authority: they are bounded by operator constraints exactly like explicit
    inputs, and they do not supply domain parameter values.
    """

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    max_concurrency: Optional[int] = Field(default=None, ge=1)
    timeout_s: Optional[int] = Field(default=None, ge=1)
    model_roles: dict[str, str] = Field(default_factory=dict)


class ResolutionRecord(BaseModel):
    """Provenance of one resolved value — nothing resolves silently."""

    model_config = ConfigDict(extra="forbid")

    field: str
    source: Literal["explicit", "skill_default", "harness_preference", "system_default"]
    requested: Optional[Any] = None
    effective: Any
    bounded: bool = False


class ResolvedRunInputs(BaseModel):
    """Deterministically resolved inputs with per-field provenance."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    parameters: dict[str, Any]
    budget: BudgetDimensions
    model_roles: dict[str, str]
    records: list[ResolutionRecord]


def _chain_pick(
    field: str,
    *,
    explicit: Mapping[str, Any],
    skill_defaults: Mapping[str, Any],
    preferences: Mapping[str, Any],
    system_defaults: Mapping[str, Any],
) -> tuple[Any, str]:
    """Resolve one field through the precedence chain (no bounding yet)."""
    for source, layer in (
        ("explicit", explicit),
        ("skill_default", skill_defaults),
        ("harness_preference", preferences),
        ("system_default", system_defaults),
    ):
        if field in layer and layer[field] is not None:
            return layer[field], source
    raise ContractError(f"no layer supplies required field {field!r}")


def resolve_run_inputs(
    *,
    operator: OperatorConstraints,
    explicit: Optional[Mapping[str, Any]] = None,
    skill_defaults: Optional[SkillDefaults] = None,
    harness_preferences: Optional[HarnessPreferences] = None,
    system_defaults: Optional[Mapping[str, Any]] = None,
) -> ResolvedRunInputs:
    """Resolve run inputs with deterministic precedence and hard bounds.

    Value precedence, highest first: explicit run inputs, then skill
    defaults, then harness preferences, then system defaults. Operator
    constraints bound every step: a resolved numeric value outside a
    constraint is clamped to the bound with ``bounded=True`` and the original
    request preserved in the record — nothing widens authority silently.

    Domain parameters resolve per key from explicit inputs, then skill
    defaults, then system defaults. Harness preferences never set domain
    parameters: they are harness convenience, not domain behavior. The four
    budget field names are reserved: they resolve into budget dimensions and
    never into domain parameters.
    """
    explicit = dict(explicit or {})
    skill = skill_defaults or SkillDefaults()
    prefs = harness_preferences or HarnessPreferences()
    system = dict(system_defaults if system_defaults is not None else SYSTEM_DEFAULTS)

    reject_raw_secret_parameters(explicit, "explicit inputs")
    reject_raw_secret_parameters(skill.parameters, "skill defaults")

    records: list[ResolutionRecord] = []
    budget_values: dict[str, Any] = {}
    for field in _RESOLVABLE_BUDGET_FIELDS:
        value, source = _chain_pick(
            field,
            explicit=explicit,
            skill_defaults=skill.budget,
            preferences={
                "max_concurrency": prefs.max_concurrency,
                "timeout_s": prefs.timeout_s,
            },
            system_defaults=system,
        )
        requested = value
        minimum = 0.0 if field == "max_budget_usd" else 1
        if value < minimum:
            raise ContractError(f"{field}: limit {value!r} below minimum {minimum}")
        bound = getattr(operator, field)
        bounded = False
        if bound is not None and value > bound:
            value, bounded = bound, True
        budget_values[field] = value
        records.append(
            ResolutionRecord(
                field=f"budget.{field}",
                source=source,
                requested=requested,
                effective=value,
                bounded=bounded,
            )
        )

    parameters: dict[str, Any] = {}
    # Budget field names are reserved: they resolve into budget dimensions
    # above and never leak into domain parameters.
    parameter_keys = (set(skill.parameters) | set(explicit)) - set(_RESOLVABLE_BUDGET_FIELDS)
    for key in sorted(parameter_keys):
        value, source = _chain_pick(
            key,
            explicit=explicit,
            skill_defaults=skill.parameters,
            preferences={},
            system_defaults=system if key in system else {},
        )
        parameters[key] = value
        records.append(
            ResolutionRecord(
                field=f"parameters.{key}", source=source, requested=None, effective=value
            )
        )

    model_roles: dict[str, str] = {}
    for key in sorted(set(skill.model_roles) | set(prefs.model_roles)):
        value, source = _chain_pick(
            key,
            explicit={},
            skill_defaults=skill.model_roles,
            preferences=prefs.model_roles,
            system_defaults={},
        )
        model_roles[key] = value
        records.append(
            ResolutionRecord(
                field=f"model_roles.{key}", source=source, requested=None, effective=value
            )
        )

    return ResolvedRunInputs(
        parameters=parameters,
        budget=BudgetDimensions(**budget_values),
        model_roles=model_roles,
        records=records,
    )


# ---------------------------------------------------------------------------
# Legacy readers and the v1 compatibility mapping
# ---------------------------------------------------------------------------


class LegacyFieldCompat(BaseModel):
    """One legacy surface's disposition under the v1 contracts."""

    model_config = ConfigDict(extra="forbid")

    legacy_field: str
    disposition: Literal["preserved", "rejected"]
    contract_field: Optional[str] = None
    reason: str
    #: For rejected entries: when the payload merely carries the field the
    #: reader tolerates it; when it *requests* the feature (non-empty value)
    #: the reader raises an explicit migration error.
    rejected_when: Optional[str] = None


#: The v1 compatibility mapping. ``preserved`` entries keep their behavior
#: (mapped to a contract field or explicitly retained on existing surfaces);
#: ``rejected`` entries name incomplete features that the v1 contracts refuse
#: to pretend are supported. Serialized form:
#: ``examples/contracts/v1/legacy-compatibility.json``.
LEGACY_COMPATIBILITY: tuple[LegacyFieldCompat, ...] = (
    LegacyFieldCompat(
        legacy_field="schema_version",
        disposition="preserved",
        contract_field="reader gate",
        reason="session artifacts v1-v3 are accepted and normalized by the reader",
    ),
    LegacyFieldCompat(
        legacy_field="skill_id / model_type",
        disposition="preserved",
        contract_field="SkillPackageRef.skill_id",
        reason="legacy model_type aliases resolve through the alias registry",
    ),
    LegacyFieldCompat(
        legacy_field="subject_id / instrument",
        disposition="preserved",
        contract_field="ObservationIdentity.subject_id",
        reason="legacy identity fields map to canonical subject identity",
    ),
    LegacyFieldCompat(
        legacy_field="variant / timeframe",
        disposition="preserved",
        contract_field="ObservationIdentity.variant",
        reason="legacy identity fields map to canonical variant identity",
    ),
    LegacyFieldCompat(
        legacy_field="budget.max_budget_usd",
        disposition="preserved",
        contract_field="BudgetDimensions.max_budget_usd",
        reason="spend ceilings carry over unchanged",
    ),
    LegacyFieldCompat(
        legacy_field="max_iterations",
        disposition="preserved",
        contract_field="BudgetDimensions.max_iterations",
        reason="iteration ceilings carry over unchanged",
    ),
    LegacyFieldCompat(
        legacy_field="timeout_s / timeout_minutes",
        disposition="preserved",
        contract_field="BudgetDimensions.timeout_s",
        reason="time ceilings carry over; minute values convert to seconds",
    ),
    LegacyFieldCompat(
        legacy_field="objective",
        disposition="preserved",
        contract_field="LegacyRunInputs.legacy_objective_text",
        reason="descriptive objective text is preserved verbatim; metric "
        "semantics come from the skill metric declaration",
    ),
    LegacyFieldCompat(
        legacy_field="skill_params",
        disposition="preserved",
        contract_field="RunSpec.parameters",
        reason="nonsecret parameters migrate; credential-shaped keys must "
        "already use secret references",
    ),
    LegacyFieldCompat(
        legacy_field="focus_hint",
        disposition="preserved",
        contract_field="RunLineage.focus_hint",
        reason="continuation guidance is preserved through restart",
    ),
    LegacyFieldCompat(
        legacy_field="skill / metric_schema",
        disposition="preserved",
        contract_field="ObjectivePolicy",
        reason="the skill's metric declaration yields the objective policy",
    ),
    LegacyFieldCompat(
        legacy_field="manifest_hash",
        disposition="preserved",
        contract_field="artifact digest evidence",
        reason="existing manifest digests remain provenance evidence",
    ),
    LegacyFieldCompat(
        legacy_field="tag / quick_mode / hpo / legacy provenance sections",
        disposition="preserved",
        contract_field=None,
        reason="retained on their existing session surfaces as-is; no v1 "
        "contract field, so migration neither maps nor drops them",
    ),
    LegacyFieldCompat(
        legacy_field="session_nonce",
        disposition="rejected",
        contract_field=None,
        rejected_when="non-empty",
        reason="nonce-echo self-verification is an incomplete trust feature; "
        "verified results require an evaluator receipt, and legacy "
        "self-claims migrate as unverified_imported at best",
    ),
    LegacyFieldCompat(
        legacy_field="mlflow_experiment",
        disposition="rejected",
        contract_field=None,
        rejected_when="non-empty",
        reason="experiment-tracking integration was never implemented; "
        "accepting the field would promise inert behavior",
    ),
)


class LegacyRunInputs(VersionedContract):
    """What a legacy payload migrates into: identity, parameters, budget."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    EXPECTED_SCHEMA_VERSION = LEGACY_RUN_INPUTS_SCHEMA_VERSION
    schema_version: str = LEGACY_RUN_INPUTS_SCHEMA_VERSION

    source_schema: str = Field(..., min_length=1)
    skill_id: str = Field(..., min_length=1)
    subject_id: str = Field(..., min_length=1)
    variant: str = Field(..., min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)
    budget: BudgetDimensions
    legacy_objective_text: Optional[str] = None
    focus_hint: Optional[str] = None
    preserved_fields: list[str] = Field(default_factory=list)
    absent_rejected_fields: list[str] = Field(default_factory=list)


_LEGACY_SESSION_SCHEMA_VERSIONS = frozenset(
    {
        "research_session_manifest.v1",
        "research_session_manifest.v2",
        "research_session_manifest.v3",
    }
)

_REJECTED_FIELDS = tuple(
    entry for entry in LEGACY_COMPATIBILITY if entry.disposition == "rejected"
)


def _is_requested(value: Any) -> bool:
    """Whether a legacy payload actually requests a feature (non-empty)."""
    return value is not None and value != "" and value != [] and value != {}


def _check_rejected_fields(payload: Mapping[str, Any]) -> list[str]:
    """Raise on requested rejected features; return absent tolerated ones."""
    issues: list[Mapping[str, str]] = []
    absent: list[str] = []
    for entry in _REJECTED_FIELDS:
        value = payload.get(entry.legacy_field)
        if _is_requested(value):
            issues.append(
                {
                    "legacy_field": entry.legacy_field,
                    "reason": entry.reason,
                    "remediation": (
                        "clear the field before migration or keep the run on "
                        "the legacy surfaces"
                    ),
                }
            )
        else:
            absent.append(entry.legacy_field)
    if issues:
        raise ContractMigrationError(
            f"legacy payload requests rejected incomplete feature(s): "
            f"{sorted(i['legacy_field'] for i in issues)}",
            issues=issues,
        )
    return absent


def _require_identity(payload: Mapping[str, Any]) -> tuple[str, str, str, list[str]]:
    """Resolve (skill_id, subject_id, variant) plus consumed legacy fields."""
    consumed: list[str] = []
    if payload.get("skill_id"):
        skill_id = str(payload["skill_id"])
        consumed.append("skill_id")
    elif payload.get("model_type"):
        skill_id = model_type_to_skill_id(str(payload["model_type"]))
        consumed.append("model_type")
    else:
        raise ContractMigrationError(
            "legacy payload carries neither skill_id nor model_type",
            issues=[{"legacy_field": "skill_id/model_type", "reason": "identity missing"}],
        )
    if payload.get("subject_id"):
        subject_id, subject_src = str(payload["subject_id"]), "subject_id"
    elif payload.get("instrument"):
        subject_id, subject_src = str(payload["instrument"]), "instrument"
    else:
        raise ContractMigrationError(
            "legacy payload carries neither subject_id nor instrument",
            issues=[{"legacy_field": "subject_id/instrument", "reason": "identity missing"}],
        )
    consumed.append(subject_src)
    if payload.get("variant"):
        variant = str(payload["variant"])
        consumed.append("variant")
    elif payload.get("timeframe"):
        variant = str(payload["timeframe"])
        consumed.append("timeframe")
    else:
        raise ContractMigrationError(
            "legacy payload carries neither variant nor timeframe",
            issues=[{"legacy_field": "variant/timeframe", "reason": "identity missing"}],
        )
    return skill_id, subject_id, variant, consumed


def read_legacy_session_manifest(payload: Mapping[str, Any]) -> LegacyRunInputs:
    """Migrate a serialized session manifest (v1-v3) into contract inputs.

    Preserved fields migrate; a requested rejected feature raises
    :class:`ContractMigrationError` naming every offending field. Required
    manifest fields must be present — the reader never invents a budget.
    """
    schema_version = payload.get("schema_version")
    if schema_version not in _LEGACY_SESSION_SCHEMA_VERSIONS:
        raise ContractMigrationError(
            f"unsupported legacy manifest schema_version {schema_version!r}; "
            f"expected one of {sorted(_LEGACY_SESSION_SCHEMA_VERSIONS)}",
            issues=[{"legacy_field": "schema_version", "reason": "unknown schema"}],
        )
    absent_rejected = _check_rejected_fields(payload)
    skill_id, subject_id, variant, consumed = _require_identity(payload)

    budget_block = payload.get("budget")
    if not isinstance(budget_block, Mapping) or "max_budget_usd" not in budget_block:
        raise ContractMigrationError(
            "legacy manifest is missing budget.max_budget_usd",
            issues=[{"legacy_field": "budget", "reason": "required field missing"}],
        )
    for field in ("max_iterations", "timeout_s"):
        if field not in payload:
            raise ContractMigrationError(
                f"legacy manifest is missing required field {field!r}",
                issues=[{"legacy_field": field, "reason": "required field missing"}],
            )
    budget = BudgetDimensions(
        max_iterations=int(payload["max_iterations"]),
        max_budget_usd=float(budget_block["max_budget_usd"]),
        timeout_s=int(payload["timeout_s"]),
    )
    consumed.extend(["budget", "max_iterations", "timeout_s"])

    parameters = dict(payload.get("skill_params") or {})
    reject_raw_secret_parameters(parameters, "legacy skill_params")
    if parameters:
        consumed.append("skill_params")

    objective_text = payload.get("objective")
    if objective_text:
        consumed.append("objective")
    focus_hint = payload.get("focus_hint")
    if focus_hint:
        consumed.append("focus_hint")

    return LegacyRunInputs(
        source_schema=str(schema_version),
        skill_id=skill_id,
        subject_id=subject_id,
        variant=variant,
        parameters=parameters,
        budget=budget,
        legacy_objective_text=str(objective_text) if objective_text else None,
        focus_hint=str(focus_hint) if focus_hint else None,
        preserved_fields=consumed,
        absent_rejected_fields=absent_rejected,
    )


def read_legacy_start_request(payload: Mapping[str, Any]) -> LegacyRunInputs:
    """Migrate a legacy start-request shape into contract inputs.

    Same preservation and rejection rules as the session-manifest reader;
    ``timeout_minutes`` converts to seconds and omitted budget fields fall
    back to the conservative system defaults (those request fields were
    optional).
    """
    absent_rejected = _check_rejected_fields(payload)
    skill_id, subject_id, variant, consumed = _require_identity(payload)

    timeout_minutes = payload.get("timeout_minutes")
    budget = BudgetDimensions(
        max_iterations=int(payload.get("max_iterations") or SYSTEM_DEFAULTS["max_iterations"]),
        max_budget_usd=float(payload.get("max_budget_usd") or SYSTEM_DEFAULTS["max_budget_usd"]),
        timeout_s=int(
            timeout_minutes * 60 if timeout_minutes else SYSTEM_DEFAULTS["timeout_s"]
        ),
    )
    for field in ("max_iterations", "max_budget_usd", "timeout_minutes"):
        if payload.get(field) is not None:
            consumed.append(field)

    parameters = dict(payload.get("skill_params") or {})
    reject_raw_secret_parameters(parameters, "legacy skill_params")
    if parameters:
        consumed.append("skill_params")

    objective_text = payload.get("objective")
    if objective_text:
        consumed.append("objective")
    focus_hint = payload.get("focus_hint")
    if focus_hint:
        consumed.append("focus_hint")

    return LegacyRunInputs(
        source_schema="start_request.v1",
        skill_id=skill_id,
        subject_id=subject_id,
        variant=variant,
        parameters=parameters,
        budget=budget,
        legacy_objective_text=str(objective_text) if objective_text else None,
        focus_hint=str(focus_hint) if focus_hint else None,
        preserved_fields=consumed,
        absent_rejected_fields=absent_rejected,
    )


__all__ = [
    # Versions
    "CONTRACT_VERSIONS",
    "VersionedContract",
    "RUN_SPEC_SCHEMA_VERSION",
    "EXECUTION_REQUEST_SCHEMA_VERSION",
    "CANDIDATE_IDENTITY_SCHEMA_VERSION",
    "OBSERVATION_IDENTITY_SCHEMA_VERSION",
    "VERIFIED_RESULT_SCHEMA_VERSION",
    "OBJECTIVE_POLICY_SCHEMA_VERSION",
    "CAPABILITY_DESCRIPTOR_SCHEMA_VERSION",
    "LEGACY_RUN_INPUTS_SCHEMA_VERSION",
    # Errors
    "ContractError",
    "UnsupportedCapabilityError",
    "ContractMigrationError",
    # Secrets
    "SecretReference",
    "is_secret_reference",
    "reject_raw_secret_parameters",
    "validate_secret_list",
    # Identity
    "ArtifactRef",
    "CandidateIdentity",
    "CandidateData",
    "ScorerRef",
    "ObservationIdentity",
    "canonical_digest",
    # Objective
    "MetricConstraint",
    "ObjectivePolicy",
    "objective_policy_from_skill_metric",
    # Capabilities / isolation
    "CapabilityDescriptor",
    "IsolationBoundary",
    "LINUX_ISOLATION_BOUNDARY",
    "MINIMUM_SUPPORTED_CAPABILITIES",
    "KNOWN_CAPABILITIES",
    "ensure_minimum_capabilities",
    "ensure_capabilities_allowed",
    "ensure_isolation_boundary",
    # Results
    "FailureRecord",
    "ResultReceipt",
    "VerifiedResult",
    # Execution / run
    "WorkspaceBounds",
    "NetworkPolicy",
    "ResourceLimits",
    "ExecutionRequest",
    "SkillPackageRef",
    "HarnessConfig",
    "EnvironmentIdentity",
    "BudgetDimensions",
    "RunInputs",
    "RunLineage",
    "RunSpec",
    "ensure_request_matches_run_spec",
    # Input layers
    "SYSTEM_DEFAULTS",
    "OperatorConstraints",
    "SkillDefaults",
    "HarnessPreferences",
    "ResolutionRecord",
    "ResolvedRunInputs",
    "resolve_run_inputs",
    # Legacy
    "LegacyFieldCompat",
    "LEGACY_COMPATIBILITY",
    "LegacyRunInputs",
    "read_legacy_session_manifest",
    "read_legacy_start_request",
]

