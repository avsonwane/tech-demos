"""Unscoped Anthropic keys need anthropic-workspace-id on the request."""


def test_workspace_header_is_forwarded(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_WORKSPACE_ID", "wrkspc_test")
    import runner
    from tradingagents.llm_clients import anthropic_client as ac

    runner._ANTHROPIC_WORKSPACE_PATCHED = False
    runner._install_anthropic_workspace_header()

    captured: dict = {}

    class Capture:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(ac, "NormalizedChatAnthropic", Capture)
    ac.AnthropicClient("claude-haiku-4-5", api_key="sk-test").get_llm()

    assert captured["default_headers"]["anthropic-workspace-id"] == "wrkspc_test"
    assert "default_headers" in ac._PASSTHROUGH_KWARGS
