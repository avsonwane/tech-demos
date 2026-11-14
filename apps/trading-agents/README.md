# TradingAgents desk

A single-user paper desk for [TradingAgents](https://github.com/TauricResearch/TradingAgents) (Apache-2.0), the multi-agent LLM trading framework from Tauric Research. Analysts write market, sentiment, news, and fundamentals reports. A bull and a bear debate them. A trader proposes an action. A risk team and a portfolio manager produce a paper BUY, HOLD, or SELL.

Nothing here places an order. The page says so: research and simulation only, not financial advice.

- Framework: https://github.com/TauricResearch/TradingAgents (pinned in `sidecar/requirements.txt` at `9fa1196`, package 0.7.1)
- Paper: https://arxiv.org/abs/2412.20138
- Bookmark: https://x.com/gusik4ever/status/2119044302319853924

## Prerequisites

On macOS, install Bun and uv. TradingAgents needs Python 3.11 or newer; `bun run dev` asks uv for Python 3.13.

```bash
curl -fsSL https://bun.sh/install | bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Run

From this directory:

```bash
bun run dev
```

That creates `sidecar/.venv` with Python 3.13 on first launch, installs TradingAgents, and starts the Vite app at http://127.0.0.1:5173 plus the FastAPI sidecar at http://127.0.0.1:8000. The page calls `/api` through the Vite proxy.

Open the page, leave the sample ticker, and click **Run**. With no LLM key, the run is the shipped transcript and the page shows a replay banner. **Replay sample** plays that transcript even when a key is set.

## India mode

The switch turns on for tickers ending in `.NS` or `.BO`, and for `^NSEI`, `^BSESN`, and `^NSEBANK`. Prices for those listings are shown in ₹. The run keeps Yahoo Finance for prices and statements, and adds:

- Screener.in ratios, quarterly results, and promoter / FII / DII shareholding when the public page loads
- Moneycontrol, Economic Times, Business Standard, and LiveMint market RSS, plus Google News, filtered by name and date
- NSE corporate announcements and FII/DII flows when the public JSON answers
- INR/USD, India VIX, Nifty 50, a sector index, Brent, and a static RBI repo-rate and CPI note
- An optional TradingView technical summary (1D and 1W Buy/Sell/Neutral, oscillators, moving averages, RSI, MACD, ADX) via `tradingview-ta`. It is labeled supplementary and does not replace the sources above.

StockTwits, Reddit, SEC EDGAR, and FRED are not used in India mode. Each source is a row on the page: ok, failed, skipped, or blocked. A timeout or a blocked NSE or TradingView call is not retried.

`sidecar/sample_run_india.json` is an illustrative India transcript. **Replay sample** plays it when India mode is on. It was not captured from a model.

Preview the fetchers without an LLM:

```bash
sidecar/.venv/bin/python -m india.preview RELIANCE.NS
```

Run that with the working directory set to `sidecar/`. The static RBI note lives in `sidecar/india/rbi_note.py`.

## Keys

Copy `.env.example` to `.env`. Live runs need the key for the provider you pick:

- `XAI_API_KEY` — xAI / Grok. The form defaults here (`grok-4.6` for both the quick and deep tiers).
- `OPENAI_API_KEY` — OpenAI. Quick default `gpt-6-luna`, deep default `gpt-6-sol`, matching the library.
- `ANTHROPIC_API_KEY` — Anthropic. Quick default `claude-sonnet-5-5`, deep default `claude-opus-5-5`. The form lists the models confirmed from Anthropic's `/v1/models` endpoint. Unscoped keys also need optional `ANTHROPIC_WORKSPACE_ID`. TradingAgents' Anthropic client does not forward `default_headers`, so the sidecar sends `anthropic-workspace-id` when that variable is set.
- `GOOGLE_API_KEY`

Market data stays on the library default: Yahoo Finance for prices, indicators, and news; SEC EDGAR then Yahoo for statements; Polymarket with no key; FRED for macro. FRED is skipped, with an unavailable note inside the news work, when `FRED_API_KEY` is unset. Alpha Vantage is not on the vendor chain. Do not commit `.env`.

The sample file `sidecar/sample_run.json` is an illustrative transcript. It was not captured from a model. This demo was built in an environment with no LLM key.

## Tests

```bash
sidecar/.venv/bin/python -m pytest sidecar/tests
```

Run that from this directory. The tests cover the stage diff, the India parsers (mocked network, including TradingView), and the pinned library’s `propagate` / `stream_run` surface. They do not call an LLM. The preview command above is the live network check.
