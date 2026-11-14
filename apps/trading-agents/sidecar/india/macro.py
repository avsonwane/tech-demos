"""India macro series from Yahoo Finance, plus the static RBI note."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from india.rbi_note import NOTE
from india.sources import Source

# Longer keys are matched first so "information technology" wins over a shorter token.
SECTOR_INDEXES: tuple[tuple[str, str, str], ...] = (
    ("information technology", "^CNXIT", "Nifty IT"),
    ("financial services", "^CNXFIN", "Nifty Financial Services"),
    ("consumer defensive", "^CNXFMCG", "Nifty FMCG"),
    ("consumer staples", "^CNXFMCG", "Nifty FMCG"),
    ("consumer cyclical", "^CNXAUTO", "Nifty Auto"),
    ("basic materials", "^CNXMETAL", "Nifty Metal"),
    ("communication", "^CNXMEDIA", "Nifty Media"),
    ("technology", "^CNXIT", "Nifty IT"),
    ("healthcare", "^CNXPHARMA", "Nifty Pharma"),
    ("utilities", "^CNXENERGY", "Nifty Energy"),
    ("energy", "^CNXENERGY", "Nifty Energy"),
    ("pharma", "^CNXPHARMA", "Nifty Pharma"),
    ("bank", "^NSEBANK", "Nifty Bank"),
    ("fmcg", "^CNXFMCG", "Nifty FMCG"),
    ("metal", "^CNXMETAL", "Nifty Metal"),
    ("realty", "^CNXREALTY", "Nifty Realty"),
    ("real estate", "^CNXREALTY", "Nifty Realty"),
    ("auto", "^CNXAUTO", "Nifty Auto"),
    ("oil", "^CNXENERGY", "Nifty Energy"),
    ("gas", "^CNXENERGY", "Nifty Energy"),
    ("media", "^CNXMEDIA", "Nifty Media"),
)


@dataclass
class SeriesSnap:
    symbol: str
    label: str
    unit: str
    last_date: str | None = None
    last: float | None = None
    change_21d: float | None = None
    change_63d: float | None = None
    error: str | None = None


def sector_index(sector: str | None, industry: str | None) -> tuple[str, str] | None:
    haystack = f"{industry or ''} {sector or ''}".lower()
    for key, symbol, label in sorted(SECTOR_INDEXES, key=lambda item: len(item[0]), reverse=True):
        if key in haystack:
            return symbol, label
    return None


def load_series(symbol: str, label: str, unit: str, as_of: date) -> SeriesSnap:
    try:
        import yfinance as yf
    except Exception as exc:
        return SeriesSnap(symbol, label, unit, error=f"yfinance is not installed ({exc.__class__.__name__}).")
    try:
        history = yf.Ticker(symbol).history(
            start=(as_of - timedelta(days=220)).isoformat(),
            end=(as_of + timedelta(days=1)).isoformat(),
            auto_adjust=True,
        )
    except Exception as exc:
        return SeriesSnap(symbol, label, unit, error=f"{exc.__class__.__name__}: {exc}")
    if history is None or getattr(history, "empty", True) or "Close" not in getattr(history, "columns", []):
        return SeriesSnap(symbol, label, unit, error=f"No closes for {symbol} on or before {as_of.isoformat()}.")
    closes: list[tuple[date, float]] = []
    for stamp, value in history["Close"].items():
        try:
            day = stamp.date()
        except AttributeError:
            continue
        if day <= as_of:
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            closes.append((day, number))
    if not closes:
        return SeriesSnap(symbol, label, unit, error=f"No closes for {symbol} on or before {as_of.isoformat()}.")
    last_day, last = closes[-1]
    return SeriesSnap(
        symbol=symbol,
        label=label,
        unit=unit,
        last_date=last_day.isoformat(),
        last=last,
        change_21d=_change(closes, 21),
        change_63d=_change(closes, 63),
    )


def format_snap(snap: SeriesSnap) -> str:
    if snap.error or snap.last is None:
        return f"{snap.label} ({snap.symbol}): unavailable ({snap.error or 'no close'})."
    text = f"{snap.label} ({snap.symbol}): {snap.last:,.2f} {snap.unit} on {snap.last_date}"
    moves = []
    if snap.change_21d is not None:
        moves.append(f"{snap.change_21d:+.1f}% over 21 sessions")
    if snap.change_63d is not None:
        moves.append(f"{snap.change_63d:+.1f}% over 63 sessions")
    if moves:
        text += ", " + ", ".join(moves)
    return text + "."


def series_source(source_id: str, snap: SeriesSnap) -> Source:
    if snap.error or snap.last is None:
        return Source(source_id, snap.label, "failed", snap.error or "No close on or before the as-of date.")
    detail = f"{snap.last:,.2f} {snap.unit} on {snap.last_date}"
    if snap.change_21d is not None:
        detail += f", {snap.change_21d:+.1f}% over 21 sessions"
    return Source(source_id, snap.label, "ok", detail)


def relative_strength(stock: SeriesSnap, nifty: SeriesSnap, sector: SeriesSnap | None) -> str:
    if stock.change_21d is None or nifty.change_21d is None:
        return "Nifty relative strength was not computed because a 21-session change was missing."
    spread = stock.change_21d - nifty.change_21d
    text = (
        f"Relative strength: {stock.label} {stock.change_21d:+.1f}% over 21 sessions versus "
        f"Nifty 50 {nifty.change_21d:+.1f}% (spread {spread:+.1f} percentage points)."
    )
    if sector and sector.change_21d is not None and sector.symbol != stock.symbol:
        sector_spread = stock.change_21d - sector.change_21d
        text += (
            f" Versus {sector.label} {sector.change_21d:+.1f}% "
            f"(spread {sector_spread:+.1f} percentage points)."
        )
    return text


def rbi_source() -> Source:
    return Source("rbi_note", "RBI repo rate and CPI", "ok", "Static config, not a live fetch. " + NOTE)


def render_macro(
    *,
    snaps: list[SeriesSnap],
    strength: str,
    flows: str,
) -> str:
    lines = [
        "Source: India macro set. FRED is not used. "
        "Prices and index levels are Yahoo Finance. The RBI repo rate and CPI are the static desk note.",
        strength,
        NOTE,
    ]
    lines.extend(format_snap(snap) for snap in snaps)
    lines.append(flows)
    return "\n".join(lines)


def _change(closes: list[tuple[date, float]], sessions: int) -> float | None:
    if len(closes) <= sessions:
        return None
    previous = closes[-(sessions + 1)][1]
    last = closes[-1][1]
    if previous == 0:
        return None
    return (last / previous - 1) * 100
