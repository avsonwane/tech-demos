"""Optional TradingView technical summary for an NSE or BSE equity.

Uses ``tradingview-ta``, the technical-summary library behind the MIT
``tradingview-mcp-server``. That library reads TradingView's screener scan
over HTTP. It is not a chart websocket client. The result is an extra block.
Yahoo prices, Screener.in, the news feeds, and NSE are left as they are.
"""

from __future__ import annotations

from india.detect import normalize_symbol
from india.sources import Source, clip

_TIMEOUT_SECONDS = 12
_OSCILLATORS = ("RSI", "MACD", "ADX", "Stoch.K", "CCI", "Mom", "AO", "W%R", "UO", "BBP", "Stoch.RSI")
_AVERAGES = ("EMA10", "EMA20", "EMA50", "EMA200", "SMA10", "SMA20", "SMA50", "SMA200")
_VALUES = (
    ("RSI", "RSI"),
    ("MACD.macd", "MACD"),
    ("MACD.signal", "MACD signal"),
    ("ADX", "ADX"),
    ("ADX+DI", "ADX +DI"),
    ("ADX-DI", "ADX -DI"),
    ("Stoch.K", "Stochastic %K"),
    ("CCI20", "CCI"),
    ("Mom", "Momentum"),
    ("close", "Close"),
)


def tradingview_symbol(ticker: str) -> tuple[str, str, str] | None:
    """Map ``RELIANCE.NS`` to ``("NSE", "RELIANCE", "NSE:RELIANCE")``. Indexes return None."""

    symbol = normalize_symbol(ticker)
    if symbol.endswith(".NS"):
        code = symbol[:-3]
        return ("NSE", code, f"NSE:{code}") if code else None
    if symbol.endswith(".BO"):
        code = symbol[:-3]
        return ("BSE", code, f"BSE:{code}") if code else None
    return None


def fetch_tradingview(ticker: str, *, loader=None) -> tuple[Source, str]:
    """One attempt per timeframe. Timeout skips. 401, 403, and 429 are blocked."""

    mapped = tradingview_symbol(ticker)
    if mapped is None:
        detail = "Not an NSE or BSE equity. TradingView was not queried."
        return (
            Source("tradingview", "TradingView technicals", "skipped", detail),
            _note(normalize_symbol(ticker) or ticker, detail),
        )
    exchange, code, label = mapped
    load = loader or load_interval
    frames: list[dict] = []
    problems: list[tuple[str, str, str]] = []
    for interval, frame_label in (("1d", "1D"), ("1W", "1W")):
        try:
            frames.append(load(exchange, code, interval))
        except Exception as exc:
            problems.append((frame_label, _status_from_error(exc), clip(f"{exc.__class__.__name__}: {exc}")))
    if not frames:
        status = "blocked" if any(item[1] == "blocked" for item in problems) else "skipped"
        detail = "; ".join(f"{name} {reason}" for name, _status, reason in problems) or "No technical summary."
        if status == "blocked":
            detail = f"Blocked, not retried. {detail}"
        else:
            detail = f"Skipped, not retried. {detail}"
        return Source("tradingview", "TradingView technicals", status, clip(detail, 240)), _note(label, detail)
    text = render_technicals(label, frames, problems)
    summary = ", ".join(
        f"{_frame_name(frame)} {_recommendation(frame.get('summary'))}" for frame in frames
    )
    if problems:
        summary += ". " + "; ".join(f"{name} {status}" for name, status, _reason in problems)
    return Source("tradingview", "TradingView technicals", "ok", clip(f"{label} {summary}. Supplementary.")), text


def load_interval(exchange: str, symbol: str, interval: str) -> dict:
    """One screener-scan request. ``timeout`` is passed through to the library."""

    from tradingview_ta import TA_Handler

    handler = TA_Handler(
        symbol=symbol,
        screener="india",
        exchange=exchange,
        interval=interval,
        timeout=_TIMEOUT_SECONDS,
    )
    analysis = handler.get_analysis()
    return {
        "interval": interval,
        "summary": dict(getattr(analysis, "summary", None) or {}),
        "oscillators": dict(getattr(analysis, "oscillators", None) or {}),
        "moving_averages": dict(getattr(analysis, "moving_averages", None) or {}),
        "indicators": dict(getattr(analysis, "indicators", None) or {}),
    }


def render_technicals(label: str, frames: list[dict], problems: list[tuple[str, str, str]]) -> str:
    lines = [
        "TradingView technicals (supplementary)",
        f"Symbol: {label}. Source: tradingview-ta screener scan, 1D and 1W.",
        "This does not replace Yahoo Finance prices, Yahoo indicators, Screener.in, Indian news, or NSE.",
    ]
    for frame in frames:
        lines.append(_render_frame(frame))
    for name, status, reason in problems:
        lines.append(f"{name}: {status} ({reason}). Not retried.")
    return "\n".join(lines)


def _render_frame(frame: dict) -> str:
    name = _frame_name(frame)
    summary = frame.get("summary") or {}
    oscillators = frame.get("oscillators") or {}
    averages = frame.get("moving_averages") or {}
    indicators = frame.get("indicators") or {}
    parts = [
        f"{name} summary: {_recommendation(summary)} "
        f"(buy {summary.get('BUY', '—')}, sell {summary.get('SELL', '—')}, neutral {summary.get('NEUTRAL', '—')})",
        f"{name} oscillators: {_recommendation(oscillators)} ({_compute(oscillators, _OSCILLATORS)})",
        f"{name} moving averages: {_recommendation(averages)} ({_compute(averages, _AVERAGES)})",
        f"{name} values: {_values(indicators)}",
    ]
    return "\n".join(parts)


def _note(label: str, detail: str) -> str:
    return (
        "TradingView technicals (supplementary)\n"
        f"Symbol: {label}\n"
        f"{detail}\n"
        "Yahoo Finance prices and indicators are unchanged. This source added nothing."
    )


def _frame_name(frame: dict) -> str:
    interval = str(frame.get("interval") or "")
    if interval.lower() in {"1d", "1day"}:
        return "1D"
    if interval.lower() in {"1w", "1week"}:
        return "1W"
    return interval or "frame"


def _recommendation(block: object) -> str:
    if not isinstance(block, dict):
        return "—"
    value = block.get("RECOMMENDATION")
    return str(value) if value else "—"


def _compute(block: dict, keys: tuple[str, ...]) -> str:
    compute = block.get("COMPUTE") if isinstance(block, dict) else None
    if not isinstance(compute, dict) or not compute:
        return "no breakdown"
    chosen = [f"{key} {compute[key]}" for key in keys if key in compute]
    if not chosen:
        chosen = [f"{key} {value}" for key, value in list(compute.items())[:8]]
    return ", ".join(chosen)


def _values(indicators: dict) -> str:
    if not isinstance(indicators, dict):
        return "none"
    parts = []
    for key, label in _VALUES:
        if key not in indicators or indicators[key] in (None, ""):
            continue
        number = indicators[key]
        if isinstance(number, (int, float)) and not isinstance(number, bool):
            parts.append(f"{label} {number:.2f}")
        else:
            parts.append(f"{label} {number}")
    return ", ".join(parts) if parts else "none"


def _status_from_error(exc: BaseException) -> str:
    response = getattr(exc, "response", None)
    code = getattr(response, "status_code", None)
    if code in {401, 403, 429}:
        return "blocked"
    text = f"{exc.__class__.__name__} {exc}".lower()
    if any(token in text for token in ("401", "403", "429", "forbidden", "blocked")):
        return "blocked"
    return "skipped"
