from tickers import (
    data_error_message,
    empty_price_message,
    missing_symbol,
    suffixed_symbols,
    ticker_error,
)


def test_welspun_has_no_yahoo_prices():
    def lookup(symbol: str) -> bool:
        return symbol != "WELSPUN.NS"

    prompt = "Backtest a 20/50 SMA crossover on WELSPUN.NS for 2024 vs buy-and-hold"
    assert suffixed_symbols(prompt) == ["WELSPUN.NS"]
    assert missing_symbol(prompt, lookup) == "WELSPUN.NS"
    assert ticker_error("WELSPUN.NS") == (
        "No price data for WELSPUN.NS on Yahoo Finance. Check the ticker symbol."
    )
    assert missing_symbol("Backtest RELIANCE.NS for 2024", lookup) is None


def test_a_lookup_error_does_not_invent_a_missing_symbol():
    def lookup(_symbol: str) -> bool:
        raise TimeoutError("yahoo down")

    assert missing_symbol("Backtest WELSPUN.NS", lookup) is None


def test_empty_bars_and_a_missing_timezone_use_the_same_message():
    prompt = "Backtest WELSPUN.NS"
    message = "No price data for WELSPUN.NS on Yahoo Finance. Check the ticker symbol."
    assert empty_price_message(prompt, {"equity": [], "illustrative": False}) == message
    assert empty_price_message(prompt, {"equity": [{"equity": 1}], "illustrative": False}) is None
    assert empty_price_message(prompt, {"equity": [], "illustrative": True}) is None
    assert data_error_message(prompt, "No timezone found, symbol may be delisted") == message
    assert data_error_message("Backtest AAPL", "No timezone found") is None
