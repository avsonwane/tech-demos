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


def live_events(ticker: str, as_of: str, provider: str, quick_model: str, deep_model: str, debate_rounds: int):
    from tradingagents.agents.rating import run_rating
    from tradingagents.default_config import DEFAULT_CONFIG
    from tradingagents.graph.trading_graph import TradingAgentsGraph

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

    asset_type = "crypto" if ticker.endswith("-USD") else "stock"
    graph = TradingAgentsGraph(
        selected_analysts=["market", "social", "news", "fundamentals"],
        debug=False,
        config=config,
    )
    init_state = graph.create_run_state(ticker, as_of, asset_type=asset_type)
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


def key_is_set(env_name: str) -> bool:
    return bool(os.environ.get(env_name, "").strip())
