"""Map desk providers onto Vibe-Trading's LANGCHAIN_* settings.

vibe-trading-ai 0.1.19 has catalog entries for OpenAI and Anthropic and none
for xAI. xAI is sent through the OpenAI-compatible client at api.x.ai.
"""

from __future__ import annotations

import os

XAI_BASE_URL = "https://api.x.ai/v1"
OPENAI_BASE_URL = "https://api.openai.com/v1"

PROVIDERS: dict[str, dict[str, str]] = {
    "xai": {
        "label": "xAI",
        "env": "XAI_API_KEY",
        "model": "grok-4.6",
        "langchain_provider": "openai",
        "note": "No xAI entry in the 0.1.19 catalog. The serve process uses the OpenAI-compatible client at https://api.x.ai/v1.",
    },
    "openai": {
        "label": "OpenAI",
        "env": "OPENAI_API_KEY",
        "model": "gpt-5.5",
        "langchain_provider": "openai",
        "note": "Catalog default model on vibe-trading-ai 0.1.19.",
    },
    "anthropic": {
        "label": "Anthropic",
        "env": "ANTHROPIC_API_KEY",
        "model": "claude-sonnet-5-5",
        "langchain_provider": "anthropic",
        "note": "Prefer claude-sonnet-5-5 over the 0.1.19 catalog default (claude-sonnet-4-6). Optional ANTHROPIC_WORKSPACE_ID is sent as anthropic-workspace-id.",
    },
}


def key_is_set(env_name: str, source: dict[str, str] | None = None) -> bool:
    values = source if source is not None else os.environ
    return bool(str(values.get(env_name, "")).strip())


def provider_child_env(provider_id: str, base: dict[str, str] | None = None) -> dict[str, str]:
    """Return a serve-process environment for one provider.

    The returned dict is a copy. ``base`` is not modified, so a parent process
    that also holds an OpenAI key keeps that key when the child is pointed at xAI.
    """
    spec = PROVIDERS[provider_id]
    env = dict(os.environ if base is None else base)
    env["LANGCHAIN_PROVIDER"] = spec["langchain_provider"]
    env["LANGCHAIN_MODEL_NAME"] = spec["model"]
    if provider_id == "xai":
        env["OPENAI_API_KEY"] = str(env.get("XAI_API_KEY", "")).strip()
        env["OPENAI_BASE_URL"] = XAI_BASE_URL
    elif provider_id == "openai":
        configured = str(env.get("OPENAI_BASE_URL", "")).strip()
        env["OPENAI_BASE_URL"] = configured or OPENAI_BASE_URL
    return env


def preferred_provider(source: dict[str, str] | None = None) -> str:
    for provider_id in PROVIDERS:
        if key_is_set(PROVIDERS[provider_id]["env"], source):
            return provider_id
    return "xai"
