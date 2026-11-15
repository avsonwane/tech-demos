"""NSE public JSON: corporate announcements and FII/DII flows.

One session, one call per endpoint. A block or a timeout is skipped.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from india.http_client import HttpResult, build_opener, http_get, timed_out
from india.sources import Source, clip

_HOME = "https://www.nseindia.com/"
_ANNOUNCEMENTS = "https://www.nseindia.com/api/corporate-announcements"
_FII = "https://www.nseindia.com/api/fiidiiTradeReact"
_HTML_HEADERS = {
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}
_API_HEADERS = {
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-announcements",
}


def fetch_nse(symbol: str, as_of: date, *, lookback_days: int = 30) -> tuple[Source, str, Source, str]:
    """Announcements for ``symbol`` and the market-wide FII/DII print."""

    start = as_of - timedelta(days=lookback_days)
    opener = _session()
    announcements = _announcements(opener, symbol, start, as_of)
    flows = _flows(opener, as_of)
    return announcements[0], announcements[1], flows[0], flows[1]


def fetch_flows(as_of: date) -> tuple[Source, str]:
    """Market-wide FII/DII only. One session, one API call."""

    return _flows(_session(), as_of)


def _session():
    opener = build_opener()
    http_get(_HOME, headers=_HTML_HEADERS, timeout=15, opener=opener)
    return opener


def parse_announcements(payload: object, *, symbol: str, start: date, end: date, limit: int = 12) -> list[dict]:
    if not isinstance(payload, list):
        return []
    rows: list[tuple[date, dict]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        when = _nse_date(str(item.get("an_dt") or item.get("dt") or ""))
        if when is None or when < start or when > end:
            continue
        item_symbol = str(item.get("symbol") or symbol).upper()
        if item_symbol != symbol.upper():
            continue
        rows.append((when, item))
    rows.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _when, item in rows[:limit]]


def render_announcements(rows: list[dict]) -> str:
    if not rows:
        return "NSE corporate announcements: none in the window."
    lines = ["Source: NSE corporate announcements JSON (nseindia.com)."]
    for item in rows:
        when = str(item.get("an_dt") or "")
        desc = " ".join(str(item.get("desc") or "").split())
        text = " ".join(str(item.get("attchmntText") or "").split())
        if len(text) > 280:
            text = text[:279].rstrip() + "…"
        lines.append(f"- {when} | {desc}")
        if text:
            lines.append(f"  {text}")
    return "\n".join(lines)


def parse_fii_dii(payload: object, *, as_of: date) -> list[dict]:
    if not isinstance(payload, list):
        return []
    rows = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        when = _nse_date(str(item.get("date") or ""))
        if when is None or when > as_of:
            continue
        rows.append(item)
    return rows


def render_fii_dii(rows: list[dict]) -> str:
    if not rows:
        return "NSE FII/DII flows: no rows on or before the as-of date."
    lines = [
        "Source: NSE FII/DII JSON (fiidiiTradeReact). Values are the exchange's own figures, in ₹ crore."
    ]
    for item in rows:
        lines.append(
            f"- {item.get('date')} | {item.get('category')} | "
            f"buy {item.get('buyValue')} | sell {item.get('sellValue')} | net {item.get('netValue')}"
        )
    return "\n".join(lines)


def _announcements(opener, symbol: str, start: date, end: date) -> tuple[Source, str]:
    url = (
        f"{_ANNOUNCEMENTS}?index=equities&symbol={symbol}"
        f"&from_date={start.strftime('%d-%m-%Y')}&to_date={end.strftime('%d-%m-%Y')}"
    )
    result = http_get(url, headers=_API_HEADERS, timeout=25, opener=opener)
    skipped = _skip_source("nse_announcements", "NSE corporate announcements", result)
    if skipped is not None:
        return skipped, "NSE corporate announcements were skipped. The public JSON did not answer."
    payload = _json_or_none(result)
    if payload is None:
        return (
            Source("nse_announcements", "NSE corporate announcements", "failed", "Response was not JSON."),
            "NSE corporate announcements came back as something other than JSON.",
        )
    rows = parse_announcements(payload, symbol=symbol, start=start, end=end)
    detail = f"{len(rows)} announcements from {start.isoformat()} to {end.isoformat()}."
    return Source("nse_announcements", "NSE corporate announcements", "ok", detail), render_announcements(rows)


def _flows(opener, as_of: date) -> tuple[Source, str]:
    result = http_get(_FII, headers=_API_HEADERS, timeout=20, opener=opener)
    skipped = _skip_source("nse_fii_dii", "NSE FII/DII flows", result)
    if skipped is not None:
        return skipped, "NSE FII/DII flows were skipped. The public JSON did not answer."
    payload = _json_or_none(result)
    if payload is None:
        return (
            Source("nse_fii_dii", "NSE FII/DII flows", "failed", "Response was not JSON."),
            "NSE FII/DII flows came back as something other than JSON.",
        )
    rows = parse_fii_dii(payload, as_of=as_of)
    detail = f"{len(rows)} rows on or before {as_of.isoformat()}."
    if rows:
        latest = rows[0]
        detail = f"{latest.get('date')}: {len(rows)} category rows."
    return Source("nse_fii_dii", "NSE FII/DII flows", "ok", detail), render_fii_dii(rows)


def _skip_source(source_id: str, label: str, result: HttpResult) -> Source | None:
    if result.blocked or timed_out(result):
        reason = result.error or "no response"
        return Source(
            source_id,
            label,
            "skipped",
            f"NSE did not serve this JSON ({reason}). Skipped, not retried.",
        )
    if result.status != 200 or not result.body:
        return Source(source_id, label, "failed", clip(result.error or f"HTTP {result.status}"))
    return None


def _json_or_none(result: HttpResult) -> object | None:
    body = result.body.lstrip()
    if not body.startswith(b"{") and not body.startswith(b"["):
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


def _nse_date(value: str) -> date | None:
    head = value.strip().split(" ")[0]
    if not head:
        return None
    for pattern in ("%d-%b-%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(head, pattern).date()
        except ValueError:
            continue
    return None
