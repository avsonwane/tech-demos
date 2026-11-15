"""Reject Yahoo symbols that have no prices before a session starts.

WELSPUN.NS is not a Yahoo symbol. A live session on it used to finish with
empty bars and no message. Suffixed symbols in the prompt (RELIANCE.NS,
WELSPUN.NS) are checked with a short yfinance history call. Replay of the
shipped sample does not call this.
"""

from __future__ import annotations

import re

_SUFFIXED = re.compile(r"\b([A-Za-z][A-Za-z0-9]{0,12}\.[A-Za-z]{1,4})\b")


def suffixed_symbols(prompt: str) -> list[str]:
    seen: list[str] = []
    for match in _SUFFIXED.findall(prompt or ""):
        symbol = match.upper()
        if symbol not in seen:
            seen.append(symbol)
    return seen


def ticker_error(symbol: str) -> str:
    return f"No price data for {symbol} on Yahoo Finance. Check the ticker symbol."


def yahoo_has_prices(symbol: str) -> bool:
    """True when Yahoo returns at least one daily bar for ``symbol``."""
    import yfinance as yf

    frame = yf.Ticker(symbol).history(period="5d", auto_adjust=False)
    return frame is not None and len(frame) > 0


def missing_symbol(prompt: str, lookup=yahoo_has_prices) -> str | None:
    """Return the first suffixed symbol whose lookup says there are no prices.

    A lookup that raises is skipped. The caller still refuses an empty run.
    """
    for symbol in suffixed_symbols(prompt):
        try:
            ok = lookup(symbol)
        except Exception:
            continue
        if not ok:
            return symbol
    return None


def empty_price_message(prompt: str, result: dict | None) -> str | None:
    """Map a finished run with no equity bars back to the ticker error."""
    if not result or result.get("illustrative"):
        return None
    equity = result.get("equity") or []
    if equity:
        return None
    symbols = suffixed_symbols(prompt)
    if not symbols:
        return None
    return ticker_error(symbols[0])


def data_error_message(prompt: str, text: str) -> str | None:
    """Rewrite an engine error about missing bars or a missing timezone."""
    lowered = (text or "").lower()
    if "timezone" not in lowered and "no price" not in lowered and "no data" not in lowered:
        return None
    symbols = suffixed_symbols(prompt)
    if not symbols:
        return None
    return ticker_error(symbols[0])
