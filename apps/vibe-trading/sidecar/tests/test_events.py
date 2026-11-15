import json

from events import apply_event, empty_state, parse_sse


def test_parse_sse_skips_comments_and_heartbeats():
    raw = "\n".join(
        [
            ": stream-open",
            "id: abc",
            "event: heartbeat",
            'data: {"ts": 1}',
            "",
            "event: text_delta",
            'data: {"delta": "Plan the crossover."}',
            "",
        ]
    )
    frames = list(parse_sse(raw.splitlines()))
    assert frames[0][0] == "heartbeat"
    assert frames[1] == ("text_delta", {"delta": "Plan the crossover."})
    state = empty_state()
    assert apply_event(state, *frames[0]) == []
    phases = apply_event(state, *frames[1])
    assert phases[0]["id"] == "plan"
    assert "crossover" in phases[0]["body"]


def test_tool_calls_fill_ground_code_and_execution():
    state = empty_state()
    events = [
        ("text_delta", {"delta": "A 20/50 crossover on AAPL."}),
        ("tool_call", {"tool": "get_market_data", "arguments": {"codes": "AAPL", "start_date": "2024-01-01"}}),
        ("tool_progress", {"tool": "get_market_data", "stage": "fetch", "message": "yahoo"}),
        ("tool_result", {"tool": "get_market_data", "status": "ok", "preview": "252 bars"}),
        ("tool_call", {"tool": "write_file", "arguments": {"path": "code/signal_engine.py"}}),
        ("tool_result", {"tool": "write_file", "status": "ok", "preview": "wrote"}),
        ("tool_call", {"tool": "backtest", "arguments": {"codes": "AAPL"}}),
        (
            "tool_result",
            {
                "tool": "backtest",
                "status": "ok",
                "preview": json.dumps({"run_id": "run-from-preview", "metrics": {}})[:200],
            },
        ),
        (
            "attempt.completed",
            {"attempt_id": "a1", "status": "completed", "run_dir": "/tmp/runs/run-final"},
        ),
    ]
    seen: list[str] = []
    for event_type, data in events:
        for phase in apply_event(state, event_type, data):
            seen.append(phase["id"])
    assert seen[0] == "plan"
    assert "ground" in seen
    assert "code" in seen
    assert "execution" in seen
    assert state["phases"]["plan"]["status"] == "done"
    assert state["phases"]["ground"]["status"] == "done"
    assert "AAPL" in state["phases"]["ground"]["body"]
    assert "yahoo" in state["phases"]["ground"]["body"]
    assert state["phases"]["code"]["body"].startswith("write_file")
    assert state["run_id"] == "run-final"
    assert state["terminal"] == "attempt.completed"
    assert state["error"] is None


def test_failed_attempt_keeps_the_error_and_preview_run_id():
    state = empty_state()
    apply_event(
        state,
        "tool_result",
        {"tool": "backtest", "status": "error", "preview": '{"run_id": "run-partial"}'},
    )
    apply_event(state, "attempt.failed", {"error": "model timeout"})
    assert state["run_id"] == "run-partial"
    assert state["error"] == "model timeout"
    assert state["terminal"] == "attempt.failed"
