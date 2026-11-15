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
        "note": "Optional ANTHROPIC_WORKSPACE_ID is sent as anthropic-workspace-id. Set ANTHROPIC_MODEL to change the default.",
    },
}

ANTHROPIC_MODELS: list[dict[str, str]] = [
    {"id": "claude-sonnet-5-5", "label": "claude-sonnet-5-5", "note": ""},
    {
        "id": "claude-opus-5-5",
        "label": "claude-opus-5-5",
        "note": "Costs several times more than Sonnet.",
    },
    {
        "id": "claude-fable-5-2",
        "label": "claude-fable-5-2",
        "note": "Costs several times more than Sonnet.",
    },
]


def key_is_set(env_name: str, source: dict[str, str] | None = None) -> bool:
    values = source if source is not None else os.environ
    return bool(str(values.get(env_name, "")).strip())


def _values(source: dict[str, str] | None) -> dict[str, str]:
    if source is not None:
        return source
    return dict(os.environ)


def anthropic_choices(source: dict[str, str] | None = None) -> list[dict[str, str]]:
    """The page's Anthropic models. ``ANTHROPIC_MODEL`` is included when it is new."""
    choices = [dict(item) for item in ANTHROPIC_MODELS]
    override = str(_values(source).get("ANTHROPIC_MODEL", "")).strip()
    if override and override not in {item["id"] for item in choices}:
        choices.insert(0, {"id": override, "label": override, "note": ""})
    return choices


def default_model(provider_id: str, source: dict[str, str] | None = None) -> str:
    spec = PROVIDERS[provider_id]
    if provider_id == "anthropic":
        override = str(_values(source).get("ANTHROPIC_MODEL", "")).strip()
        if override:
            return override
    return spec["model"]


def resolve_model(provider_id: str, requested: str = "", source: dict[str, str] | None = None) -> str:
    """Pick the model for one run. An Anthropic page selection must be listed."""
    requested = (requested or "").strip()
    if provider_id != "anthropic":
        return default_model(provider_id, source)
    allowed = {item["id"] for item in anthropic_choices(source)}
    if requested:
        if requested not in allowed:
            raise ValueError("Unknown Anthropic model.")
        return requested
    return default_model(provider_id, source)


def provider_child_env(
    provider_id: str,
    base: dict[str, str] | None = None,
    model: str | None = None,
) -> dict[str, str]:
    """Return a serve-process environment for one provider.

    The returned dict is a copy. ``base`` is not modified, so a parent process
    that also holds an OpenAI key keeps that key when the child is pointed at xAI.
    """
    spec = PROVIDERS[provider_id]
    env = dict(os.environ if base is None else base)
    env["LANGCHAIN_PROVIDER"] = spec["langchain_provider"]
    env["LANGCHAIN_MODEL_NAME"] = model or default_model(provider_id, env)
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
