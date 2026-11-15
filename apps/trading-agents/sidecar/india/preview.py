"""Print India-mode sources for one ticker without calling an LLM.

Run from the sidecar directory:

    .venv/bin/python -m india.preview RELIANCE.NS
"""

from __future__ import annotations

import sys
from datetime import date

from india.bundle import collect


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    ticker = args[0] if args else "RELIANCE.NS"
    as_of = args[1] if len(args) > 1 else date.today().isoformat()
    bundle = collect(ticker, as_of)
    print(f"India preview {bundle.ticker} as of {bundle.as_of}")
    print(f"Company: {bundle.company_name or '—'}")
    for source in bundle.sources:
        print(f"[{source.status}] {source.label}: {source.detail}")
    sections = [
        ("FUNDAMENTALS", bundle.fundamentals_text),
        ("INCOME", bundle.income_text),
        ("BALANCE", bundle.balance_text),
        ("CASH FLOW", bundle.cashflow_text),
        ("NEWS", bundle.news_text),
        ("MACRO", bundle.macro_text),
        ("SENTIMENT INPUT", bundle.sentiment_text),
        ("TRADINGVIEW", bundle.tradingview_text),
        ("PROMPT", bundle.prompt_context),
    ]
    for title, body in sections:
        print(f"\n===== {title} =====")
        print(_excerpt(body))
    return 0


def _excerpt(body: str, limit: int = 1200) -> str:
    text = body.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


if __name__ == "__main__":
    raise SystemExit(main())
