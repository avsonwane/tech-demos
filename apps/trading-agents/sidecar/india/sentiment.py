"""Headline tone for India mode. StockTwits and Reddit are not called."""

from __future__ import annotations

import re

from india.rss import Headline, render_headlines

_POSITIVE = {
    "beat",
    "beats",
    "bullish",
    "gain",
    "gains",
    "growth",
    "jump",
    "jumps",
    "profit",
    "profits",
    "rally",
    "rallies",
    "record",
    "rise",
    "rises",
    "rose",
    "strong",
    "surge",
    "surges",
    "upgrade",
    "upgrades",
}
_NEGATIVE = {
    "bearish",
    "cut",
    "cuts",
    "decline",
    "declines",
    "downgrade",
    "downgrades",
    "drop",
    "drops",
    "fall",
    "falls",
    "fell",
    "fraud",
    "loss",
    "losses",
    "miss",
    "misses",
    "plunge",
    "plunges",
    "slump",
    "slumps",
    "weak",
}


def score_title(title: str) -> int:
    words = re.findall(r"[a-z]+", title.lower())
    return sum(word in _POSITIVE for word in words) - sum(word in _NEGATIVE for word in words)


def tone_summary(headlines: list[Headline]) -> str:
    """A count of headline words. It is an input to the analyst, not a rating."""

    if not headlines:
        return "No headlines to score, so the tone is unavailable."
    scores = [score_title(item.title) for item in headlines]
    positive = sum(score > 0 for score in scores)
    negative = sum(score < 0 for score in scores)
    neutral = len(scores) - positive - negative
    net = sum(scores)
    if net >= 2 and positive > negative:
        band = "positive"
    elif net <= -2 and negative > positive:
        band = "negative"
    elif positive and negative:
        band = "mixed"
    else:
        band = "neutral"
    return (
        f"{band} on {len(headlines)} headlines "
        f"({positive} positive, {negative} negative, {neutral} neutral, net {net:+d}). "
        "This is a word count, not a forecast."
    )


def sentiment_input(
    *,
    ticker: str,
    start: str,
    end: str,
    tone: str,
    company: list[Headline],
    google: list[Headline],
) -> str:
    return "\n\n".join(
        [
            (
                f"Sentiment inputs for {ticker} from {start} to {end}. "
                "StockTwits and Reddit are not used in India mode. "
                "The tone line is a lexicon count of the headlines below."
            ),
            f"Tone: {tone}",
            "Indian market RSS, company or index matches\n"
            + render_headlines(company, empty="No matching Indian-market headlines in the window."),
            "Google News RSS\n" + render_headlines(google, empty="No Google News items in the window."),
        ]
    )


def sentiment_system_message(*, ticker: str, start: str, end: str, block: str) -> str:
    """Same report fields the library's sentiment analyst already asks for."""

    return f"""You are a financial market sentiment analyst. Produce a sentiment report for {ticker} from {start} to {end}.

India mode does not use StockTwits or Reddit. The only sentiment inputs are Indian news headlines and Google News RSS, already collected below, plus a lexicon tone count. Do not invent social posts, cashtags, or subreddit threads. If a block says nothing matched, say the source was quiet.

<start_of_india_sentiment>
{block}
<end_of_india_sentiment>

Read the headlines as events or opinions as written. Separate a filing or a results headline from a columnist's adjective. The lexicon tone is a word count of titles, so a single loud word can move it. Say when the count and the headlines disagree.

Fill these fields:

- **overall_band**: Exactly one of Bullish / Mildly Bullish / Neutral / Mixed / Mildly Bearish / Bearish. Use Mixed when headlines disagree. Use Neutral when the sources are quiet.
- **overall_score**: A number from 0 (maximally bearish) to 10 (maximally bullish). 5 is neutral. Keep it consistent with overall_band.
- **confidence**: low / medium / high, based on how many headlines actually matched.
- **narrative**: What the headlines say, what the tone count says, where they differ, and which catalyst or risk shows up more than once. Name the source of each claim.
"""
