"""Collect every India-mode source once, then let the vendor tools reuse it."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from datetime import date, timedelta

from india.detect import bare_symbol, listing_kind, listing_label, normalize_symbol, quotes_in_inr
from india.macro import load_series, relative_strength, render_macro, rbi_source, sector_index, series_source
from india.nse import fetch_flows, fetch_nse
from india.prompts import india_context
from india.rss import FEEDS, Headline, aliases_for, fetch_feed, fetch_google_news, render_headlines, select_headlines
from india.screener import fetch_screener
from india.sentiment import sentiment_input, tone_summary
from india.sources import Source
from india.statements import financials_source, load_yahoo, render_ratios, render_statement
from india.tradingview import fetch_tradingview

_LOOKBACK = 30
_bundle: ContextVar[IndiaBundle | None] = ContextVar("india_bundle", default=None)


@dataclass
class IndiaBundle:
    ticker: str
    as_of: str
    sources: list[Source] = field(default_factory=list)
    company_name: str | None = None
    company_headlines: list[Headline] = field(default_factory=list)
    market_headlines: list[Headline] = field(default_factory=list)
    google_headlines: list[Headline] = field(default_factory=list)
    fundamentals_text: str = ""
    income_text: str = ""
    balance_text: str = ""
    cashflow_text: str = ""
    news_text: str = ""
    global_news_text: str = ""
    insider_text: str = ""
    macro_text: str = ""
    sentiment_text: str = ""
    prompt_context: str = ""
    announcements_text: str = ""
    tradingview_text: str = ""

    def public_sources(self) -> list[dict[str, str]]:
        return [source.as_dict() for source in self.sources]


def current_bundle() -> IndiaBundle | None:
    return _bundle.get()


def bind_bundle(bundle: IndiaBundle) -> Token:
    return _bundle.set(bundle)


def reset_bundle(token: Token) -> None:
    _bundle.reset(token)


def collect(ticker: str, as_of: str) -> IndiaBundle:
    """Fetch Indian inputs for one run. A failed source is a row, not an exception."""

    symbol = normalize_symbol(ticker)
    as_of_date = date.fromisoformat(as_of)
    window_start = as_of_date - timedelta(days=_LOOKBACK)
    kind = listing_kind(symbol)
    pack = load_yahoo(symbol, as_of_date)
    name = pack.name
    if kind == "index" and not name:
        name = listing_label(symbol)
    aliases = aliases_for(symbol, None if kind == "index" else name)
    mapped = sector_index(pack.sector, pack.industry)
    unit = "INR" if quotes_in_inr(symbol) else (pack.currency or "points")

    with ThreadPoolExecutor(max_workers=8) as pool:
        screener_future = None if kind == "index" else pool.submit(fetch_screener, bare_symbol(symbol))
        feed_futures = [pool.submit(fetch_feed, feed_id, label, url) for feed_id, label, url in FEEDS]
        google_future = pool.submit(fetch_google_news, aliases)
        exchange_future = pool.submit(_exchange, kind, symbol, as_of_date)
        series_future = pool.submit(_series, symbol, name or symbol, unit, as_of_date, mapped)
        tradingview_future = pool.submit(fetch_tradingview, symbol)

        sources: list[Source] = []
        if kind == "index":
            sources.append(
                Source(
                    "yfinance_financials",
                    "Yahoo Finance financials",
                    "skipped",
                    "This symbol is an index. There is no company income statement.",
                )
            )
            screener_text = "Screener.in does not have a company page for an index."
            sources.append(Source("screener", "Screener.in", "skipped", "Index symbol. No company page."))
        else:
            sources.append(financials_source(pack))
            screener_source, screener_text = screener_future.result()
            sources.append(screener_source)

        feed_items: list[Headline] = []
        for future in feed_futures:
            source, items = future.result()
            matched = select_headlines(
                items, aliases=aliases, start=window_start, end=as_of_date, require_alias=True, limit=8
            )
            if source.status == "ok":
                source = Source(source.id, source.label, "ok", f"{source.detail} {len(matched)} matched the name.")
            sources.append(source)
            feed_items.extend(items)

        google_source, google_items = google_future.result()
        google_matched = select_headlines(
            google_items, aliases=aliases, start=window_start, end=as_of_date, require_alias=False, limit=10
        )
        if google_source.status == "ok":
            google_source = Source(
                google_source.id,
                google_source.label,
                "ok",
                f"{google_source.detail} {len(google_matched)} inside the window.",
            )
        sources.append(google_source)
        ann_source, ann_text, flow_source, flow_text = exchange_future.result()
        stock_snap, nifty, vix, inr, brent, sector_snap = series_future.result()
        tradingview_source, tradingview_text = tradingview_future.result()

    sources.append(ann_source)
    sources.append(tradingview_source)

    company_headlines = select_headlines(
        feed_items, aliases=aliases, start=window_start, end=as_of_date, require_alias=True, limit=16
    )
    market_headlines = select_headlines(
        feed_items, aliases=aliases, start=window_start, end=as_of_date, require_alias=False, limit=12
    )
    tone = tone_summary(company_headlines + google_matched)
    sources.append(Source("headline_tone", "Headline tone", "ok" if company_headlines or google_matched else "failed", tone))
    sources.append(Source("stocktwits", "StockTwits", "skipped", "Not used in India mode."))
    sources.append(Source("reddit", "Reddit", "skipped", "Not used in India mode."))
    sources.append(Source("fred", "FRED", "skipped", "Replaced by the India macro set. No FRED call."))

    sources.extend(
        [
            series_source("inr_usd", inr),
            series_source("india_vix", vix),
            series_source("nifty", nifty),
            series_source("brent", brent),
        ]
    )
    if sector_snap is not None:
        sources.append(series_source("sector_index", sector_snap))
    elif kind == "index":
        sources.append(
            Source("sector_index", "Sector index", "skipped", "The symbol is already an index. No second sector series.")
        )
    else:
        sources.append(
            Source(
                "sector_index",
                "Sector index",
                "skipped",
                f"No sector index mapped for {pack.sector or 'an unknown sector'}.",
            )
        )
    sources.append(rbi_source())
    sources.append(flow_source)

    strength = relative_strength(stock_snap, nifty, sector_snap)
    snaps = [stock_snap, inr, vix, nifty, brent]
    if sector_snap is not None:
        snaps.append(sector_snap)
    macro_text = render_macro(snaps=snaps, strength=strength, flows=flow_text)
    sentiment_text = sentiment_input(
        ticker=symbol,
        start=window_start.isoformat(),
        end=as_of_date.isoformat(),
        tone=tone,
        company=company_headlines,
        google=google_matched,
    )
    caveat = (
        "Live pages filtered to the as-of window. Not a point-in-time archive. "
        f"Window {window_start.isoformat()} to {as_of_date.isoformat()}."
    )
    bundle = IndiaBundle(
        ticker=symbol,
        as_of=as_of_date.isoformat(),
        sources=_ordered(sources),
        company_name=name,
        company_headlines=company_headlines,
        market_headlines=market_headlines,
        google_headlines=google_matched,
        fundamentals_text="\n\n".join(
            part for part in (render_ratios(pack, symbol) if kind != "index" else "Index: no company fundamentals.", screener_text) if part
        ),
        income_text=render_statement("Quarterly income statement", pack.income, freq="quarterly")
        if kind != "index"
        else "Index: no income statement.",
        balance_text=render_statement("Quarterly balance sheet", pack.balance, freq="quarterly")
        if kind != "index"
        else "Index: no balance sheet.",
        cashflow_text=render_statement("Quarterly cash flow", pack.cashflow, freq="quarterly")
        if kind != "index"
        else "Index: no cash flow statement.",
        announcements_text=ann_text,
        tradingview_text=tradingview_text,
        insider_text=_insider_text(screener_text if kind != "index" else "No shareholding for an index."),
        macro_text=macro_text,
        sentiment_text=sentiment_text,
        news_text="",
        global_news_text="",
        prompt_context=india_context(
            ticker=symbol,
            listing=listing_label(symbol),
            company_name=name,
            quotes_in_inr=quotes_in_inr(symbol),
            relative_strength=strength,
            tone=tone,
        ),
    )
    bundle.news_text = _news_text(bundle, caveat)
    bundle.global_news_text = _global_news_text(bundle, caveat)
    return bundle


def _news_text(bundle: IndiaBundle, caveat: str) -> str:
    return "\n\n".join(
        [
            f"India news for {bundle.ticker}. {caveat} StockTwits and Reddit were not called.",
            "Company headlines\n"
            + render_headlines(bundle.company_headlines, empty="No company headlines matched the window."),
            "Google News\n" + render_headlines(bundle.google_headlines, empty="No Google News items in the window."),
            bundle.announcements_text,
        ]
    )


def _global_news_text(bundle: IndiaBundle, caveat: str) -> str:
    return "\n\n".join(
        [
            f"Indian market headlines. {caveat} FRED is not used. "
            "Call get_macro_indicators for INR/USD, India VIX, Nifty, the sector index, Brent, the RBI note, and FII/DII.",
            render_headlines(bundle.market_headlines, empty="No market headlines in the window."),
        ]
    )


def _insider_text(screener_text: str) -> str:
    return (
        "US insider transactions are not used in India mode. "
        "The ownership input is the Screener.in shareholding pattern (promoter, FII, DII) when that page loaded.\n\n"
        + screener_text
    )


def _exchange(kind: str, symbol: str, as_of: date) -> tuple[Source, str, Source, str]:
    if kind == "nse":
        return fetch_nse(bare_symbol(symbol), as_of)
    if kind in {"bse", "index"}:
        flow_source, flow_text = fetch_flows(as_of)
        if kind == "bse":
            return (
                Source(
                    "nse_announcements",
                    "NSE corporate announcements",
                    "skipped",
                    "BSE listing. NSE announcements are not queried for a .BO symbol.",
                ),
                "NSE corporate announcements were not queried because this is a BSE symbol.",
                flow_source,
                flow_text,
            )
        return (
            Source(
                "nse_announcements",
                "NSE corporate announcements",
                "skipped",
                "Index symbol. No single-company announcement feed.",
            ),
            "NSE corporate announcements do not apply to an index.",
            flow_source,
            flow_text,
        )
    return (
        Source(
            "nse_announcements",
            "NSE corporate announcements",
            "skipped",
            "Symbol is not an NSE equity, so announcements were not queried.",
        ),
        "NSE corporate announcements were not queried for this symbol.",
        Source(
            "nse_fii_dii",
            "NSE FII/DII flows",
            "skipped",
            "India mode is on for a symbol that is not an Indian listing. FII/DII was not queried.",
        ),
        "NSE FII/DII flows were not queried for this symbol.",
    )


def _series(symbol: str, label: str, unit: str, as_of: date, mapped: tuple[str, str] | None):
    stock = load_series(symbol, label, unit, as_of)
    nifty = load_series("^NSEI", "Nifty 50", "points", as_of)
    vix = load_series("^INDIAVIX", "India VIX", "points", as_of)
    inr = load_series("INR=X", "INR/USD", "INR per USD", as_of)
    brent = load_series("BZ=F", "Brent crude", "USD/barrel", as_of)
    sector = None
    if mapped and mapped[0] != symbol:
        sector = load_series(mapped[0], mapped[1], "points", as_of)
    return stock, nifty, vix, inr, brent, sector


def _ordered(sources: list[Source]) -> list[Source]:
    order = [
        "yfinance_financials",
        "screener",
        "tradingview",
        "moneycontrol",
        "economic_times",
        "business_standard",
        "livemint",
        "google_news",
        "nse_announcements",
        "headline_tone",
        "inr_usd",
        "india_vix",
        "nifty",
        "sector_index",
        "brent",
        "rbi_note",
        "nse_fii_dii",
        "stocktwits",
        "reddit",
        "fred",
    ]
    rank = {source_id: index for index, source_id in enumerate(order)}
    return sorted(sources, key=lambda source: rank.get(source.id, 100))
