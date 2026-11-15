"""Start ``vibe-trading serve`` and attach the Anthropic workspace header.

vibe-trading-ai 0.1.19 builds ``ChatAnthropic`` without ``default_headers``.
Unscoped Anthropic keys need ``anthropic-workspace-id``. When
``ANTHROPIC_WORKSPACE_ID`` is set, the builder's import of
``langchain_anthropic`` is wrapped so that header is passed into the client.
"""

from __future__ import annotations

import os
import sys
from types import ModuleType
from typing import Any


def patch_anthropic_builder(llm_module: Any, workspace_id: str) -> None:
    """Wrap ``llm_module._build_anthropic`` so new clients send the workspace id."""
    workspace_id = workspace_id.strip()
    if not workspace_id:
        return
    original = llm_module._build_anthropic

    def _build_anthropic(**kwargs: Any) -> Any:
        real_import = llm_module.import_module

        def importing(name: str, package: str | None = None) -> ModuleType:
            module = real_import(name, package)
            if name == "langchain_anthropic" and not getattr(module, "_vibe_desk_workspace", False):
                chat = module.ChatAnthropic

                class WorkspaceChat(chat):  # type: ignore[misc, valid-type]
                    def __init__(self, *args: Any, **kw: Any) -> None:
                        headers = dict(kw.get("default_headers") or {})
                        headers.setdefault("anthropic-workspace-id", workspace_id)
                        kw["default_headers"] = headers
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
    workspace_id = os.environ.get("ANTHROPIC_WORKSPACE_ID", "").strip()
    if not workspace_id:
        return
    import src.providers.llm as llm

    patch_anthropic_builder(llm, workspace_id)


def main() -> int:
    install_workspace_header()
    from cli import main as cli_main

    port = os.environ.get("VIBE_SERVE_PORT", "8899")
    return int(cli_main(["serve", "--host", "127.0.0.1", "--port", port]))


if __name__ == "__main__":
    sys.exit(main())
