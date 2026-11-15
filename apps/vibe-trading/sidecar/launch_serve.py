"""Start ``vibe-trading serve`` and attach the Anthropic workspace header.

vibe-trading-ai 0.1.19 builds ``ChatAnthropic`` without ``default_headers``.
Unscoped Anthropic keys need ``anthropic-workspace-id``. When
``ANTHROPIC_WORKSPACE_ID`` is set, the builder's import of
``langchain_anthropic`` is wrapped so that header is passed into the client.

langchain-anthropic also rejects a non-default ``temperature`` (and ``top_p`` /
``top_k``) for ``claude-sonnet-5-5`` and ``claude-fable-5*`` before the request
is sent. vibe-trading-ai 0.1.19's temperature-safe wrapper only retries after
an API error, so those models fail on the default 0.0 temperature. The same
wrapper clears those sampling fields.
"""

from __future__ import annotations

import os
import sys
from types import ModuleType
from typing import Any


def _needs_default_sampling(model: str) -> bool:
    name = (model or "").strip().lower()
    return name.startswith("claude-sonnet-5-5") or name.startswith("claude-fable-5")


def patch_anthropic_builder(llm_module: Any, workspace_id: str) -> None:
    """Wrap ``llm_module._build_anthropic`` so new clients send the workspace id.

    The wrapper is installed even when ``workspace_id`` is empty, so
    ``claude-sonnet-5-5`` still drops a non-default temperature.
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
                        if _needs_default_sampling(model):
                            temp = kw.get("temperature")
                            if temp is not None and temp != 1:
                                kw["temperature"] = None
                            top_p = kw.get("top_p")
                            if top_p is not None and top_p != 1:
                                kw["top_p"] = None
                            if kw.get("top_k") is not None:
                                kw["top_k"] = None
                        super().__init__(*args, **kw)

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
    # Always install the ChatAnthropic wrapper so sonnet-5-5 can drop
    # a non-default temperature even when no workspace id is set.
    import src.providers.llm as llm

    patch_anthropic_builder(llm, os.environ.get("ANTHROPIC_WORKSPACE_ID", "").strip())


def main() -> int:
    install_workspace_header()
    from cli import main as cli_main

    port = os.environ.get("VIBE_SERVE_PORT", "8899")
    return int(cli_main(["serve", "--host", "127.0.0.1", "--port", port]))


if __name__ == "__main__":
    sys.exit(main())
