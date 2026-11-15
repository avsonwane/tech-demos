import json
import os

from fastapi.testclient import TestClient

os.environ["VIBE_DESK_AUTOSTART"] = "0"

from app import app  # noqa: E402


def test_health_lists_providers_and_the_nse_preset():
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["advice"] == "Research/simulation only, not financial advice."
    assert body["nse"]["accepted"] is True
    assert body["nse"]["market"] == "india_equity"
    ids = [provider["id"] for provider in body["providers"]]
    assert ids == ["xai", "openai", "anthropic"]
    assert all(isinstance(provider["key_set"], bool) for provider in body["providers"])
    assert "sk-" not in response.text
    prompts = [preset["prompt"] for preset in body["presets"]]
    assert any("RELIANCE.NS" in prompt for prompt in prompts)
    assert body["sample"]["source"] == "illustrative-sample"
    assert "Not produced by a live Vibe-Trading session" in body["sample"]["label"]


def test_replay_stream_includes_phases_and_the_sample_result(monkeypatch):
    monkeypatch.setenv("VIBE_DESK_REPLAY_DELAY", "0")
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    client = TestClient(app)
    response = client.post(
        "/api/run",
        json={
            "prompt": "Backtest a 20/50 SMA crossover on AAPL for 2024 vs buy-and-hold, report max drawdown",
            "provider": "xai",
            "mode": "replay",
        },
    )
    assert response.status_code == 200
    text = response.text
    assert "event: meta" in text
    assert "Not produced by a live Vibe-Trading session" in text
    assert "event: result" in text
    assert "event: done" in text
    phases = []
    result = None
    for block in text.split("\n\n"):
        event = "message"
        data_line = ""
        for line in block.splitlines():
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data_line = line[5:].strip()
        if not data_line:
            continue
        payload = json.loads(data_line)
        if event == "phase":
            phases.append(payload["id"])
        if event == "result":
            result = payload
    assert phases == ["plan", "ground", "code", "execution"]
    assert result is not None
    assert result["illustrative"] is True
    assert result["strategy_label"] == "20/50 SMA"
    assert result["benchmark_label"] == "Buy and hold"
    assert result["codes"] == ["RELIANCE.NS"]
    assert result["sources"] == ["yfinance"]
    assert result["metrics"]["total_return"] == 0.116
    assert result["metrics"]["sharpe"] == 0.8
    assert result["metrics"]["max_drawdown"] == -0.0959
    assert result["metrics"]["fees"] == 7355
    assert result["metrics"]["benchmark_return"] == -0.0604
    assert result["equity"][0]["benchmark"] == 100
    assert result["equity"][-1]["equity"] == 111.6
    assert result["equity"][-1]["benchmark"] == 93.96
    assert len(result["trades"]) == 3
    assert "rolling(20)" in result["code"]
    assert "Buy and hold" not in result["code"]


def test_auto_without_a_key_replays(monkeypatch):
    monkeypatch.setenv("VIBE_DESK_REPLAY_DELAY", "0")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = TestClient(app)
    response = client.post(
        "/api/run",
        json={"prompt": "AAPL crossover", "provider": "openai", "mode": "auto"},
    )
    assert response.status_code == 200
    assert "OPENAI_API_KEY is not set" in response.text
    assert '"mode": "replay"' in response.text


def test_live_without_a_key_is_rejected(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    client = TestClient(app)
    response = client.post(
        "/api/run",
        json={"prompt": "AAPL crossover", "provider": "anthropic", "mode": "live"},
    )
    assert response.status_code == 400
    assert "ANTHROPIC_API_KEY" in response.json()["detail"]


def test_serve_readiness_checks_health_not_the_spa_root(monkeypatch):
    seen: list[str] = []

    class _Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def opener(url, timeout=0):
        seen.append(url)
        return _Response()

    monkeypatch.setattr("app.urllib.request.urlopen", opener)
    from app import serve_http_ready

    assert serve_http_ready("http://127.0.0.1:8899") is True
    assert seen == ["http://127.0.0.1:8899/health"]
