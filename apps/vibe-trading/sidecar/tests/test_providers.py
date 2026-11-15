from launch_serve import patch_anthropic_builder
from providers import provider_child_env


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
    assert anthropic["LANGCHAIN_MODEL_NAME"] == "claude-sonnet-4-6"
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
            return module.ChatAnthropic(model=kwargs.get("model"))

    llm = LLM()
    llm.modules = {"langchain_anthropic": type("Mod", (), {"ChatAnthropic": ChatAnthropic})()}
    patch_anthropic_builder(llm, "wrkspc_test")
    llm._build_anthropic(model="claude-sonnet-4-6")
    headers = captured["kwargs"]["default_headers"]
    assert headers["anthropic-workspace-id"] == "wrkspc_test"
    assert llm.import_module.__func__ is LLM.import_module
