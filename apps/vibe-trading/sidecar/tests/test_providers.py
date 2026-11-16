import logging

import pytest

from launch_serve import call_with_sampling_retry, patch_anthropic_builder, uses_model_defaults
from providers import provider_child_env, resolve_model


def test_xai_mapping_leaves_the_parent_openai_key_alone():
    parent = {
        "XAI_API_KEY": "test-xai-key",
        "OPENAI_API_KEY": "test-openai-key",
        "OPENAI_BASE_URL": "https://api.openai.com/v1",
        "ANTHROPIC_API_KEY": "test-anthropic-key",
        "ANTHROPIC_WORKSPACE_ID": "wrkspc_test",
    }
    child = provider_child_env("xai", parent)
    assert parent["OPENAI_API_KEY"] == "test-openai-key"
    assert child["OPENAI_API_KEY"] == "test-xai-key"
    assert child["OPENAI_BASE_URL"] == "https://api.x.ai/v1"
    assert child["LANGCHAIN_PROVIDER"] == "openai"
    assert child["LANGCHAIN_MODEL_NAME"] == "grok-4.6"
    assert child["ANTHROPIC_WORKSPACE_ID"] == "wrkspc_test"

    openai = provider_child_env("openai", parent)
    assert openai["OPENAI_API_KEY"] == "test-openai-key"
    assert openai["OPENAI_BASE_URL"] == "https://api.openai.com/v1"
    assert openai["LANGCHAIN_PROVIDER"] == "openai"
    assert openai["LANGCHAIN_MODEL_NAME"] == "gpt-5.5"

    anthropic = provider_child_env("anthropic", parent)
    assert anthropic["LANGCHAIN_PROVIDER"] == "anthropic"
    assert anthropic["LANGCHAIN_MODEL_NAME"] == "claude-sonnet-5-5"
    assert anthropic["ANTHROPIC_API_KEY"] == "test-anthropic-key"
    assert anthropic["ANTHROPIC_WORKSPACE_ID"] == "wrkspc_test"


def test_workspace_header_is_passed_into_chat_anthropic():
    captured: dict = {}

    class ChatAnthropic:
        def __init__(self, *args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs

    class LLM:
        def import_module(self, name, package=None):
            assert name == "langchain_anthropic"
            return self.modules[name]

        def _build_anthropic(self, **kwargs):
            module = self.import_module("langchain_anthropic")
            return module.ChatAnthropic(**kwargs)

    llm = LLM()
    llm.modules = {"langchain_anthropic": type("Mod", (), {"ChatAnthropic": ChatAnthropic})()}
    patch_anthropic_builder(llm, "wrkspc_test")
    llm._build_anthropic(model="claude-sonnet-4-6")
    headers = captured["kwargs"]["default_headers"]
    assert headers["anthropic-workspace-id"] == "wrkspc_test"
    assert llm.import_module.__func__ is LLM.import_module


def _fake_llm():
    captured: dict = {}

    class ChatAnthropic:
        def __init__(self, *args, **kwargs):
            captured["args"] = args
            captured["kwargs"] = kwargs

    class LLM:
        def import_module(self, name, package=None):
            return self.modules[name]

        def _build_anthropic(self, **kwargs):
            module = self.import_module("langchain_anthropic")
            return module.ChatAnthropic(**kwargs)

    llm = LLM()
    llm.modules = {"langchain_anthropic": type("Mod", (), {"ChatAnthropic": ChatAnthropic})()}
    return llm, captured


def test_claude_5_models_drop_sampling_and_claude_4_keeps_it():
    for model in ("claude-sonnet-5-5", "claude-opus-5-5", "claude-fable-5-2", "claude-haiku-5"):
        assert uses_model_defaults(model) is True
        llm, captured = _fake_llm()
        patch_anthropic_builder(llm, "")
        llm._build_anthropic(model=model, temperature=1, top_p=1, top_k=40)
        assert "temperature" not in captured["kwargs"]
        assert "top_p" not in captured["kwargs"]
        assert "top_k" not in captured["kwargs"]

    assert uses_model_defaults("claude-sonnet-4-6") is False
    llm, captured = _fake_llm()
    patch_anthropic_builder(llm, "wrkspc_keep")
    llm._build_anthropic(model="claude-sonnet-4-6", temperature=0, top_p=0.2, top_k=8)
    assert captured["kwargs"]["temperature"] == 0
    assert captured["kwargs"]["top_p"] == 0.2
    assert captured["kwargs"]["top_k"] == 8
    assert captured["kwargs"]["default_headers"]["anthropic-workspace-id"] == "wrkspc_keep"


class _SamplingError(Exception):
    status_code = 400

    def __str__(self) -> str:
        return "Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', 'message': 'temperature is not supported'}}"


def test_sampling_400_retries_once_without_those_fields(caplog):
    calls: list[dict] = []

    def call(params):
        calls.append(dict(params))
        if len(calls) == 1:
            raise _SamplingError()
        return "ok"

    with caplog.at_level(logging.WARNING):
        result = call_with_sampling_retry(
            "claude-sonnet-4-6",
            {"model": "claude-sonnet-4-6", "temperature": 0, "top_p": 0.2, "top_k": 8},
            call,
        )
    assert result == "ok"
    assert calls[0]["temperature"] == 0
    assert calls[0]["top_p"] == 0.2
    assert "temperature" not in calls[1]
    assert "top_p" not in calls[1]
    assert "top_k" not in calls[1]
    assert "retrying once" in caplog.text.lower()


def test_claude_5_strips_sampling_before_the_first_call():
    seen: list[dict] = []
    for model in ("claude-sonnet-5", "claude-opus-5-5", "claude-fable-5", "claude-haiku-5-0"):
        seen.clear()
        result = call_with_sampling_retry(
            model,
            {"model": model, "temperature": 1, "top_p": 1, "top_k": 5},
            lambda params: seen.append(dict(params)) or "ok",
        )
        assert result == "ok"
        assert list(seen[0]) == ["model"]


def test_unrelated_400_is_not_retried():
    class Other(Exception):
        status_code = 400

        def __str__(self) -> str:
            return "400 invalid_request_error: max_tokens is too large"

    def call(_params):
        raise Other()

    with pytest.raises(Other):
        call_with_sampling_retry("claude-sonnet-4-6", {"temperature": 0}, call)


def test_wrapper_retries_generate_after_a_sampling_400(caplog):
    calls: list[dict] = []

    class ChatAnthropic:
        def __init__(self, *args, **kwargs):
            self.model = kwargs.get("model")
            self.temperature = kwargs.get("temperature", None)
            self.top_p = kwargs.get("top_p", None)
            self.top_k = kwargs.get("top_k", None)

        def _get_request_payload(self):
            payload = {"model": self.model}
            if self.temperature is not None:
                payload["temperature"] = self.temperature
            if self.top_p is not None:
                payload["top_p"] = self.top_p
            if self.top_k is not None:
                payload["top_k"] = self.top_k
            return payload

        def _generate(self):
            payload = self._get_request_payload()
            calls.append(payload)
            if "temperature" in payload or "top_p" in payload or "top_k" in payload:
                raise _SamplingError()
            return "ok"

    class LLM:
        def import_module(self, name, package=None):
            return self.modules[name]

        def _build_anthropic(self, **kwargs):
            module = self.import_module("langchain_anthropic")
            return module.ChatAnthropic(**kwargs)

    llm = LLM()
    llm.modules = {"langchain_anthropic": type("Mod", (), {"ChatAnthropic": ChatAnthropic})()}
    patch_anthropic_builder(llm, "")
    client = llm._build_anthropic(model="claude-sonnet-4-6", temperature=0, top_p=0.2, top_k=8)
    with caplog.at_level(logging.WARNING):
        assert client._generate() == "ok"
    assert calls[0]["temperature"] == 0
    assert "temperature" not in calls[1]
    assert "top_p" not in calls[1]
    assert "top_k" not in calls[1]
    assert "retrying once" in caplog.text.lower()


def test_anthropic_model_override_and_page_selection():
    parent = {"ANTHROPIC_API_KEY": "test-anthropic-key", "ANTHROPIC_MODEL": "claude-opus-5-5"}
    child = provider_child_env("anthropic", parent)
    assert child["LANGCHAIN_MODEL_NAME"] == "claude-opus-5-5"
    picked = provider_child_env("anthropic", parent, model="claude-fable-5-2")
    assert picked["LANGCHAIN_MODEL_NAME"] == "claude-fable-5-2"
    assert resolve_model("anthropic", "claude-sonnet-5-5", parent) == "claude-sonnet-5-5"
    with pytest.raises(ValueError, match="Unknown Anthropic model"):
        resolve_model("anthropic", "claude-sonnet-4-6", parent)
