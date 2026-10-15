"""Per-workdir trial state (P2 — the ``execution.concurrency`` prerequisite).

Every per-command piece of orchestrator state that today derives from the
*session* workspace — the pre-run config snapshot, the governed subprocess
cwd, the marker/results fallback files, and the runtime-command provenance —
is derived from a :class:`TrialContext` instead. With
``execution.concurrency == 1`` (the default) the context's ``trial_dir`` is
``None`` and every call site resolves against the session workspace exactly
as before (byte-identical behavior). A skill that opts into
``execution.concurrency > 1`` gets each sanctioned experiment command
executed inside its own isolated trial directory: a staged copy of the
session workspace at dispatch time, so concurrent trials can never clobber
each other's candidate configs, marker files, or result artifacts.

Trial eligibility reuses the sanctioned-scripts rule already governing the
W11 nonce delivery (``_nonce_env_for_command``) and the
``turn_ran_training_command`` flag: a bash command is trial-eligible iff it
invokes one of the skill manifest's declared ``allowed_scripts``. Bookkeeping
commands (``cp``/``cat``) and non-bash tools keep running against the session
workspace.

Trial directories live under ``<session_workspace>/.trials/`` — inside the
session workspace, so every existing path-safety and command-policy check
applies unchanged — and are retained as operator-inspectable provenance.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Optional

from src.core import fs_safety

logger = logging.getLogger(__name__)

#: Trial directories root, relative to the session workspace.
TRIALS_DIRNAME = ".trials"

#: Session-workspace entries never staged into a trial copy: the trials tree
#: itself (recursion guard), server-owned logs/snapshots, and Python caches.
_STAGE_IGNORE = frozenset({
    TRIALS_DIRNAME,
    "command_logs",
    "server_snapshots",
    "__pycache__",
})


@dataclass(frozen=True)
class TrialContext:
    """Per-command execution context (P2 per-workdir state).

    ``trial_dir`` is ``None`` for the default sequential path — ``workdir``
    then resolves to the session workspace and every consumer behaves
    exactly as before the refactor.
    """

    research_id: str
    turn: int
    #: 1-based index of this bash command within the turn (all bash blocks
    #: counted, eligible or not — deterministic, collision-free naming).
    seq: int
    session_workspace: str
    trial_dir: Optional[str] = None

    @property
    def workdir(self) -> str:
        """The directory the governed subprocess runs in."""
        return (
            self.trial_dir if self.trial_dir is not None else self.session_workspace
        )

    @property
    def is_trial(self) -> bool:
        return self.trial_dir is not None


def is_trial_eligible_command(
    command: object,
    allowed_scripts: Optional[Iterable[str] | Mapping[str, str]],
) -> bool:
    """True when a bash command invokes one of the skill's sanctioned scripts.

    Same predicate the orchestrator uses for nonce-env narrowing and the
    ``turn_ran_training_command`` flag — the sanctioned experiment commands
    are exactly the ones that get trial directories.
    """
    cmd = str(command or "")
    if not cmd:
        return False
    scripts = allowed_scripts or ()
    try:
        return any(str(script) in cmd for script in scripts)
    except TypeError:
        return False


def allocate_trial_dir(session_workspace: str, *, turn: int, seq: int) -> str:
    """Create (idempotently) and return this command's trial directory."""
    trial_root = Path(session_workspace) / TRIALS_DIRNAME
    trial_dir = trial_root / f"turn-{turn:03d}-seq-{seq:02d}"
    trial_dir.mkdir(parents=True, exist_ok=True)
    return str(trial_dir)


def stage_trial_workspace(session_workspace: str, trial_dir: str) -> int:
    """Copy the session-workspace state into the trial directory.

    Returns the number of staged top-level entries. Server-owned directories
    (logs, snapshots, the trials tree itself) and caches are excluded, and
    no link is ever followed: symlinked, hardlinked, and special entries are
    skipped with a warning instead of materializing content that could come
    from (or alias) a shared file. Per-entry copy errors are logged and
    skipped; a wholesale failure propagates so :func:`stage_trial_or_none`
    can fail open.
    """
    src = Path(session_workspace)
    dst = Path(trial_dir)
    dst.mkdir(parents=True, exist_ok=True)

    def _on_skip(name: str, reason: str) -> None:
        logger.warning(
            "Trial staging skipped %s (%s); the trial may miss this state",
            name, reason,
        )

    return fs_safety.copy_tree_regular_files(
        str(src), str(dst), ignore=_STAGE_IGNORE, on_skip=_on_skip
    )


def stage_trial_or_none(session_workspace: str, trial_dir: str) -> Optional[str]:
    """Stage a trial workspace, returning ``trial_dir`` or ``None`` on failure.

    ``None`` means "run in the session workspace instead" — the fail-open
    fallback that keeps a staging hiccup from failing the session.
    """
    try:
        stage_trial_workspace(session_workspace, trial_dir)
        return trial_dir
    except (OSError, fs_safety.FilesystemSafetyError) as exc:
        logger.warning(
            "Trial staging failed for %s (%s); falling back to the session "
            "workspace for this command",
            trial_dir, exc,
        )
        return None


def trial_marker_candidates(
    trial_dir: str, marker_paths: Iterable[Path]
) -> list[Path]:
    """Trial-dir-first candidates for the marker-file fallback.

    Given the skill-declared marker paths (session-workspace locations),
    return the same *basenames* resolved inside the trial directory first —
    a trial subprocess writes its marker/results files to its cwd, so the
    trial copy is the fresh one; the session paths stay as fallback.
    """
    trial = Path(trial_dir)
    return [trial / p.name for p in marker_paths] + list(marker_paths)


def build_trial_context(
    *,
    research_id: str,
    turn: int,
    seq: int,
    session_workspace: str,
    command: object,
    allowed_scripts: Optional[Iterable[str] | Mapping[str, str]],
    execution_concurrency: int,
) -> TrialContext:
    """Build the per-command context, allocating a trial dir when eligible.

    A trial directory is allocated only when the skill opted into
    ``execution.concurrency > 1`` AND the command invokes one of the
    skill's sanctioned scripts. Staging failure degrades to the session
    workspace (fail-open), never failing the session.
    """
    trial_dir: Optional[str] = None
    if execution_concurrency > 1 and is_trial_eligible_command(
        command, allowed_scripts
    ):
        candidate = allocate_trial_dir(session_workspace, turn=turn, seq=seq)
        staged = stage_trial_or_none(session_workspace, candidate)
        if staged is not None:
            trial_dir = candidate
            logger.info(
                "Research %s turn %d: staged trial workspace %s",
                research_id, turn, trial_dir,
            )
    return TrialContext(
        research_id=research_id,
        turn=turn,
        seq=seq,
        session_workspace=session_workspace,
        trial_dir=trial_dir,
    )


__all__ = [
    "TRIALS_DIRNAME",
    "TrialContext",
    "allocate_trial_dir",
    "build_trial_context",
    "is_trial_eligible_command",
    "stage_trial_or_none",
    "stage_trial_workspace",
    "trial_marker_candidates",
]

