"""The pinned TradingAgents checkout still exposes the API this desk calls."""


def test_pinned_library_exposes_propagate_and_the_default_vendors():
    from tradingagents.agents.rating import run_rating
    from tradingagents.default_config import DEFAULT_CONFIG
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    assert DEFAULT_CONFIG["llm_provider"] == "openai"
    assert DEFAULT_CONFIG["deep_think_llm"]
    assert DEFAULT_CONFIG["quick_think_llm"]
    vendors = DEFAULT_CONFIG["data_vendors"]
    assert vendors["core_stock_apis"] == "yfinance"
    assert vendors["technical_indicators"] == "yfinance"
    assert "yfinance" in vendors["fundamental_data"]
    assert vendors["news_data"] == "yfinance"
    assert vendors["macro_data"] == "fred"
    assert DEFAULT_CONFIG["max_debate_rounds"] == 1
    assert hasattr(TradingAgentsGraph, "propagate")
    assert hasattr(TradingAgentsGraph, "stream_run")
    assert hasattr(TradingAgentsGraph, "create_run_state")
    assert hasattr(TradingAgentsGraph, "record_decision")
    assert run_rating({"final_trade_decision": "Rating: Hold\nStay aside."}) == "Hold"
