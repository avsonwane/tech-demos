"""India-mode parsers and the TradingView add-on. Network is mocked."""

import json
from datetime import date

from fastapi.testclient import TestClient

from app import app
from india.bundle import _ordered
from india.detect import is_india_symbol
from india.http_client import HttpResult
from india.nse import fetch_nse, parse_announcements
from india.prompts import india_context
from india.rss import parse_rss, select_headlines
from india.screener import parse_screener
from india.sources import Source
from india.statements import _ratio_value
from india.tradingview import fetch_tradingview, tradingview_symbol


def test_dividend_yield_stays_a_percent_when_yahoo_already_scaled_it():
    assert _ratio_value("dividendYield", 0.45, "INR") == "0.45%"
    assert _ratio_value("dividendYield", 0.0045, "INR") == "0.45%"
    assert _ratio_value("returnOnEquity", 0.0876, "INR") == "8.76%"


def test_india_symbols():
    assert is_india_symbol("reliance.ns")
    assert is_india_symbol("TCS.BO")
    assert is_india_symbol("^NSEI")
    assert is_india_symbol("^BSESN")
    assert is_india_symbol("^NSEBANK")
    assert not is_india_symbol("NVDA")
    assert tradingview_symbol("RELIANCE.NS") == ("NSE", "RELIANCE", "NSE:RELIANCE")
    assert tradingview_symbol("tcs.bo") == ("BSE", "TCS", "BSE:TCS")
    assert tradingview_symbol("^NSEI") is None


def test_rss_keeps_a_matching_headline_inside_the_window():
    payload = b"""<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <item>
        <title>Reliance Industries raises refining margin</title>
        <link>https://example.test/reliance</link>
        <pubDate>Thu, 12 Nov 2026 10:00:00 GMT</pubDate>
      </item>
      <item>
        <title>Unrelated steel note</title>
        <link>https://example.test/steel</link>
        <pubDate>Thu, 12 Nov 2026 10:00:00 GMT</pubDate>
      </item>
      <item>
        <title>Reliance Industries old item</title>
        <link>https://example.test/old</link>
        <pubDate>Thu, 01 Jan 2026 10:00:00 GMT</pubDate>
      </item>
    </channel></rss>"""
    items = parse_rss(payload, "Economic Times markets")
    chosen = select_headlines(
        items,
        aliases=["Reliance Industries", "RELIANCE"],
        start=date(2026, 11, 1),
        end=date(2026, 11, 14),
        require_alias=True,
        limit=10,
    )
    assert [item.title for item in chosen] == ["Reliance Industries raises refining margin"]


def test_screener_parser_reads_ratios_results_and_shareholding():
    html = """
    <title>Reliance Industries Ltd share price</title>
    <ul id="top-ratios">
      <li><span class="name">Stock P/E</span><span class="nowrap value">₹ <span class="number">24.1</span></span></li>
      <li><span class="name">ROE</span><span class="value">9%</span></li>
    </ul>
    <section id="quarters"><table>
      <tr><th></th><th>Jun 2026</th><th>Sep 2026</th></tr>
      <tr><td>Sales</td><td>309,468</td><td>330,601</td></tr>
    </table></section>
    <section id="shareholding"><table>
      <tr><th></th><th>Jun 2026</th><th>Sep 2026</th></tr>
      <tr><td>Promoters</td><td>50.48%</td><td>50.44%</td></tr>
      <tr><td>FIIs</td><td>17.19%</td><td>16.67%</td></tr>
      <tr><td>DIIs</td><td>21.10%</td><td>21.62%</td></tr>
    </table></section>
    """
    page = parse_screener(html)
    assert page.ratios[0] == ("Stock P/E", "₹ 24.1")
    assert page.quarterly_rows[0][0] == "Sales"
    assert page.quarterly_rows[0][1][-1] == "330,601"
    labels = [label for label, _values in page.holding_rows]
    assert "Promoters" in labels and "FIIs" in labels and "DIIs" in labels


def test_nse_announcements_filter_symbol_and_date():
    payload = [
        {"symbol": "RELIANCE", "an_dt": "13-Nov-2026 18:25:01", "desc": "Investor meet", "attchmntText": "Singapore"},
        {"symbol": "TCS", "an_dt": "13-Nov-2026 18:25:01", "desc": "Other", "attchmntText": "no"},
        {"symbol": "RELIANCE", "an_dt": "01-Jan-2026 10:00:00", "desc": "Old", "attchmntText": "old"},
    ]
    rows = parse_announcements(payload, symbol="RELIANCE", start=date(2026, 10, 1), end=date(2026, 11, 14))
    assert len(rows) == 1
    assert rows[0]["desc"] == "Investor meet"


def test_nse_block_is_not_retried(monkeypatch):
    calls = []

    def fake(url, **_kwargs):
        calls.append(url)
        return HttpResult(status=403, body=b"", error="HTTP 403", blocked=True, url=url)

    monkeypatch.setattr("india.nse.http_get", fake)
    source, _text, flows, _flow_text = fetch_nse("RELIANCE", date(2026, 11, 14))
    assert source.status == "skipped"
    assert "not retried" in source.detail.lower() or "Skipped" in source.detail
    assert flows.status == "skipped"
    announcement_calls = [url for url in calls if "corporate-announcements" in url]
    assert len(announcement_calls) == 1


def test_tradingview_summary_is_supplementary():
    def loader(exchange, symbol, interval):
        assert (exchange, symbol) == ("NSE", "RELIANCE")
        return {
            "interval": interval,
            "summary": {"RECOMMENDATION": "BUY" if interval == "1d" else "NEUTRAL", "BUY": 15, "SELL": 5, "NEUTRAL": 6},
            "oscillators": {"RECOMMENDATION": "NEUTRAL", "COMPUTE": {"RSI": "NEUTRAL", "MACD": "SELL", "ADX": "BUY"}},
            "moving_averages": {"RECOMMENDATION": "BUY", "COMPUTE": {"EMA20": "BUY", "SMA50": "BUY"}},
            "indicators": {"RSI": 58.2, "MACD.macd": 1.5, "MACD.signal": 1.1, "ADX": 22.4, "ADX+DI": 20.0, "ADX-DI": 14.0},
        }

    source, text = fetch_tradingview("RELIANCE.NS", loader=loader)
    assert source.status == "ok"
    assert source.id == "tradingview"
    assert text.startswith("TradingView technicals (supplementary)")
    assert "does not replace Yahoo Finance" in text
    assert "RSI 58.20" in text
    assert "MACD" in text and "ADX" in text
    assert "1D summary: BUY" in text
    assert "1W summary: NEUTRAL" in text


def test_tradingview_timeout_is_skipped_without_a_retry():
    calls = []

    def loader(_exchange, _symbol, interval):
        calls.append(interval)
        raise TimeoutError("timed out")

    source, text = fetch_tradingview("RELIANCE.NS", loader=loader)
    assert source.status == "skipped"
    assert calls == ["1d", "1W"]
    assert "TradingView technicals (supplementary)" in text
    assert "Yahoo Finance prices and indicators are unchanged" in text


def test_tradingview_forbidden_is_blocked():
    def loader(_exchange, _symbol, _interval):
        raise RuntimeError("HTTP 403 Forbidden")

    source, _text = fetch_tradingview("TCS.BO", loader=loader)
    assert source.status == "blocked"
    assert "not retried" in source.detail.lower()


def test_tradingview_does_not_replace_the_other_source_rows():
    ordered = _ordered(
        [
            Source("tradingview", "TradingView technicals", "ok", "1D BUY"),
            Source("yfinance_financials", "Yahoo Finance financials", "ok", "rows"),
            Source("screener", "Screener.in", "ok", "ratios"),
            Source("nse_announcements", "NSE corporate announcements", "ok", "2"),
            Source("moneycontrol", "Moneycontrol markets", "ok", "feed"),
        ]
    )
    ids = [source.id for source in ordered]
    assert "yfinance_financials" in ids and "tradingview" in ids and "screener" in ids
    assert ids.index("yfinance_financials") < ids.index("tradingview")


def test_india_prompt_names_the_market_rules_and_the_tradingview_add_on():
    text = india_context(
        ticker="RELIANCE.NS",
        listing="NSE listing, Yahoo suffix .NS",
        company_name="Reliance Industries Limited",
        quotes_in_inr=True,
        relative_strength="Relative strength: flat versus Nifty 50.",
        tone="mixed on 4 headlines.",
    )
    for phrase in (
        "₹",
        "circuit",
        "expiry",
        "Results season",
        "promoter",
        "FII",
        "DII",
        "Nifty",
        "sector",
        "TradingView technicals (supplementary)",
        "does not replace Yahoo Finance",
    ):
        assert phrase in text


def test_india_replay_shows_the_sources_panel_and_rupees(monkeypatch):
    monkeypatch.setenv("TRADING_AGENTS_REPLAY_DELAY", "0")
    client = TestClient(app)
    response = client.post(
        "/api/run",
        json={
            "ticker": "RELIANCE.NS",
            "as_of": "2026-11-13",
            "provider": "xai",
            "quick_model": "grok-4.6",
            "deep_model": "grok-4.6",
            "debate_rounds": 1,
            "mode": "replay",
            "india_mode": True,
        },
    )
    assert response.status_code == 200
    assert "event: sources" in response.text
    assert "TradingView technicals" in response.text
    assert "₹" in response.text
    assert "Illustrative India-mode transcript" in response.text
    payloads = []
    for block in response.text.split("\n\n"):
        for line in block.splitlines():
            if line.startswith("data:"):
                payloads.append(json.loads(line[5:]))
    meta = next(item for item in payloads if item.get("mode") == "replay")
    assert meta["currency"] == "INR"
    assert meta["india_mode"] is True
    sources = next(item["sources"] for item in payloads if "sources" in item)
    ids = [row["id"] for row in sources]
    assert "yfinance_financials" in ids
    assert "screener" in ids
    assert "tradingview" in ids
    assert "nse_announcements" in ids
