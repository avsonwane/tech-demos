import pandas as pd

from market import future_timestamps, is_binance_symbol, parse_binance_klines


def test_binance_symbol_detection():
    assert is_binance_symbol("btcusdt")
    assert not is_binance_symbol("AAPL")
    assert not is_binance_symbol("BTC-USD")


def test_parse_binance_klines():
    raw = [[
        1_700_000_000_000,
        "100.5",
        "110",
        "90",
        "105",
        "12.5",
        1_700_003_599_999,
        "1300.25",
        10,
        "0",
        "0",
        "0",
    ]]
    frame = parse_binance_klines(raw)
    assert frame.loc[0, "open"] == 100.5
    assert frame.loc[0, "close"] == 105
    assert frame.loc[0, "amount"] == 1300.25
    assert frame.loc[0, "timestamp"] == pd.Timestamp("2023-11-14T22:13:20Z")


def test_hourly_future_steps_from_the_last_bar():
    start = pd.Timestamp("2026-01-01T00:00:00Z")
    history = pd.Series([start + pd.Timedelta(hours=i) for i in range(10)])
    future = future_timestamps(history, 3, "1h")
    assert list(future) == [
        start + pd.Timedelta(hours=10),
        start + pd.Timedelta(hours=11),
        start + pd.Timedelta(hours=12),
    ]


def test_equity_daily_skips_the_weekend():
    history = pd.Series(pd.bdate_range("2026-01-05", "2026-01-16", tz="UTC"))
    assert int(history.iloc[-1].weekday()) == 4
    future = future_timestamps(history, 1, "1d")
    assert int(future[0].weekday()) == 0


def test_crypto_daily_keeps_the_weekend_step():
    history = pd.Series(pd.date_range("2026-01-10", periods=8, freq="1D", tz="UTC"))
    assert bool((history.dt.day_of_week >= 5).any())
    future = future_timestamps(history, 2, "1d")
    assert future[0] - history.iloc[-1] == pd.Timedelta(days=1)
