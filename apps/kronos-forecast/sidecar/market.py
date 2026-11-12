"""Free OHLCV. Crypto *USDT pairs use Binance public klines. Everything else uses Yahoo Finance."""

from __future__ import annotations

import time

import httpx
import pandas as pd

# data-api.binance.vision is Binance's public market-data host. api.binance.com
# answers 451 in some regions, so try the vision host first.
BINANCE_KLINES = [
    "https://data-api.binance.vision/api/v3/klines",
    "https://api.binance.com/api/v3/klines",
]

TIMEFRAMES: dict[str, dict[str, str]] = {
    "15m": {"binance": "15m", "pandas": "15min", "yf_interval": "15m", "yf_period": "60d"},
    "1h": {"binance": "1h", "pandas": "1h", "yf_interval": "1h", "yf_period": "730d"},
    "4h": {"binance": "4h", "pandas": "4h", "yf_interval": "1h", "yf_period": "730d", "resample": "4h"},
    "1d": {"binance": "1d", "pandas": "1D", "yf_interval": "1d", "yf_period": "5y"},
}


class MarketError(Exception):
    pass


def is_binance_symbol(symbol: str) -> bool:
    text = symbol.strip().upper()
    return text.endswith("USDT") and text.isalnum() and 5 <= len(text) <= 20


def parse_binance_klines(raw: list) -> pd.DataFrame:
    rows = []
    for item in raw:
        rows.append(
            {
                "timestamp": pd.to_datetime(int(item[0]), unit="ms", utc=True),
                "open": float(item[1]),
                "high": float(item[2]),
                "low": float(item[3]),
                "close": float(item[4]),
                "volume": float(item[5]),
                "amount": float(item[7]),
                "close_time_ms": int(item[6]),
            }
        )
    if not rows:
        raise MarketError("Binance returned no candles.")
    return pd.DataFrame(rows)


def fetch_ohlcv(symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    if timeframe not in TIMEFRAMES:
        raise MarketError("Timeframe must be 15m, 1h, 4h, or 1d.")
    cleaned = symbol.strip().upper()
    if not cleaned or len(cleaned) > 20:
        raise MarketError("Enter a ticker such as BTCUSDT or AAPL.")
    limit = max(10, min(int(limit), 1000))
    if is_binance_symbol(cleaned):
        frame = _fetch_binance(cleaned, timeframe, limit)
    else:
        frame = _fetch_yahoo(cleaned, timeframe, limit)
    frame = frame.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)
    if frame.empty:
        raise MarketError(f"No candles for {cleaned}.")
    return frame.tail(limit).reset_index(drop=True)


def future_timestamps(history: pd.Series, pred_len: int, timeframe: str) -> pd.DatetimeIndex:
    ts = pd.to_datetime(pd.Series(history), utc=True)
    if len(ts) == 0:
        raise MarketError("No history to extend.")
    # Equity daily series have no weekend bars. Crypto daily series do.
    if timeframe == "1d" and not bool((ts.dt.day_of_week >= 5).any()):
        start = ts.iloc[-1].tz_convert("UTC").tz_localize(None)
        future = pd.bdate_range(start, periods=pred_len + 1)[1:]
        return future.tz_localize("UTC")

    deltas = ts.diff().dropna()
    delta = deltas.median() if len(deltas) else pd.NaT
    if pd.isna(delta) or delta <= pd.Timedelta(0):
        delta = pd.Timedelta(TIMEFRAMES[timeframe]["pandas"])
    return pd.date_range(ts.iloc[-1] + delta, periods=pred_len, freq=delta)


def _fetch_binance(symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    params = {"symbol": symbol, "interval": TIMEFRAMES[timeframe]["binance"], "limit": limit}
    last_error: Exception | None = None
    payload = None
    for url in BINANCE_KLINES:
        try:
            response = httpx.get(url, params=params, timeout=20.0)
            if response.status_code == 451:
                last_error = MarketError(f"Binance host refused the request ({response.status_code}).")
                continue
            response.raise_for_status()
            payload = response.json()
            break
        except httpx.HTTPError as exc:
            last_error = MarketError(f"Binance request failed: {exc}")
    if payload is None:
        raise last_error or MarketError("Binance request failed.")
    if isinstance(payload, dict):
        raise MarketError(payload.get("msg") or f"Binance rejected {symbol}.")
    frame = parse_binance_klines(payload)
    now_ms = int(time.time() * 1000)
    if len(frame) > 2 and int(frame.iloc[-1]["close_time_ms"]) > now_ms:
        frame = frame.iloc[:-1]
    return frame.drop(columns=["close_time_ms"]).reset_index(drop=True)


def _fetch_yahoo(symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
    import yfinance as yf

    spec = TIMEFRAMES[timeframe]
    try:
        downloaded = yf.download(
            symbol,
            period=spec["yf_period"],
            interval=spec["yf_interval"],
            auto_adjust=False,
            progress=False,
            threads=False,
        )
    except Exception as exc:
        raise MarketError(f"Yahoo Finance request failed: {exc}") from exc
    if downloaded is None or downloaded.empty:
        raise MarketError(f"Yahoo Finance has no data for {symbol}.")
    frame = downloaded.copy()
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)
    frame = frame.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"})
    missing = {"open", "high", "low", "close"}.difference(frame.columns)
    if missing:
        raise MarketError(f"Yahoo Finance response is missing {sorted(missing)}.")
    frame = frame.reset_index()
    time_col = "Date" if "Date" in frame.columns else "Datetime" if "Datetime" in frame.columns else frame.columns[0]
    frame = frame.rename(columns={time_col: "timestamp"})
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    if "volume" not in frame.columns:
        frame["volume"] = 0.0
    keep = frame[["timestamp", "open", "high", "low", "close", "volume"]].dropna()
    if spec.get("resample"):
        keep = (
            keep.set_index("timestamp")
            .resample("4h")
            .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
            .dropna()
            .reset_index()
        )
    typical = keep[["open", "high", "low", "close"]].astype(float).mean(axis=1)
    keep["amount"] = keep["volume"].astype(float) * typical
    return keep.reset_index(drop=True)
