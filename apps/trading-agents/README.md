# TradingAgents desk

A single-user paper desk for [TradingAgents](https://github.com/TauricResearch/TradingAgents) (Apache-2.0), the multi-agent LLM trading framework from Tauric Research. Analysts write market, sentiment, news, and fundamentals reports. A bull and a bear debate them. A trader proposes an action. A risk team and a portfolio manager produce a paper BUY, HOLD, or SELL.

Nothing here places an order. The page says so: research and simulation only, not financial advice.

- Framework: https://github.com/TauricResearch/TradingAgents (pinned in `sidecar/requirements.txt` at `9fa1196`, package 0.7.1)
- Paper: https://arxiv.org/abs/2412.20138
- Bookmark: https://x.com/gusik4ever/status/2119044302319853924

## Run

From this directory:

```bash
bun run dev
```

That creates `sidecar/.venv` with Python 3.13 on first launch, installs TradingAgents, and starts the Vite app at http://127.0.0.1:5173 plus the FastAPI sidecar at http://127.0.0.1:8000. The page calls `/api` through the Vite proxy.

Open the page, leave the sample ticker, and click **Run**. With no LLM key, the run is the shipped transcript and the page shows a replay banner. **Replay sample** plays that transcript even when a key is set.

## Keys

Copy `.env.example` to `.env`. Live runs need the key for the provider you pick:

- `XAI_API_KEY` — xAI / Grok. The form defaults here (`grok-4.6` for both the quick and deep tiers).
- `OPENAI_API_KEY` — OpenAI. Quick default `gpt-6-luna`, deep default `gpt-6-sol`, matching the library.
- `ANTHROPIC_API_KEY`
- `GOOGLE_API_KEY`

Market data stays on the library default: Yahoo Finance for prices, indicators, and news; SEC EDGAR then Yahoo for statements; Polymarket with no key; FRED for macro. FRED is skipped, with an unavailable note inside the news work, when `FRED_API_KEY` is unset. Alpha Vantage is not on the vendor chain. Do not commit `.env`.

The sample file `sidecar/sample_run.json` is an illustrative transcript. It was not captured from a model. This demo was built in an environment with no LLM key.

## Tests

```bash
sidecar/.venv/bin/python -m pytest sidecar/tests
```

Run that from this directory. The tests cover the stage diff and the pinned library’s `propagate` / `stream_run` surface. They do not call an LLM or the network.
