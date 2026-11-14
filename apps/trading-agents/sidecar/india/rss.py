"""Indian market RSS and Google News RSS, filtered by name and date."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

from india.detect import bare_symbol, index_aliases, normalize_symbol
from india.http_client import http_get
from india.sources import Source, clip

FEEDS: tuple[tuple[str, str, str], ...] = (
    ("moneycontrol", "Moneycontrol markets", "https://www.moneycontrol.com/rss/marketreports.xml"),
    (
        "economic_times",
        "Economic Times markets",
        "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    ),
    ("business_standard", "Business Standard markets", "https://www.business-standard.com/rss/markets-106.rss"),
    ("livemint", "LiveMint markets", "https://www.livemint.com/rss/markets"),
)

_STOP = {
    "limited",
    "ltd",
    "inc",
    "corp",
    "corporation",
    "company",
    "industries",
    "industry",
    "the",
    "and",
    "of",
    "plc",
    "private",
}


@dataclass
class Headline:
    title: str
    link: str
    published: date | None
    source: str
    summary: str


def aliases_for(ticker: str, company_name: str | None) -> list[str]:
    """Names a headline must mention. The bare symbol always counts."""

    symbol = normalize_symbol(ticker)
    found: list[str] = []

    def add(value: str | None) -> None:
        cleaned = " ".join((value or "").split())
        if len(cleaned) < 3:
            return
        if cleaned.lower() not in {item.lower() for item in found}:
            found.append(cleaned)

    add(bare_symbol(symbol))
    for alias in index_aliases(symbol):
        add(alias)
    if company_name:
        stripped = re.sub(r"\b(limited|ltd|inc|corp|corporation|plc)\b\.?", "", company_name, flags=re.I)
        add(stripped)
        tokens = [
            token
            for token in re.split(r"[^A-Za-z0-9]+", company_name)
            if len(token) >= 5 and token.lower() not in _STOP
        ]
        if tokens:
            add(tokens[0])
    return found


def parse_rss(payload: bytes, source: str) -> list[Headline]:
    """RSS 2.0 or Atom items. A bad document returns an empty list."""

    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        return []
    headlines: list[Headline] = []
    for node in root.iter():
        kind = _local(node.tag)
        if kind not in {"item", "entry"}:
            continue
        title = _child_text(node, "title")
        if not title:
            continue
        link = _link(node)
        published = _published(node)
        summary = _child_text(node, "description") or _child_text(node, "summary") or ""
        headlines.append(
            Headline(
                title=_strip_markup(title),
                link=link,
                published=published,
                source=source,
                summary=_strip_markup(summary)[:400],
            )
        )
    return headlines


def parse_when(value: str | None) -> date | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return parsedate_to_datetime(text).date()
    except (TypeError, ValueError, IndexError, OverflowError):
        pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def in_window(item: Headline, start: date, end: date) -> bool:
    if item.published is None:
        return False
    return start <= item.published <= end


def matches_alias(item: Headline, aliases: list[str]) -> bool:
    haystack = f"{item.title} {item.summary}"
    for alias in aliases:
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])", haystack, re.I):
            return True
    return False


def select_headlines(
    items: list[Headline],
    *,
    aliases: list[str],
    start: date,
    end: date,
    require_alias: bool,
    limit: int,
) -> list[Headline]:
    chosen: list[Headline] = []
    for item in items:
        if not in_window(item, start, end):
            continue
        if require_alias and not matches_alias(item, aliases):
            continue
        chosen.append(item)
        if len(chosen) >= limit:
            break
    return chosen


def render_headlines(items: list[Headline], *, empty: str) -> str:
    if not items:
        return empty
    lines: list[str] = []
    for item in items:
        when = item.published.isoformat() if item.published else "date unknown"
        lines.append(f"- {when} | {item.source} | {item.title}")
        if item.link:
            lines.append(f"  {item.link}")
    return "\n".join(lines)


def fetch_feed(feed_id: str, label: str, url: str, *, timeout: float = 20) -> tuple[Source, list[Headline]]:
    result = http_get(url, headers={"Accept": "application/rss+xml, application/xml, text/xml, */*"}, timeout=timeout)
    if result.status != 200 or not result.body:
        return (
            Source(feed_id, label, "failed", clip(result.error or f"HTTP {result.status}")),
            [],
        )
    items = parse_rss(result.body, label)
    if not items and b"<" not in result.body[:200]:
        return Source(feed_id, label, "failed", "Response was not an RSS document."), []
    return Source(feed_id, label, "ok", f"Fetched {len(items)} items."), items


def google_news_url(aliases: list[str]) -> str:
    query = " OR ".join(f'"{alias}"' if " " in alias else alias for alias in aliases[:4]) or "NSE"
    return (
        "https://news.google.com/rss/search?q="
        + quote_plus(f"{query} when:30d")
        + "&hl=en-IN&gl=IN&ceid=IN:en"
    )


def fetch_google_news(aliases: list[str]) -> tuple[Source, list[Headline]]:
    url = google_news_url(aliases)
    return fetch_feed("google_news", "Google News RSS", url)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _child_text(node: ET.Element, name: str) -> str:
    for child in list(node):
        if _local(child.tag) == name:
            return "".join(child.itertext()).strip()
    return ""


def _link(node: ET.Element) -> str:
    for child in list(node):
        if _local(child.tag) != "link":
            continue
        href = child.attrib.get("href")
        if href:
            return href.strip()
        text = "".join(child.itertext()).strip()
        if text:
            return text
    return ""


def _published(node: ET.Element) -> date | None:
    for name in ("pubdate", "published", "updated", "date"):
        text = _child_text(node, name)
        if text:
            parsed = parse_when(text)
            if parsed:
                return parsed
    return None


def _strip_markup(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    return " ".join(text.split())
