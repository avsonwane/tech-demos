import json

import httpx

from proxy import VibeClient, drive_live


def _sse(*frames: tuple[str, dict]) -> str:
    chunks = []
    for event_type, data in frames:
        chunks.append(f"event: {event_type}\ndata: {json.dumps(data)}\n\n")
    return "".join(chunks)


def test_drive_live_posts_the_session_and_parses_the_run():
    seen: list[tuple[str, str]] = []
    prompt = "Backtest a 20/50 SMA crossover on AAPL for 2024 vs buy-and-hold, report max drawdown"

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        if request.method == "POST" and request.url.path == "/sessions":
            body = json.loads(request.content)
            assert body["title"]
            return httpx.Response(
                200,
                json={
                    "session_id": "sess-1",
                    "title": body["title"],
                    "status": "idle",
                    "created_at": "t",
                    "updated_at": "t",
                },
            )
        if request.method == "POST" and request.url.path == "/sessions/sess-1/messages":
            body = json.loads(request.content)
            assert body["content"] == prompt
            return httpx.Response(200, json={"message_id": "m1"})
        if request.method == "GET" and request.url.path == "/sessions/sess-1/events":
            assert request.url.params["replay"] == "active"
            stream = _sse(
                ("tool_call", {"tool": "get_market_data", "arguments": {"codes": "AAPL"}}),
                ("tool_result", {"tool": "get_market_data", "status": "ok", "preview": "bars"}),
                ("tool_call", {"tool": "write_file", "arguments": {"path": "code/signal_engine.py"}}),
                ("tool_result", {"tool": "write_file", "status": "ok", "preview": "wrote"}),
                ("tool_call", {"tool": "backtest", "arguments": {}}),
                ("tool_result", {"tool": "backtest", "status": "ok", "preview": '{"run_id": "run-1"}'}),
                ("attempt.completed", {"run_dir": "/home/runs/run-1", "status": "completed"}),
            )
            return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=stream)
        if request.method == "GET" and request.url.path == "/runs/run-1":
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "run_id": "run-1",
                    "metrics": {
                        "total_return": 0.1,
                        "annual_return": 0.1,
                        "sharpe": 1.1,
                        "max_drawdown": -0.05,
                        "win_rate": 0.4,
                    },
                    "run_card": {
                        "data_sources": ["yahoo"],
                        "backtest": {"codes": ["AAPL"], "start_date": "2024-01-02", "end_date": "2024-12-31"},
                    },
                    "artifacts_equity_csv": [
                        {"timestamp": "2024-01-02", "equity": "100", "drawdown": "0", "benchmark_equity": "100"}
                    ],
                    "artifacts_trades_csv": [],
                },
            )
        if request.method == "GET" and request.url.path == "/runs/run-1/code":
            return httpx.Response(200, json={"signal_engine.py": "class SignalEngine:\n    pass\n"})
        return httpx.Response(404, json={"detail": request.url.path})

    transport = httpx.MockTransport(handler)
    client = VibeClient(
        "http://vibe.test",
        httpx.Client(transport=transport, base_url="http://vibe.test"),
    )
    events = list(drive_live(client, prompt))
    paths = [path for _method, path in seen]
    assert "/sessions" in paths
    assert "/sessions/sess-1/messages" in paths
    assert "/sessions/sess-1/events" in paths
    assert "/runs/run-1" in paths
    assert "/runs/run-1/code" in paths
    phases = [payload["id"] for name, payload in events if name == "phase"]
    assert phases[0] == "ground"
    assert "code" in phases
    assert "execution" in phases
    result = events[-1]
    assert result[0] == "result"
    assert result[1]["codes"] == ["AAPL"]
    assert result[1]["sources"] == ["yahoo"]
    assert result[1]["metrics"]["sharpe"] == 1.1
    assert result[1]["equity"][0]["benchmark"] == 100
    assert "SignalEngine" in result[1]["code"]
    assert result[1]["illustrative"] is False


def test_missing_code_endpoint_does_not_fail_the_run():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path == "/sessions":
            return httpx.Response(
                200,
                json={"session_id": "sess-2", "title": "t", "status": "idle", "created_at": "t", "updated_at": "t"},
            )
        if request.url.path == "/sessions/sess-2/messages":
            return httpx.Response(200, json={"message_id": "m"})
        if request.url.path == "/sessions/sess-2/events":
            stream = _sse(("attempt.completed", {"run_dir": "/runs/run-2", "status": "completed"}))
            return httpx.Response(200, content=stream)
        if request.url.path == "/runs/run-2":
            return httpx.Response(
                200,
                json={
                    "run_id": "run-2",
                    "status": "success",
                    "metrics": {"total_return": 0, "annual_return": 0, "sharpe": 0, "max_drawdown": 0, "win_rate": 0},
                    "run_card": {"data_sources": [], "backtest": {"codes": ["BTC-USDT"], "source": "okx"}},
                    "artifacts_equity_csv": [],
                    "artifacts_trades_csv": [],
                },
            )
        if request.url.path == "/runs/run-2/code":
            return httpx.Response(404, json={"detail": "missing"})
        return httpx.Response(404)

    client = VibeClient(
        "http://vibe.test",
        httpx.Client(transport=httpx.MockTransport(handler), base_url="http://vibe.test"),
    )
    events = list(drive_live(client, "BTC-USDT crossover"))
    assert events[-1][1]["code"] == ""
    assert events[-1][1]["sources"] == ["okx"]
    assert events[-1][1]["codes"] == ["BTC-USDT"]
