"""Persistent agent log writer — captures the full Claude conversation to JSONL."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from server.ws.events import broadcaster

logger = logging.getLogger(__name__)

# Maximum chars kept for tool results in a single log entry
_MAX_RESULT_LEN = 5000

# Type labels for human-readable formatting
_TYPE_LABELS = {
    "text": "CLAUDE",
    "tool_call": "TOOL",
    "tool_result": "RESULT",
    "system": "SYSTEM",
    "error": "ERROR",
}


class AgentLogWriter:
    """Append-only JSONL log writer with WebSocket broadcasting.

    Each line is a JSON object:
        {"ts": str, "turn": int, "type": str, "content": str, "meta": dict}
    """

    def __init__(
        self,
        log_path: Path,
        research_id: str,
        *,
        pipeline_id: Optional[str] = None,
        phase: Optional[str] = None,
    ) -> None:
        self._path = log_path
        self._research_id = research_id
        self._pipeline_id = pipeline_id
        self._phase = phase
        self._line_count = 0
        os.makedirs(log_path.parent, exist_ok=True)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def append(
        self,
        entry_type: str,
        content: str,
        turn: int = -1,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Append one log entry to file and broadcast via WebSocket."""
        meta = dict(meta) if isinstance(meta, dict) else {}
        if self._phase:
            meta.setdefault("phase", self._phase)
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "turn": turn,
            "type": entry_type,
            "content": content,
            "meta": meta,
        }
        line = json.dumps(entry, default=str) + "\n"
        try:
            await asyncio.to_thread(self._write_line, line)
        except Exception:
            logger.warning("Failed to write agent log entry", exc_info=True)
        self._line_count += 1

        # Broadcast to connected WS clients
        try:
            event = {
                "event": "agent_log",
                "research_id": self._research_id,
                "entry": entry,
            }
            if self._pipeline_id:
                event["pipeline_id"] = self._pipeline_id
            await broadcaster.broadcast(event)
        except Exception:
            pass  # non-critical — don't break the agent loop

    def _write_line(self, line: str) -> None:
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(line)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    @staticmethod
    def read_all(log_path: Path) -> str:
        """Read the full log and return human-readable formatted text."""
        if not log_path.exists():
            return ""
        lines: list[str] = []
        with open(log_path, "r", encoding="utf-8") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    entry = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                lines.append(_format_entry(entry))
        return "\n".join(lines)

    @staticmethod
    def read_lines(log_path: Path, after_line: int = 0) -> List[Dict[str, Any]]:
        """Return parsed entries after the given line number (0-based)."""
        if not log_path.exists():
            return []
        entries: list[Dict[str, Any]] = []
        with open(log_path, "r", encoding="utf-8") as f:
            for idx, raw in enumerate(f):
                if idx < after_line:
                    continue
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    entries.append(json.loads(raw))
                except json.JSONDecodeError:
                    continue
        return entries


def _format_entry(entry: Dict[str, Any]) -> str:
    """Format a single log entry as a human-readable line."""
    ts = entry.get("ts", "")
    # Extract HH:MM:SS from ISO timestamp
    try:
        dt = datetime.fromisoformat(ts)
        time_str = dt.strftime("%H:%M:%S")
    except (ValueError, TypeError):
        time_str = "??:??:??"

    entry_type = entry.get("type", "system")
    label = _TYPE_LABELS.get(entry_type, entry_type.upper())
    content = entry.get("content", "")
    meta = entry.get("meta", {})

    if entry_type == "tool_call":
        tool_input = meta.get("input", {})
        if isinstance(tool_input, dict):
            # Show command for bash, or first 200 chars of input
            preview = tool_input.get("command", str(tool_input))[:200]
        else:
            preview = str(tool_input)[:200]
        return f"[{time_str}] [{label}] {content} → {preview}"

    if entry_type == "tool_result":
        tool_name = meta.get("tool_name", "")
        # Truncate result for display
        preview = content[:500]
        suffix = "..." if len(content) > 500 else ""
        prefix = f"{tool_name} → " if tool_name else ""
        return f"[{time_str}] [{label}] {prefix}{preview}{suffix}"

    return f"[{time_str}] [{label}] {content}"
