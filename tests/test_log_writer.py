from __future__ import annotations

from pathlib import Path

import pytest

from src.core.log_writer import AgentLogWriter


@pytest.mark.asyncio
async def test_agent_log_writer_persists_stable_line_numbers(tmp_path: Path):
    log_path = tmp_path / "agent_log.jsonl"
    writer = AgentLogWriter(log_path, "res_log")

    await writer.append("system", "started", turn=0)
    await writer.append("command_output", "progress", turn=0, meta={"stream": "stdout"})

    entries = AgentLogWriter.read_lines(log_path)
    assert [entry["line_number"] for entry in entries] == [0, 1]

    resumed = AgentLogWriter(log_path, "res_log")
    await resumed.append("system", "resumed", turn=1)

    entries = AgentLogWriter.read_lines(log_path)
    assert [entry["line_number"] for entry in entries] == [0, 1, 2]
    assert entries[1]["type"] == "command_output"
    assert entries[1]["meta"]["stream"] == "stdout"
