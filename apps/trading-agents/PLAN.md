# TradingAgents paper desk

## Goal

A single-user page that runs the TradingAgents research graph for one Yahoo Finance ticker and shows each stage as it arrives, ending in a paper BUY, HOLD, or SELL.

## Single-user MVP

- Form: ticker (NVDA, RELIANCE.NS, ^NSEI), as-of date (default today, not in the future), LLM provider and quick/deep models, debate rounds. Run starts the graph.
- The page fills a vertical timeline: market/technical, sentiment, news, and fundamentals reports; bull and bear turns; the research manager’s plan; the trader’s proposal; aggressive, conservative, and neutral risk turns; the portfolio manager’s decision and rationale.
- Paper only. A visible line reads “Research/simulation only, not financial advice.” No broker, order, or portfolio controls.
- `bun run dev` creates the Python env on first run if needed, then starts Vite and the FastAPI sidecar. The browser talks to `/api` through the Vite proxy.
- Keys come from the environment (`XAI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`). The form defaults to xAI / Grok 4.6, then OpenAI’s library defaults when that is the provider. Nothing secret is committed.
- Data vendors stay on the library default: Yahoo Finance for prices, indicators, and news; SEC EDGAR then Yahoo for statements; FRED for macro; Polymarket for prediction markets. FRED returns an unavailable note when `FRED_API_KEY` is unset and the run continues. Alpha Vantage is not on the chain, so no paid market-data key is required. All four analysts stay selected.
- Replay: `sidecar/sample_run.json` is an illustrative transcript, labeled as such, because this environment has no LLM key. With no key for the chosen provider, Run plays that transcript and the page shows a replay banner. A Replay sample button does the same when a key is present.

## Out of scope

Live trading, brokers, orders, portfolios, backtests, accounts, and saving runs beyond the shipped sample and the library’s own on-disk log under the sidecar cache.

## Vertical slices

1. Scaffold Vite and the sidecar so `bun run dev` serves a page that can call `/api/health`.
2. Play the sample transcript into the timeline, including the banner and the final decision.
3. Wire a live `TradingAgentsGraph` run that streams the same events over SSE.

## Stack

- **Vite + React + TypeScript** via `bunx create-vite` (`react-ts`, `--no-immediate`). One screen; a Next.js app would only proxy the Python graph.
- **shadcn/ui preset Sera** (`--preset sera --base radix`). Sera is the minimalist editorial preset. Components added as needed: button, card, input, label, select, badge, separator.
- **FastAPI + uvicorn**, SSE (`text/event-stream`). TradingAgents is Python and LangGraph. `propagate` returns only the final pair; with `debug=True` it iterates `stream_run`. The sidecar does the same, then `record_decision`, so stages can render before the run ends.
- **TradingAgents 0.7.1** pinned to commit `9fa1196fffbcfd9de5146d2dd2869df84ab99838` (Apache-2.0) via `uv pip install` from git. Not on PyPI. `TradingAgentsGraph` is constructed from `DEFAULT_CONFIG.copy()` with provider, models, and `max_debate_rounds` / `max_risk_discuss_rounds` overridden from the form. Checkpointing stays off.
- **uv + Python 3.13** (library README) and `requirements.txt`. `bun run dev` creates `sidecar/.venv` when imports are missing. Cache, logs, and the memory file stay under `sidecar/.run-data` (gitignored).
- **`bunfig.toml`** with `[install] minimumReleaseAge = 259200`, written before `bun install`.

## Stage events

A pure function diffs graph chunks into UI events. Analyst fields: `market_report`, `sentiment_report` (the social analyst), `news_report`, `fundamentals_report`. Debate turns are slices of `investment_debate_state.history` split on `Bull Analyst:` / `Bear Analyst:`. Risk turns split `risk_debate_state.history` on `Aggressive Analyst:`, `Conservative Analyst:`, and `Neutral Analyst:`. `investment_plan`, `trader_investment_plan`, and `final_trade_decision` are their own steps. The signal is `run_rating` (Buy, Overweight, Hold, Underweight, Sell, or REVIEW). The badge collapses Buy/Overweight to BUY, Hold to HOLD, Underweight/Sell to SELL, and leaves REVIEW as REVIEW.

## Layout

```
apps/trading-agents/
  src/features/desk/     page, timeline, SSE client
  src/components/ui/     shadcn components actually used
  scripts/dev.ts         sidecar + Vite
  sidecar/app.py         FastAPI
  sidecar/stages.py      chunk diff and rating collapse
  sidecar/runner.py      TradingAgentsGraph stream
  sidecar/sample_run.json
  sidecar/tests/
```

## Testing and hooks

Pytest covers the chunk diff, the rating collapse, and that the sample transcript contains every phase and the sample label. No test calls an LLM or the network. No git hooks: the repo has no hook runner, and a per-app hook would live outside this app.

## Deferred

- Streaming token-by-token inside a stage. Stages arrive when the graph files them.
- Choosing analysts or data vendors in the UI.
- Separate research-round and risk-round controls. One rounds value sets both.
- Checkpoint resume, memory browsing, and saved user runs.
- A repo-level formatter hook.

## India mode

### Goal

When the desk runs an NSE or BSE name, the analysts see Indian prices, filings, news, and macro instead of the US defaults that come back empty or blocked.

### Single-user MVP

- A switch on the run form. It turns on by itself for symbols ending in `.NS` or `.BO`, and for `^NSEI`, `^BSESN`, and `^NSEBANK`. The user can flip it. Prices for that run are labeled in ₹.
- Fundamentals come from Yahoo Finance quarterly income, balance sheet, and cash flow plus the ratio block on the ticker, and from the public Screener.in company page (top ratios, quarterly results, promoter / FII / DII shareholding) when that page loads without a login. Each block names its source. A missing page or an empty table is a failed row, and the run continues.
- News comes from Moneycontrol, Economic Times markets, Business Standard markets, and LiveMint markets RSS, plus Google News RSS, kept only when the headline matches the company and the as-of window. NSE corporate announcements use one cookie-warmed session and the public JSON. A 403, 401, 429, or timeout is skipped with a note and is not retried.
- Macro replaces FRED: INR/USD (`INR=X`), India VIX (`^INDIAVIX`), Nifty 50, the mapped sector index, and Brent (`BZ=F`), plus a dated static note for the RBI repo rate and CPI. NSE FII/DII daily flows use the same public JSON session. If that call is blocked, it is skipped with a note.
- Sentiment does not call StockTwits or Reddit. The input is the Indian headlines and a counted headline tone.
- The India note is appended to `instrument_context`, which the analyst, researcher, trader, and risk prompts already include: NSE/BSE listing, ₹ prices, circuit bands, weekly and monthly F&O expiry, results season, promoter pledging and holding changes, and Nifty or sector relative strength. Vendor methods are registered on the library router under the name `india`. The library is not forked.
- The run shows a sources panel: one row per feed with ok, failed, skipped, or blocked. Replay of `sample_run_india.json` shows the same panel and is labeled as an illustrative India transcript. The US sample, the provider list, and `ANTHROPIC_WORKSPACE_ID` stay as they are.
- TradingView is an extra row, not a replacement. `tradingview-ta` (the technical-summary library behind the MIT `tradingview-mcp-server`) reads the public screener scan for `NSE:SYMBOL` or `BSE:SYMBOL` on the 1D and 1W frames: the Buy/Sell/Neutral summary, oscillator and moving-average counts, and RSI, MACD, and ADX. The block is labeled `TradingView technicals (supplementary)` and is appended to the instrument context the market analyst already reads. A timeout is skipped. A 401, 403, or 429 is blocked. No chart websocket.

### Out of scope

Live LLM calls in this environment (no key). Broker or F&O order logic. A pledge figure that is not on the public page. Fighting NSE when the JSON is blocked. Paid Indian data terminals. Editing any other app.

### Vertical slices

1. Pure parsers and the sources model, with mocked HTTP, so a RELIANCE page, an RSS item, and an NSE payload become labeled text.
2. A collector that hits the real sources once per run and a preview command that prints each row without an LLM.
3. The form switch, the ₹ label, the sources panel, and the India replay sample.

### Stack

- **Existing Vite + React + shadcn desk.** The switch is a `role="switch"` control in the same form. No new frontend framework.
- **Stdlib** `urllib`, `xml.etree`, and `html.parser` for RSS, Screener, and NSE. The pages are simple enough that feedparser and BeautifulSoup would only add installs.
- **yfinance**, already installed with TradingAgents, for `.NS` / `.BO` statements and the India macro series.
- **A sidecar vendor name `india`** registered in `VENDOR_METHODS` at runtime, selected through `data_vendors` for fundamentals, news, and macro. Sentiment is a wrapper around the library’s system-message builder so StockTwits and Reddit are not called while that bundle is bound.
- **`sidecar/india/rbi_note.py`** for the repo rate and CPI, because no free keyless API is wired. The note is dated and says it is static.
- **`tradingview-ta`** for an optional technical summary. It is the library `tradingview-mcp-server` already depends on, called in-process. Yahoo, Screener.in, the RSS feeds, and NSE stay on their own rows.

### Deferred for India mode

- Point-in-time Screener or NSE history for a backtest. The public pages are the latest page, and the run says so.
- Promoter pledge when the public Screener page does not print it.
- Intraday circuit-band lookups and the exact expiry calendar.
- Translating reports into Hindi. Output language stays English.
