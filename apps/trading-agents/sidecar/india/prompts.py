"""India note appended to the instrument context every agent already reads."""

from __future__ import annotations


def india_context(
    *,
    ticker: str,
    listing: str,
    company_name: str | None,
    quotes_in_inr: bool,
    relative_strength: str,
    tone: str,
) -> str:
    """Market rules for an India-mode run. Tools still have to supply the numbers."""

    name = company_name or ticker
    if quotes_in_inr:
        price_line = "Quote every price in Indian rupees (₹). Do not convert the print into dollars."
    else:
        price_line = (
            "India mode is on for a symbol that is not an NSE/BSE listing. "
            "Keep the currency the price tool reports. Do not relabel a non-rupee price as ₹."
        )
    return (
        f"India market context for {name} ({ticker}), {listing}. {price_line} "
        "NSE and BSE cash stocks trade inside a circuit band, commonly 5%, 10%, or 20% "
        "(some names 2%). A print locked at the band is a halt, not a fundamental. "
        "F&O monthly stock expiry and weekly index expiry pull volume and can pin the price "
        "into that session. Treat a move that lands on expiry as a positioning effect until "
        "the cash trend confirms it. Results season clusters in the weeks after each quarter, "
        "roughly the middle of April, July, October, and January. "
        "Weigh promoter pledging only when a source states a number, and weigh changes in "
        "promoter, FII, and DII shareholding. Do not invent a pledge figure. "
        "Judge the name against Nifty 50 and its sector index, not against the S&P 500. "
        f"{relative_strength} "
        "Do not use SEC EDGAR, StockTwits, Reddit, or FRED for this run. Those sources are "
        "skipped. A macro call such as cpi or fed_funds_rate returns the India set "
        "(INR/USD, India VIX, Nifty 50, the sector index, Brent, the static RBI repo and CPI "
        "note, and NSE FII/DII flows) instead of FRED. "
        "If a source says it failed, was skipped, or was blocked, say that and continue. "
        "A block titled TradingView technicals (supplementary) is an optional extra for the "
        "market analyst. It does not replace Yahoo Finance prices or indicators, Screener.in, "
        "the Indian news feeds, NSE announcements, or this macro set. "
        f"Headline tone from Indian news, lexicon count only: {tone}"
    )
