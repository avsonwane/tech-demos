"""Confirm the installed package still routes NSE tickers to India equity rules."""

from backtest.engines._market_hooks import matched_market

from app import PRESETS


def test_nse_suffix_is_india_equity_and_the_preset_stays():
    assert matched_market("RELIANCE.NS") == "india_equity"
    assert matched_market("M&M.NS") == "india_equity"
    assert matched_market("500325.BO") == "india_equity"
    assert matched_market("AAPL") == "us_equity"
    assert matched_market("BTC-USDT") == "crypto"
    # A suffix with no market rule is not silently treated as A-shares.
    assert matched_market("7203.T") is None
    prompts = [preset["prompt"] for preset in PRESETS]
    assert any("RELIANCE.NS" in prompt for prompt in prompts)
