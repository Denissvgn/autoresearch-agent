"""Track D2: digest bash tool output before it enters the agent's context.

The bash tool previously returned the FULL combined stdout+stderr of every
command into the conversation (read_file caps at 100k, grep at 60k — bash had
no cap at all). A full-mode training run streams 50–200KB of per-fold logs,
progress ticks and library INFO spam, which then gets re-read as input tokens
on EVERY subsequent turn of the session.

The digest keeps everything the agent acts on — the ``---`` metrics block,
``ITERATION_RESULT`` markers, errors/tracebacks/warnings, per-fold gate lines,
head and tail context — collapses recognizable noise into counted one-liners,
and points at the on-disk full log (readable via the read_file/grep tools)
for anything else.

The SERVER always parses markers from the RAW output — digesting only changes
what the LLM sees, never what the orchestrator records.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

#: Lines dropped entirely (pure noise, zero decision value).
_DROP_PATTERNS = [
    re.compile(r"matplotlib\.font_manager"),
    re.compile(r"alembic\.runtime\.migration"),
    re.compile(r"mlflow\.store\.db\.utils"),
    re.compile(r"Downloading artifacts:\s*\d+%"),
    re.compile(r"NumExpr defaulting to"),
    re.compile(r"^\s*$"),
]

#: Lines collapsed into a single "label ×N" counter per contiguous-ish group.
_COLLAPSE_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"Training in progress\.\.\."), "training-progress tick"),
    (re.compile(r"urllib3\.connectionpool.*Retrying"), "http retry"),
    (re.compile(r"Using feature library version"), "feature-library banner"),
    (re.compile(r"Computing features via shared library"), "feature-library banner"),
    (re.compile(r"Calculating technical indicators"), "indicator banner"),
    (re.compile(r"Generated \d+ technical indicators"), "indicator banner"),
    (re.compile(r"\[prepare(/gpu)?\] Progress:"), "gpu-progress tick"),
]

#: Lines ALWAYS kept (the agent's decision inputs), wherever they appear.
_KEEP_PATTERNS = [
    re.compile(r"ITERATION_RESULT"),
    re.compile(r"\b(error|traceback|exception|failed|fatal|assert)\b", re.IGNORECASE),
    re.compile(r"^fold_\d+:"),
    re.compile(r"[⚠❌✅⏹🔴]"),
    re.compile(r"\b(WARNING|CRITICAL)\b"),
    re.compile(r"\ball_gates_passed\b"),
    re.compile(r"\bprimary_metric\b"),
]

_HEAD_LINES = 25
_TAIL_LINES = 40
_MAX_KEPT_MIDDLE = 80
_METRICS_BLOCK_CAP = 8_000

DEFAULT_MAX_CHARS = 12_000


def _last_metrics_block(text: str) -> Optional[str]:
    """The last ``---`` … ``---`` delimited block (prepare.py metrics)."""
    matches = list(re.finditer(r"^---\s*$", text, flags=re.MULTILINE))
    if len(matches) < 2:
        return None
    start, end = matches[-2].start(), matches[-1].end()
    block = text[start:end]
    if len(block) > _METRICS_BLOCK_CAP:
        block = block[:_METRICS_BLOCK_CAP] + "\n...(metrics block truncated)..."
    return block


def digest_command_output(
    output: str,
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
    full_log_path: Optional[str] = None,
) -> str:
    """Return a context-friendly digest of a command's combined output.

    Small outputs pass through untouched; large ones are reduced to
    head + always-keep lines + collapsed-noise counters + the final metrics
    block + tail, with a footer naming the on-disk full log.
    """
    if max_chars <= 0 or len(output) <= max_chars:
        return output

    lines = output.splitlines()
    collapsed: dict[str, int] = {}
    dropped = 0

    def _denoise(chunk: List[str]) -> List[str]:
        """Strip drop/collapse noise from head/tail while keeping the rest."""
        nonlocal dropped
        out: List[str] = []
        for line in chunk:
            if any(p.search(line) for p in _DROP_PATTERNS):
                dropped += 1
                continue
            label = next(
                (lab for pat, lab in _COLLAPSE_PATTERNS if pat.search(line)), None
            )
            if label is not None:
                collapsed[label] = collapsed.get(label, 0) + 1
                continue
            out.append(line)
        return out

    head = _denoise(lines[:_HEAD_LINES])
    tail = (
        _denoise(lines[-_TAIL_LINES:])
        if len(lines) > _HEAD_LINES + _TAIL_LINES else []
    )
    middle = lines[_HEAD_LINES:-_TAIL_LINES] if tail else []

    kept: List[str] = []
    for line in middle:
        if any(p.search(line) for p in _DROP_PATTERNS):
            dropped += 1
            continue
        label = next(
            (lab for pat, lab in _COLLAPSE_PATTERNS if pat.search(line)), None
        )
        if label is not None:
            collapsed[label] = collapsed.get(label, 0) + 1
            continue
        if any(p.search(line) for p in _KEEP_PATTERNS):
            if len(kept) < _MAX_KEPT_MIDDLE:
                kept.append(line)
            else:
                dropped += 1
        else:
            dropped += 1

    summary_bits = [f"{label} ×{count}" for label, count in sorted(collapsed.items())]
    if dropped:
        summary_bits.append(f"other lines omitted ×{dropped}")
    omission_note = (
        "... [digested: " + ", ".join(summary_bits) + "] ..." if summary_bits else ""
    )

    metrics_block = _last_metrics_block(output)

    parts: List[str] = ["\n".join(head)]
    if omission_note:
        parts.append(omission_note)
    if kept:
        parts.append("\n".join(kept))
    if metrics_block and metrics_block not in ("\n".join(tail)):
        parts.append(metrics_block)
    if tail:
        parts.append("\n".join(tail))
    footer = f"[output digest: {len(output):,} → "
    digest = "\n".join(p for p in parts if p)

    # Hard safety cap: even the digest must respect max_chars.
    if len(digest) > max_chars:
        half = max_chars // 2
        digest = digest[:half] + "\n...(digest truncated)...\n" + digest[-half:]

    footer += f"{len(digest):,} chars"
    if full_log_path:
        footer += f" | full log: {full_log_path} (read_file/grep_files)"
    footer += "]"
    return digest + "\n" + footer
