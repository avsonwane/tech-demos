"""Yahoo Finance quarterly statements and ratios for an NSE/BSE ticker."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from india.screener import format_table
from india.sources import Source, clip

_INCOME = (
    "Total Revenue",
    "Operating Income",
    "Net Income",
    "EBITDA",
    "Basic EPS",
    "Diluted EPS",
)
_BALANCE = (
    "Total Assets",
    "Total Liabilities Net Minority Interest",
    "Stockholders Equity",
    "Total Debt",
    "Cash And Cash Equivalents",
    "Working Capital",
)
_CASH = (
    "Operating Cash Flow",
    "Capital Expenditure",
    "Free Cash Flow",
    "Repayment Of Debt",
    "Issuance Of Debt",
)
_RATIOS = (
    ("trailingPE", "Trailing P/E"),
    ("forwardPE", "Forward P/E"),
    ("priceToBook", "Price / book"),
    ("returnOnEquity", "ROE"),
    ("returnOnAssets", "ROA"),
    ("profitMargins", "Profit margin"),
    ("operatingMargins", "Operating margin"),
    ("debtToEquity", "Debt / equity"),
    ("currentRatio", "Current ratio"),
    ("dividendYield", "Dividend yield"),
    ("bookValue", "Book value"),
    ("marketCap", "Market cap"),
    ("enterpriseToEbitda", "EV / EBITDA"),
    ("trailingEps", "Trailing EPS"),
)
_PERCENT = {"returnOnEquity", "returnOnAssets", "profitMargins", "operatingMargins", "dividendYield"}


@dataclass
class Statement:
    columns: list[str]
    rows: list[tuple[str, list[str]]]


@dataclass
class YahooPack:
    name: str | None
    sector: str | None
    industry: str | None
    currency: str | None
    ratios: list[tuple[str, str]]
    income: Statement
    balance: Statement
    cashflow: Statement
    error: str | None = None

    @property
    def useful(self) -> bool:
        return bool(self.ratios or self.income.rows or self.balance.rows or self.cashflow.rows)


def empty_statement() -> Statement:
    return Statement(columns=[], rows=[])


def load_yahoo(symbol: str, as_of: date) -> YahooPack:
    """Pull quarterly statements. ``as_of`` is recorded on the label; Yahoo's statements are the latest filed."""

    del as_of
    try:
        import yfinance as yf
    except Exception as exc:
        return _failed(f"yfinance is not installed ({exc.__class__.__name__}).")
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info if isinstance(getattr(ticker, "info", None), dict) else {}
        return YahooPack(
            name=_text(info.get("longName")) or _text(info.get("shortName")),
            sector=_text(info.get("sector")),
            industry=_text(info.get("industry")),
            currency=_text(info.get("currency")),
            ratios=_ratios(info),
            income=_from_frame(getattr(ticker, "quarterly_income_stmt", None), _INCOME),
            balance=_from_frame(getattr(ticker, "quarterly_balance_sheet", None), _BALANCE),
            cashflow=_from_frame(getattr(ticker, "quarterly_cashflow", None), _CASH),
        )
    except Exception as exc:
        return _failed(clip(f"{exc.__class__.__name__}: {exc}"))


def render_ratios(pack: YahooPack, symbol: str) -> str:
    currency = pack.currency or "INR"
    lines = [
        f"Source: Yahoo Finance via yfinance for {symbol}. Currency field: {currency}. "
        "For .NS and .BO listings these figures are rupees (₹). Quarterly statements are the latest Yahoo holds, "
        "not a reconstructed filing as of an older date."
    ]
    if pack.name:
        lines.append(f"Name: {pack.name}")
    if pack.sector or pack.industry:
        lines.append(f"Sector / industry: {pack.sector or '—'} / {pack.industry or '—'}")
    if pack.ratios:
        lines.append("Key ratios\n" + "\n".join(f"- {label}: {value}" for label, value in pack.ratios))
    else:
        lines.append("Key ratios: Yahoo returned none.")
    return "\n".join(lines)


def render_statement(title: str, statement: Statement, *, freq: str) -> str:
    note = ""
    if freq.lower().startswith("annual"):
        note = " Annual was requested. India mode serves the quarterly Yahoo statement.\n"
    body = format_table(title, statement.columns, statement.rows)
    return f"Source: Yahoo Finance quarterly statement.{note}\n{body}"


def financials_source(pack: YahooPack) -> Source:
    if pack.error:
        return Source("yfinance_financials", "Yahoo Finance financials", "failed", pack.error)
    if not pack.useful:
        return Source(
            "yfinance_financials",
            "Yahoo Finance financials",
            "failed",
            "No ratios and no quarterly income, balance sheet, or cash flow rows.",
        )
    detail = (
        f"{len(pack.ratios)} ratios, {len(pack.income.rows)} income rows, "
        f"{len(pack.balance.rows)} balance rows, {len(pack.cashflow.rows)} cash flow rows."
    )
    if pack.currency:
        detail += f" Currency {pack.currency}."
    return Source("yfinance_financials", "Yahoo Finance financials", "ok", detail)


def _failed(message: str) -> YahooPack:
    return YahooPack(None, None, None, None, [], empty_statement(), empty_statement(), empty_statement(), message)


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _ratios(info: dict) -> list[tuple[str, str]]:
    currency = _text(info.get("currency")) or "INR"
    rows: list[tuple[str, str]] = []
    for key, label in _RATIOS:
        if key not in info or info[key] in (None, ""):
            continue
        rows.append((label, _ratio_value(key, info[key], currency)))
    return rows


def _ratio_value(key: str, value: object, currency: str) -> str:
    number = _number(value)
    if number is None:
        return str(value)
    if key in _PERCENT and abs(number) <= 2:
        # yfinance 1.8 reports dividendYield already in percent (0.45 means 0.45%).
        # ROE and margins are still fractions. A yield above 20% arrives as a number above 0.2.
        if key == "dividendYield" and abs(number) > 0.2:
            return f"{number:.2f}%"
        return f"{number * 100:.2f}%"
    if key == "marketCap":
        prefix = "₹" if currency == "INR" else f"{currency} "
        return f"{prefix}{number:,.0f}"
    if abs(number) >= 100:
        return f"{number:,.2f}"
    return f"{number:.2f}"


def _from_frame(frame: object, wanted: tuple[str, ...]) -> Statement:
    if frame is None or getattr(frame, "empty", True):
        return empty_statement()
    columns_raw = list(frame.columns)[:4]
    columns = [_column_label(column) for column in columns_raw]
    names = [str(name) for name in list(frame.index)]
    picked = _pick(names, wanted)
    rows: list[tuple[str, list[str]]] = []
    for name in picked:
        series = frame.loc[name]
        if hasattr(series, "columns"):
            series = series.iloc[0]
        values = [_cell(value) for value in list(series)[:4]]
        rows.append((name, values))
    return Statement(columns=columns, rows=rows)


def _pick(names: list[str], wanted: tuple[str, ...]) -> list[str]:
    chosen: list[str] = []
    for want in wanted:
        for name in names:
            if want.lower() in name.lower() and name not in chosen:
                chosen.append(name)
                break
    return chosen or names[:8]


def _column_label(column: object) -> str:
    if hasattr(column, "strftime"):
        try:
            return column.strftime("%Y-%m-%d")
        except (TypeError, ValueError):
            pass
    return str(column)[:10]


def _cell(value: object) -> str:
    number = _number(value)
    if number is None:
        if value is None:
            return "—"
        return str(value)
    if abs(number) >= 100:
        return f"{number:,.0f}"
    return f"{number:,.2f}"


def _number(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        if math.isnan(number) or math.isinf(number):
            return None
        return number
    return None
