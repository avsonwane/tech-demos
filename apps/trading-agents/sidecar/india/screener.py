"""Screener.in company page: ratios, quarterly results, shareholding. No login."""

from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape

from india.http_client import http_get
from india.sources import Source, clip

_HOLDING_LABELS = ("promoter", "fii", "dii", "public", "government", "pledge")


@dataclass
class ScreenerPage:
    title: str | None
    ratios: list[tuple[str, str]]
    quarterly_columns: list[str]
    quarterly_rows: list[tuple[str, list[str]]]
    holding_columns: list[str]
    holding_rows: list[tuple[str, list[str]]]


def parse_screener(html: str) -> ScreenerPage:
    title = _title(html)
    ratios = _top_ratios(html)
    q_columns, q_rows = _table_after(html, "quarters")
    h_columns, h_rows = _table_after(html, "shareholding")
    q_columns, q_rows = _tail(q_columns, q_rows, 4)
    h_columns, h_rows = _tail(h_columns, _holding_rows(h_rows), 4)
    return ScreenerPage(title, ratios, q_columns, q_rows, h_columns, h_rows)


def page_is_useful(page: ScreenerPage) -> bool:
    return bool(page.ratios or page.quarterly_rows or page.holding_rows)


def render_screener(page: ScreenerPage, symbol: str) -> str:
    """Text the fundamentals tools can paste, with the source named."""

    parts = [
        f"Source: Screener.in public company page for {symbol} (no login). "
        "Figures are whatever the page showed at fetch time, not a point-in-time filing."
    ]
    if page.title:
        parts.append(f"Page title: {page.title}")
    if page.ratios:
        parts.append("Top ratios\n" + "\n".join(f"- {name}: {value}" for name, value in page.ratios))
    else:
        parts.append("Top ratios: not found on the page.")
    parts.append(format_table("Quarterly results", page.quarterly_columns, page.quarterly_rows))
    parts.append(format_table("Shareholding pattern (promoter / FII / DII)", page.holding_columns, page.holding_rows))
    if not _has_pledge(page.holding_rows):
        parts.append(
            "Promoter pledge: the public page did not include a pledge figure. Do not invent one."
        )
    return "\n\n".join(parts)


def format_table(title: str, columns: list[str], rows: list[tuple[str, list[str]]]) -> str:
    if not rows:
        return f"{title}: no rows."
    header = " | ".join(["Item", *columns])
    lines = [title, header]
    width = len(columns)
    for label, values in rows:
        padded = list(values) + ["—"] * max(0, width - len(values))
        lines.append(" | ".join([label, *padded[:width]]))
    return "\n".join(lines)


def fetch_screener(symbol: str) -> tuple[Source, str]:
    """Try the consolidated page, then the standalone page. One GET each, then stop."""

    errors: list[str] = []
    for url in (
        f"https://www.screener.in/company/{symbol}/consolidated/",
        f"https://www.screener.in/company/{symbol}/",
    ):
        result = http_get(url, headers={"Accept": "text/html"}, timeout=25)
        if result.blocked:
            return (
                Source("screener", "Screener.in", "skipped", f"Screener.in blocked the fetch ({result.error})."),
                f"Screener.in was blocked ({result.error}). Shareholding and its ratios are unavailable.",
            )
        if result.status != 200 or not result.body:
            errors.append(result.error or f"HTTP {result.status}")
            continue
        html = result.body.decode("utf-8", "replace")
        page = parse_screener(html)
        if page_is_useful(page):
            detail = (
                f"{len(page.ratios)} ratios, {len(page.quarterly_rows)} quarterly rows, "
                f"{len(page.holding_rows)} shareholding rows."
            )
            return Source("screener", "Screener.in", "ok", detail), render_screener(page, symbol)
        errors.append("page did not contain ratios, quarterly results, or shareholding")
    return (
        Source("screener", "Screener.in", "failed", clip("; ".join(errors) or "no usable page")),
        "Screener.in did not return a usable company page. Ratios and shareholding from that source are unavailable.",
    )


def _title(html: str) -> str | None:
    match = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
    if not match:
        return None
    title = _clean(match.group(1))
    title = re.sub(r"\s+share price.*$", "", title, flags=re.I)
    return title or None


def _top_ratios(html: str) -> list[tuple[str, str]]:
    match = re.search(r'<ul id="top-ratios">(.*?)</ul>', html, re.S | re.I)
    if not match:
        return []
    pairs: list[tuple[str, str]] = []
    for name, value in re.findall(
        r'<span class="name">\s*(.*?)\s*</span>.*?<span class="[^"]*value[^"]*">(.*?)</span>',
        match.group(1),
        re.S | re.I,
    ):
        label = _clean(name)
        amount = _clean(value)
        if label and amount:
            pairs.append((label, amount))
    return pairs


def _table_after(html: str, element_id: str) -> tuple[list[str], list[tuple[str, list[str]]]]:
    marker = html.find(f'id="{element_id}"')
    if marker < 0:
        return [], []
    start = html.find("<table", marker)
    end = html.find("</table>", start)
    if start < 0 or end < 0:
        return [], []
    rows: list[list[str]] = []
    for row_html in re.findall(r"<tr\b[\s\S]*?</tr>", html[start:end], re.I):
        cells = [_clean(cell) for cell in re.findall(r"<t[hd][^>]*>([\s\S]*?)</t[hd]>", row_html, re.I)]
        cells = [cell for cell in cells if cell]
        if cells:
            rows.append(cells)
    if len(rows) < 2:
        return [], []
    columns = rows[0]
    body = [(cells[0], cells[1:]) for cells in rows[1:] if cells]
    return columns, body


def _holding_rows(rows: list[tuple[str, list[str]]]) -> list[tuple[str, list[str]]]:
    picked = [row for row in rows if any(label in row[0].lower() for label in _HOLDING_LABELS)]
    return picked or rows[:6]


def _has_pledge(rows: list[tuple[str, list[str]]]) -> bool:
    return any("pledge" in label.lower() for label, _values in rows)


def _tail(
    columns: list[str], rows: list[tuple[str, list[str]]], count: int
) -> tuple[list[str], list[tuple[str, list[str]]]]:
    if len(columns) <= count:
        return columns, rows
    kept = columns[-count:]
    return kept, [(label, values[-count:]) for label, values in rows]


def _clean(fragment: str) -> str:
    text = unescape(fragment)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("\xa0", " ")
    text = " ".join(text.split())
    return text.removesuffix("+").strip()
