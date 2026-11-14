"""LLM providers this desk exposes.

Model ids match TradingAgents' catalog at the pinned commit. The library
default provider is OpenAI; this desk lists xAI first and defaults the form
to Grok 4.6.
"""

from __future__ import annotations

PROVIDERS: dict[str, dict] = {
    "xai": {
        "label": "xAI",
        "env": "XAI_API_KEY",
        "quick": [
            ("Grok 4.6", "grok-4.6"),
            ("Grok Build 0.1", "grok-build-0.1"),
        ],
        "deep": [
            ("Grok 4.6", "grok-4.6"),
            ("Grok 4.5", "grok-4.5"),
            ("Grok 4.3", "grok-4.3"),
        ],
        "quick_default": "grok-4.6",
        "deep_default": "grok-4.6",
    },
    "openai": {
        "label": "OpenAI",
        "env": "OPENAI_API_KEY",
        "quick": [
            ("GPT-6 Luna", "gpt-6-luna"),
            ("GPT-5.6 Luna", "gpt-5.6-luna"),
            ("GPT-5.6 Terra", "gpt-5.6-terra"),
        ],
        "deep": [
            ("GPT-6 Sol", "gpt-6-sol"),
            ("GPT-6 Astra", "gpt-6-astra"),
            ("GPT-5.6", "gpt-5.6"),
            ("GPT-5.5", "gpt-5.5"),
        ],
        "quick_default": "gpt-6-luna",
        "deep_default": "gpt-6-sol",
    },
    "anthropic": {
        "label": "Anthropic",
        "env": "ANTHROPIC_API_KEY",
        "quick": [
            ("Claude Sonnet 5", "claude-sonnet-5"),
            ("Claude Haiku 4.5", "claude-haiku-4-5"),
        ],
        "deep": [
            ("Claude Opus 5.5", "claude-opus-5-5"),
            ("Claude Fable 5.1", "claude-fable-5-1"),
            ("Claude Sonnet 5", "claude-sonnet-5"),
        ],
        "quick_default": "claude-sonnet-5",
        "deep_default": "claude-opus-5-5",
    },
    "google": {
        "label": "Google",
        "env": "GOOGLE_API_KEY",
        "quick": [
            ("Gemini 3.8 Flash", "gemini-3.8-flash"),
            ("Gemini 3.5 Flash Lite", "gemini-3.5-flash-lite"),
            ("Gemini 3.1 Flash Lite", "gemini-3.1-flash-lite"),
        ],
        "deep": [
            ("Gemini 3.8 Flash", "gemini-3.8-flash"),
            ("Gemini 3.1 Pro", "gemini-3.1-pro-preview"),
            ("Gemini 3.5 Flash", "gemini-3.5-flash"),
        ],
        "quick_default": "gemini-3.8-flash",
        "deep_default": "gemini-3.8-flash",
    },
}
