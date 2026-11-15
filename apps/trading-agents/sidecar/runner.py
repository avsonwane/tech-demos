"""Run TradingAgents and yield the same stage events the sample replays.

``propagate`` returns only the finished state. With ``debug=True`` it walks
``stream_run`` and then records the decision. This runner does that walk
itself so the desk can show each stage as the graph files it, and it still
calls ``record_decision`` when the run finishes.
"""

from __future__ import annotations

import copy
import os
from pathlib import Path

from stages import absorb, diff_chunk

SIDECAR = Path(__file__).resolve().parent
RUN_DATA = SIDECAR / ".run-data"

_ANTHROPIC_WORKSPACE_PATCHED = False


def _install_anthropic_workspace_header() -> None:
    """Send ``ANTHROPIC_WORKSPACE_ID`` on every Anthropic request, if set.

    Unscoped Anthropic API keys require the ``anthropic-workspace-id`` header.
    TradingAgents' Anthropic client only forwards a fixed kwargs list and does
    not include ``default_headers``, so this adds that passthrough and injects
    the header before ``ChatAnthropic`` is built.
    """
    global _ANTHROPIC_WORKSPACE_PATCHED
    if _ANTHROPIC_WORKSPACE_PATCHED:
        return

    workspace_id = os.environ.get("ANTHROPIC_WORKSPACE_ID", "").strip()
    if not workspace_id:
        return

    from tradingagents.llm_clients import anthropic_client as ac

    if "default_headers" not in ac._PASSTHROUGH_KWARGS:
        ac._PASSTHROUGH_KWARGS = (*ac._PASSTHROUGH_KWARGS, "default_headers")

    original_get_llm = ac.AnthropicClient.get_llm

    def get_llm(self):
        headers = dict(self.kwargs.get("default_headers") or {})
        headers.setdefault("anthropic-workspace-id", workspace_id)
        self.kwargs["default_headers"] = headers
        return original_get_llm(self)

    ac.AnthropicClient.get_llm = get_llm  # type: ignore[method-assign]
    _ANTHROPIC_WORKSPACE_PATCHED = True


def live_events(
    ticker: str,
    as_of: str,
    provider: str,
    quick_model: str,
    deep_model: str,
    debate_rounds: int,
    *,
    india_mode: bool = False,
    bundle=None,
):
    from tradingagents.agents.rating import run_rating
    from tradingagents.default_config import DEFAULT_CONFIG
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    _install_anthropic_workspace_header()

    config = copy.deepcopy(DEFAULT_CONFIG)
    config["results_dir"] = str(RUN_DATA / "logs")
    config["data_cache_dir"] = str(RUN_DATA / "cache")
    config["memory_log_path"] = str(RUN_DATA / "memory" / "trading_memory.md")
    config["llm_provider"] = provider
    config["quick_think_llm"] = quick_model
    config["deep_think_llm"] = deep_model
    config["quick_think_provider"] = None
    config["deep_think_provider"] = None
    config["backend_url"] = None
    config["max_debate_rounds"] = debate_rounds
    config["max_risk_discuss_rounds"] = debate_rounds
    config["checkpoint_enabled"] = False

    token = None
    if india_mode:
        from india.bundle import bind_bundle, collect
        from india.vendor import apply_india_config, install_india_hooks

        install_india_hooks()
        apply_india_config(config)
        if bundle is None:
            bundle = collect(ticker, as_of)
        token = bind_bundle(bundle)

    try:
        asset_type = "crypto" if ticker.endswith("-USD") else "stock"
        graph = TradingAgentsGraph(
            selected_analysts=["market", "social", "news", "fundamentals"],
            debug=False,
            config=config,
        )
        init_state = graph.create_run_state(ticker, as_of, asset_type=asset_type)
        if bundle is not None:
            prior = init_state.get("instrument_context") or ""
            extra = bundle.prompt_context
            if bundle.tradingview_text:
                extra = f"{extra}\n\n{bundle.tradingview_text}"
            init_state["instrument_context"] = f"{prior}\n\n{extra}"
        args = graph.propagator.get_graph_args()
        state: dict = {}
        for _messages, chunk in graph.stream_run(init_state, **args):
            if not chunk:
                continue
            rating = None
            if chunk.get("final_trade_decision") or chunk.get("final_rating"):
                preview = {**state, **{key: value for key, value in chunk.items() if key != "messages"}}
                rating = run_rating(preview)
            events = diff_chunk(state, chunk, rating=rating)
            absorb(state, chunk)
            yield from events
        if state.get("final_trade_decision"):
            graph.record_decision(ticker, as_of, state)
    finally:
        if token is not None:
            from india.bundle import reset_bundle

            reset_bundle(token)


def key_is_set(env_name: str) -> bool:
    return bool(os.environ.get(env_name, "").strip())
