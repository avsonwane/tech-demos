"""Turn Vibe-Trading session SSE frames into the four desk phases.

The frames match vibe-trading-ai 0.1.19: ``tool_call``, ``tool_progress``,
``tool_result``, ``text_delta``, ``grounding_status``, and the attempt
terminal events. Heartbeats are ignored. This module does not import the
library, so the parser tests stay offline.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterator

PHASES: tuple[tuple[str, str], ...] = (
    ("plan", "Plan"),
    ("ground", "Ground"),
    ("code", "Code"),
    ("execution", "Execution"),
)

TERMINAL_EVENTS = {"attempt.completed", "attempt.failed", "attempt.cancelled"}
_RUN_ID_RE = re.compile(r'"run_id"\s*:\s*"([^"]+)"')
_BODY_LIMIT = 2000

_SKIP_NOTES = {
    "plan": "No plan text in this session.",
    "ground": "No separate data-fetch step in this session.",
    "code": "No strategy file event in this session.",
    "execution": "No backtest event in this session.",
}
_SOURCE_RE = re.compile(r"source=([A-Za-z0-9_.-]+)")

_TOOL_PHASE = {
    "get_market_data": "ground",
    "write_file": "code",
    "edit_file": "code",
    "backtest": "execution",
}


def phase_for_tool(name: str) -> str:
    if name in _TOOL_PHASE:
        return _TOOL_PHASE[name]
    lowered = name.lower()
    if "backtest" in lowered:
        return "execution"
    if "market" in lowered or any(
        token in lowered for token in ("ohlcv", "yfinance", "fetch_data", "load_bars", "get_bars", "download")
    ):
        return "ground"
    return "plan"


def parse_sse(lines: Iterator[str | bytes]) -> Iterator[tuple[str, dict[str, Any]]]:
    """Parse an SSE byte or text stream into ``(event_type, data)`` pairs."""
    event = "message"
    data_lines: list[str] = []

    def finish() -> tuple[str, dict[str, Any]] | None:
        if not data_lines:
            return None
        raw = "\n".join(data_lines)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"raw": raw}
        if not isinstance(payload, dict):
            payload = {"value": payload}
        return event, payload

    for raw_line in lines:
        line = raw_line.decode("utf-8", errors="replace") if isinstance(raw_line, bytes) else raw_line
        if line.endswith("\r"):
            line = line[:-1]
        if line == "":
            finished = finish()
            event = "message"
            data_lines = []
            if finished is not None:
                yield finished
            continue
        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            event = line[6:].strip() or "message"
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    finished = finish()
    if finished is not None:
        yield finished


def empty_state() -> dict[str, Any]:
    return {
        "phases": {
            phase_id: {"id": phase_id, "title": title, "status": "waiting", "body": ""}
            for phase_id, title in PHASES
        },
        "current": "plan",
        "saw_tool": False,
        "run_id": None,
        "error": None,
        "terminal": None,
    }


def _append(state: dict[str, Any], phase_id: str, line: str, status: str | None = None) -> dict[str, Any]:
    phase = state["phases"][phase_id]
    if phase["status"] == "waiting":
        phase["status"] = "working"
    text = line.strip()
    if text:
        joined = f"{phase['body']}\n{text}".strip() if phase["body"] else text
        if len(joined) > _BODY_LIMIT:
            joined = joined[-_BODY_LIMIT:]
        phase["body"] = joined
    if status:
        phase["status"] = status
    return dict(phase)


def _run_id_from(data: dict[str, Any]) -> str | None:
    run_id = data.get("run_id")
    if isinstance(run_id, str) and run_id.strip():
        return run_id.strip()
    run_dir = data.get("run_dir")
    if isinstance(run_dir, str) and run_dir.strip():
        name = Path(run_dir).name
        if name and name not in {".", "/"}:
            return name
    preview = data.get("preview")
    if isinstance(preview, str):
        match = _RUN_ID_RE.search(preview)
        if match:
            return match.group(1)
    return None


def _arg_summary(arguments: Any) -> str:
    if not isinstance(arguments, dict):
        return ""
    parts: list[str] = []
    for key in ("codes", "code", "symbol", "symbols", "start_date", "end_date", "path", "filename"):
        value = arguments.get(key)
        if value:
            parts.append(f"{key}={value}")
    return ", ".join(parts)


def _execution_source(state: dict[str, Any]) -> str | None:
    match = _SOURCE_RE.search(state["phases"]["execution"]["body"])
    return match.group(1) if match else None


def _finish_phases(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Resolve every step once the session ends.

    A step that received events is done. A step that never started is skipped,
    except Ground when the backtest itself recorded a data source.
    """
    updates: list[dict[str, Any]] = []
    source = _execution_source(state)
    for phase_id, _title in PHASES:
        phase = state["phases"][phase_id]
        if phase["status"] == "working":
            updates.append(_append(state, phase_id, "", "done"))
        elif phase["status"] == "waiting":
            if phase_id == "ground" and source:
                updates.append(
                    _append(
                        state,
                        phase_id,
                        f"Bars loaded by the backtest engine (source={source}).",
                        "done",
                    )
                )
            else:
                updates.append(_append(state, phase_id, _SKIP_NOTES[phase_id], "skipped"))
    return updates


def apply_event(state: dict[str, Any], event_type: str, data: dict[str, Any]) -> list[dict[str, Any]]:
    """Fold one SSE event into ``state`` and return the phase snapshots that changed."""
    if not isinstance(data, dict):
        data = {}
    if event_type in {"heartbeat", "message", "tool_heartbeat"}:
        return []

    updates: list[dict[str, Any]] = []
    if event_type == "text_delta":
        delta = data.get("delta")
        if isinstance(delta, str) and delta.strip() and not state["saw_tool"]:
            updates.append(_append(state, "plan", delta.strip()))
        return updates

    if event_type == "tool_call":
        tool = str(data.get("tool") or "tool")
        phase_id = phase_for_tool(tool)
        state["saw_tool"] = True
        if state["phases"]["plan"]["status"] == "working" and phase_id != "plan":
            updates.append(_append(state, "plan", "", "done"))
        state["current"] = phase_id
        summary = _arg_summary(data.get("arguments"))
        line = f"{tool} ({summary})" if summary else tool
        updates.append(_append(state, phase_id, line, "working"))
        return updates

    if event_type == "tool_progress":
        tool = str(data.get("tool") or "")
        phase_id = phase_for_tool(tool) if tool else state["current"]
        message = data.get("message") or data.get("stage")
        if message:
            prefix = f"{tool}: " if tool else ""
            updates.append(_append(state, phase_id, f"{prefix}{message}"))
        return updates

    if event_type == "tool_result":
        tool = str(data.get("tool") or "tool")
        phase_id = phase_for_tool(tool)
        status = str(data.get("status") or "ok")
        updates.append(_append(state, phase_id, f"{tool} {status}", "done" if status == "ok" else "working"))
        found = _run_id_from(data)
        if found:
            state["run_id"] = found
        return updates

    if event_type == "grounding_status":
        stage = str(data.get("stage") or "check")
        updates.append(_append(state, state["current"], f"Figure check: {stage}"))
        return updates

    if event_type in TERMINAL_EVENTS:
        state["terminal"] = event_type
        found = _run_id_from(data)
        if found:
            state["run_id"] = found
        if event_type == "attempt.cancelled":
            state["error"] = "The session was cancelled."
        elif event_type != "attempt.completed":
            error = data.get("error") or data.get("summary") or "The session failed."
            state["error"] = str(error)
        updates.extend(_finish_phases(state))
        return updates

    return updates
