import json

from fastapi.testclient import TestClient

from app import app


def test_health_lists_providers_without_secrets():
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["advice"] == "Research/simulation only, not financial advice."
    ids = [provider["id"] for provider in body["providers"]]
    assert ids[:2] == ["xai", "openai"]
    assert all(isinstance(provider["key_set"], bool) for provider in body["providers"])
    anthropic = next(provider for provider in body["providers"] if provider["id"] == "anthropic")
    assert [model["id"] for model in anthropic["quick"]] == [
        "claude-haiku-5-5",
        "claude-sonnet-5-5",
        "claude-sonnet-5",
        "claude-haiku-4-5",
    ]
    assert [model["id"] for model in anthropic["deep"]] == [
        "claude-fable-5-2",
        "claude-opus-5-5",
        "claude-fable-5-1",
        "claude-sonnet-5-5",
    ]
    assert anthropic["quick_default"] == "claude-sonnet-5-5"
    assert anthropic["deep_default"] == "claude-opus-5-5"
    assert body["sample"]["source"] == "illustrative-sample"


def test_replay_stream_includes_the_debate_and_the_decision(monkeypatch):
    monkeypatch.setenv("TRADING_AGENTS_REPLAY_DELAY", "0")
    client = TestClient(app)
    response = client.post(
        "/api/run",
        json={
            "ticker": "NVDA",
            "as_of": "2026-11-13",
            "provider": "xai",
            "quick_model": "grok-4.6",
            "deep_model": "grok-4.6",
            "debate_rounds": 1,
            "mode": "replay",
        },
    )
    assert response.status_code == 200
    text = response.text
    assert "event: meta" in text
    assert "Illustrative sample transcript" in text
    assert '"role": "bull"' in text
    assert '"role": "bear"' in text
    assert '"action": "HOLD"' in text
    assert "event: done" in text
    stages = []
    for block in text.split("\n\n"):
        for line in block.splitlines():
            if line.startswith("data:"):
                stages.append(json.loads(line[5:]))
    actions = [item.get("action") for item in stages if isinstance(item, dict)]
    assert "HOLD" in actions


def test_live_without_a_key_is_rejected():
    client = TestClient(app)
    response = client.post(
        "/api/run",
        json={
            "ticker": "NVDA",
            "as_of": "2026-11-13",
            "provider": "xai",
            "quick_model": "grok-4.6",
            "deep_model": "grok-4.6",
            "debate_rounds": 1,
            "mode": "live",
        },
    )
    assert response.status_code == 400
    assert "XAI_API_KEY" in response.json()["detail"]
