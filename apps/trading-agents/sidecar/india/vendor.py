"""Register India fetchers on the TradingAgents router and skip US social feeds.

The library is not forked. ``VENDOR_METHODS`` is a mutable dict, and the
sentiment analyst builds its prompt from a function we can wrap. Both wrappers
no-op unless an India bundle is bound for the run.
"""

from __future__ import annotations

from datetime import date

from india.bundle import IndiaBundle, current_bundle
from india.rss import render_headlines
from india.sentiment import sentiment_system_message

_UNAVAILABLE = (
    "DATA_UNAVAILABLE: the India-mode bundle was not loaded for this call. "
    "Do not estimate or fabricate values."
)
_INSTALLED = False


def apply_india_config(config: dict) -> None:
    """Point fundamentals, news, and macro at the ``india`` vendor. Prices stay on Yahoo."""

    vendors = config.setdefault("data_vendors", {})
    vendors["fundamental_data"] = "india"
    vendors["news_data"] = "india"
    vendors["macro_data"] = "india"


def install_india_hooks() -> None:
    """Add the vendor once, and wrap sentiment so StockTwits and Reddit are not called."""

    global _INSTALLED
    if _INSTALLED:
        return

    from tradingagents.dataflows.router import VENDOR_METHODS

    VENDOR_METHODS["get_fundamentals"]["india"] = get_fundamentals
    VENDOR_METHODS["get_income_statement"]["india"] = get_income_statement
    VENDOR_METHODS["get_balance_sheet"]["india"] = get_balance_sheet
    VENDOR_METHODS["get_cashflow"]["india"] = get_cashflow
    VENDOR_METHODS["get_news"]["india"] = get_news
    VENDOR_METHODS["get_global_news"]["india"] = get_global_news
    VENDOR_METHODS["get_insider_transactions"]["india"] = get_insider_transactions
    VENDOR_METHODS["get_macro_indicators"]["india"] = get_macro_indicators

    import tradingagents.agents.analysts.sentiment_analyst as sentiment

    original_message = sentiment._build_system_message
    original_stocktwits = sentiment.fetch_stocktwits_messages
    original_reddit = sentiment.fetch_reddit_posts

    def system_message(**kwargs):
        bundle = current_bundle()
        if bundle is None:
            return original_message(**kwargs)
        return sentiment_system_message(
            ticker=kwargs.get("ticker") or bundle.ticker,
            start=kwargs.get("start_date") or bundle.as_of,
            end=kwargs.get("end_date") or bundle.as_of,
            block=bundle.sentiment_text,
        )

    def stocktwits(*args, **kwargs):
        if current_bundle() is not None:
            return "Skipped in India mode. StockTwits is not used for this listing."
        return original_stocktwits(*args, **kwargs)

    def reddit(*args, **kwargs):
        if current_bundle() is not None:
            return "Skipped in India mode. Reddit is not used for this listing."
        return original_reddit(*args, **kwargs)

    sentiment._build_system_message = system_message
    sentiment.fetch_stocktwits_messages = stocktwits
    sentiment.fetch_reddit_posts = reddit
    _INSTALLED = True


def get_fundamentals(ticker: str, curr_date: str) -> str:
    bundle = _bundle()
    if isinstance(bundle, str):
        return bundle
    return _labeled(bundle, bundle.fundamentals_text, curr_date, ticker)


def get_income_statement(ticker: str, freq: str, curr_date: str) -> str:
    bundle = _bundle()
    if isinstance(bundle, str):
        return bundle
    note = ""
    if str(freq).lower().startswith("annual"):
        note = "Annual was requested. India mode serves the quarterly statement.\n"
    return note + _labeled(bundle, bundle.income_text, curr_date, ticker)


def get_balance_sheet(ticker: str, freq: str, curr_date: str) -> str:
    bundle = _bundle()
    if isinstance(bundle, str):
        return bundle
    note = ""
    if str(freq).lower().startswith("annual"):
        note = "Annual was requested. India mode serves the quarterly statement.\n"
    return note + _labeled(bundle, bundle.balance_text, curr_date, ticker)


def get_cashflow(ticker: str, freq: str, curr_date: str) -> str:
    bundle = _bundle()
    if isinstance(bundle, str):
        return bundle
    note = ""
    if str(freq).lower().startswith("annual"):
        note = "Annual was requested. India mode serves the quarterly statement.\n"
    return note + _labeled(bundle, bundle.cashflow_text, curr_date, ticker)


def get_news(ticker: str, start_date: str, end_date: str) -> str:
    bundle = _bundle()
    if isinstance(bundle, str):
        return bundle
    start, end = _window(start_date, end_date, bundle)
    company = _between(bundle.company_headlines, start, end)
    google = _between(bundle.google_headlines, start, end)
    return "\n\n".join(
        [
            f"India news for {ticker}. Window {start.isoformat()} to {end.isoformat()}. "
            "StockTwits and Reddit were not called.",
            "Company headlines\n" + render_headlines(company, empty="No company headlines in this window."),
            "Google News RSS\n" + render_headlines(google, empty="No Google News items in this window."),
            bundle.announcements_text,
        ]
    )


def get_global_news(curr_date: str, look_back_days: int | None = None, limit: int | None = None) -> str:
    bundle = _bundle()
    if isinstance(bundle, str):
        return bundle
    end = _parse(curr_date) or date.fromisoformat(bundle.as_of)
    days = look_back_days if isinstance(look_back_days, int) and look_back_days > 0 else 7
    start = date.fromordinal(end.toordinal() - days)
    cap = limit if isinstance(limit, int) and limit > 0 else 12
    rows = _between(bundle.market_headlines, start, end)[:cap]
    return "\n\n".join(
        [
            "Indian market headlines. FRED is not used. "
            "get_macro_indicators returns INR/USD, India VIX, Nifty 50, the sector index, Brent, "
            "the static RBI note, and NSE FII/DII flows.",
            render_headlines(rows, empty="No market headlines in this window."),
        ]
    )


def get_insider_transactions(ticker: str, trade_date: str | None = None) -> str:
    del ticker, trade_date
    bundle = _bundle()
    if isinstance(bundle, str):
        return bundle
    return bundle.insider_text


def get_macro_indicators(indicator: str, curr_date: str, look_back_days: int | None = None) -> str:
    del look_back_days
    bundle = _bundle()
    if isinstance(bundle, str):
        return bundle
    return (
        f"India mode: FRED is not used. Requested indicator {indicator!r} on {curr_date} "
        "is answered with the India macro set.\n\n"
        + bundle.macro_text
    )


def _bundle() -> IndiaBundle | str:
    bundle = current_bundle()
    if bundle is None:
        return _UNAVAILABLE
    return bundle


def _labeled(bundle: IndiaBundle, body: str, curr_date: str, ticker: str) -> str:
    return f"{ticker} as of {curr_date}. Collected for {bundle.ticker} on {bundle.as_of}.\n\n{body}"


def _window(start_date: str, end_date: str, bundle: IndiaBundle) -> tuple[date, date]:
    end = _parse(end_date) or date.fromisoformat(bundle.as_of)
    start = _parse(start_date) or end
    if start > end:
        start, end = end, start
    return start, end


def _between(items, start: date, end: date):
    chosen = []
    for item in items:
        if item.published is None:
            continue
        if start <= item.published <= end:
            chosen.append(item)
    return chosen


def _parse(value: str | None) -> date | None:
    try:
        return date.fromisoformat((value or "")[:10])
    except ValueError:
        return None
