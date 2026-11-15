"""Which symbols India mode treats as Indian listings."""

from __future__ import annotations

INDIA_INDEXES = {
    "^NSEI": "Nifty 50",
    "^BSESN": "BSE Sensex",
    "^NSEBANK": "Nifty Bank",
}


def normalize_symbol(ticker: str) -> str:
    return (ticker or "").strip().upper()


def is_india_symbol(ticker: str) -> bool:
    """True for Yahoo NSE/BSE suffixes and the three Indian indexes on the form."""

    symbol = normalize_symbol(ticker)
    return symbol.endswith(".NS") or symbol.endswith(".BO") or symbol in INDIA_INDEXES


def bare_symbol(ticker: str) -> str:
    """NSE/BSE code without the Yahoo suffix. Indexes stay as written."""

    symbol = normalize_symbol(ticker)
    if symbol.endswith(".NS") or symbol.endswith(".BO"):
        return symbol[:-3]
    return symbol


def listing_kind(ticker: str) -> str:
    """``nse``, ``bse``, ``index``, or ``other``."""

    symbol = normalize_symbol(ticker)
    if symbol in INDIA_INDEXES:
        return "index"
    if symbol.endswith(".NS"):
        return "nse"
    if symbol.endswith(".BO"):
        return "bse"
    return "other"


def listing_label(ticker: str) -> str:
    symbol = normalize_symbol(ticker)
    if symbol.endswith(".NS"):
        return "NSE listing, Yahoo suffix .NS"
    if symbol.endswith(".BO"):
        return "BSE listing, Yahoo suffix .BO"
    if symbol in INDIA_INDEXES:
        return f"{INDIA_INDEXES[symbol]} ({symbol})"
    return "India mode is on, but this symbol is not an NSE/BSE Yahoo ticker or ^NSEI, ^BSESN, or ^NSEBANK"


def quotes_in_inr(ticker: str) -> bool:
    """Rupee labels apply to Indian listings. A forced toggle on NVDA does not relabel dollars."""

    return is_india_symbol(ticker)


def index_aliases(ticker: str) -> list[str]:
    symbol = normalize_symbol(ticker)
    table = {
        "^NSEI": ["Nifty 50", "Nifty", "NSE Nifty"],
        "^BSESN": ["Sensex", "BSE Sensex"],
        "^NSEBANK": ["Nifty Bank", "Bank Nifty"],
    }
    return list(table.get(symbol, []))
