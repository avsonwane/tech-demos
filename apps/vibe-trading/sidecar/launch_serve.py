"""Start ``vibe-trading serve`` and attach the Anthropic workspace header.

vibe-trading-ai 0.1.19 builds ``ChatAnthropic`` without ``default_headers``.
Unscoped Anthropic keys need ``anthropic-workspace-id``. When
``ANTHROPIC_WORKSPACE_ID`` is set, the builder's import of
``langchain_anthropic`` is wrapped so that header is passed into the client.

Claude 5 models (``claude-sonnet-5*``, ``claude-opus-5*``, ``claude-fable-5*``,
``claude-haiku-5*``) reject ``temperature``, ``top_p``, and ``top_k``. The
wrapper never sends those fields for those models and uses the model defaults.
If any Anthropic call still returns HTTP 400 ``invalid_request_error`` that
mentions one of those fields, the wrapper retries once without them and logs
a warning. Claude 4 models keep the sampling values the caller passed.
"""

from __future__ import annotations

import logging
import os
import re
import sys
from types import ModuleType
from typing import Any, Callable

logger = logging.getLogger("vibe_desk.anthropic")

_CLAUDE_5 = re.compile(r"^claude-(?:sonnet|opus|fable|haiku)-5", re.IGNORECASE)
SAMPLING_KEYS = ("temperature", "top_p", "top_k")


def uses_model_defaults(model: str) -> bool:
    """True for Claude 5 models that must not be sent sampling fields."""
    return bool(_CLAUDE_5.match((model or "").strip()))


def strip_sampling(params: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(params)
    for key in SAMPLING_KEYS:
        cleaned.pop(key, None)
    return cleaned


def sampling_rejected(exc: BaseException) -> bool:
    """True for a 400 invalid_request_error that mentions a sampling field."""
    status = getattr(exc, "status_code", None)
    if status is None:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
    body = getattr(exc, "body", None)
    text = f"{exc} {body or ''}".lower()
    if status != 400 and "400" not in text:
        return False
    if "invalid_request_error" not in text:
        return False
    return any(name in text for name in SAMPLING_KEYS)


def call_with_sampling_retry(
    model: str,
    params: dict[str, Any],
    call: Callable[[dict[str, Any]], Any],
    warn: Callable[[str], None] | None = None,
) -> Any:
    """Call once with sampling stripped for Claude 5, and retry a sampling 400."""
    prepared = strip_sampling(params) if uses_model_defaults(model) else dict(params)
    try:
        return call(prepared)
    except Exception as exc:
        if not sampling_rejected(exc):
            raise
        message = (
            "Anthropic returned 400 invalid_request_error for temperature, top_p, or top_k. "
            "Retrying once without those fields."
        )
        if warn is not None:
            warn(message)
        else:
            logger.warning(message)
        return call(strip_sampling(prepared))


def patch_anthropic_builder(llm_module: Any, workspace_id: str) -> None:
    """Wrap ``llm_module._build_anthropic`` so new clients send the workspace id.

    The wrapper is installed even when ``workspace_id`` is empty, so Claude 5
    models still drop sampling fields.
    """
    workspace_id = workspace_id.strip()
    original = llm_module._build_anthropic

    def _build_anthropic(**kwargs: Any) -> Any:
        real_import = llm_module.import_module

        def importing(name: str, package: str | None = None) -> ModuleType:
            module = real_import(name, package)
            if name == "langchain_anthropic" and not getattr(module, "_vibe_desk_workspace", False):
                chat = module.ChatAnthropic

                class WorkspaceChat(chat):  # type: ignore[misc, valid-type]
                    def __init__(self, *args: Any, **kw: Any) -> None:
                        if workspace_id:
                            headers = dict(kw.get("default_headers") or {})
                            headers.setdefault("anthropic-workspace-id", workspace_id)
                            kw["default_headers"] = headers
                        model = str(kw.get("model") or (args[0] if args else "") or "")
                        if uses_model_defaults(model):
                            for key in SAMPLING_KEYS:
                                kw.pop(key, None)
                        super().__init__(*args, **kw)
                        self._vibe_sampling_retried = False
                        self._vibe_drop_sampling = uses_model_defaults(str(getattr(self, "model", model)))

                    def _get_request_payload(self, *args: Any, **kw: Any) -> Any:
                        payload = super()._get_request_payload(*args, **kw)
                        if isinstance(payload, dict) and getattr(self, "_vibe_drop_sampling", False):
                            for key in SAMPLING_KEYS:
                                payload.pop(key, None)
                        return payload

                    def _generate(self, *args: Any, **kw: Any) -> Any:
                        try:
                            return super()._generate(*args, **kw)
                        except Exception as exc:
                            if self._vibe_sampling_retried or not sampling_rejected(exc):
                                raise
                            self._vibe_sampling_retried = True
                            self._vibe_drop_sampling = True
                            for key in SAMPLING_KEYS:
                                if hasattr(self, key):
                                    setattr(self, key, None)
                            logger.warning(
                                "Anthropic returned 400 invalid_request_error for temperature, "
                                "top_p, or top_k. Retrying once without those fields."
                            )
                            return super()._generate(*args, **kw)

                module.ChatAnthropic = WorkspaceChat
                module._vibe_desk_workspace = True
            return module

        llm_module.import_module = importing
        try:
            return original(**kwargs)
        finally:
            llm_module.import_module = real_import

    llm_module._build_anthropic = _build_anthropic


def install_workspace_header() -> None:
    # Always install the ChatAnthropic wrapper. Claude 5 models drop sampling
    # fields even when no workspace id is set.
    import src.providers.llm as llm

    patch_anthropic_builder(llm, os.environ.get("ANTHROPIC_WORKSPACE_ID", "").strip())


def main() -> int:
    install_workspace_header()
    from cli import main as cli_main

    port = os.environ.get("VIBE_PORT") or os.environ.get("VIBE_SERVE_PORT") or "8899"
    return int(cli_main(["serve", "--host", "127.0.0.1", "--port", port]))


if __name__ == "__main__":
    sys.exit(main())
