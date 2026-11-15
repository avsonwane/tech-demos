# Vibe Backtest desk

A single-user research page for [Vibe-Trading](https://github.com/HKUDS/Vibe-Trading) (MIT), the personal trading agent from HKUDS. You type a strategy in plain English. The page follows the session as it plans, fetches bars, writes strategy code, and runs a backtest, then shows the equity curve against buy-and-hold, the drawdown, the trades, the metrics, and the generated code.

Nothing here places an order or connects a broker. The page says so: research and simulation only, not financial advice.

- Package: [`vibe-trading-ai` 0.1.19](https://pypi.org/project/vibe-trading-ai/) (pinned in `sidecar/requirements.txt`, with the `anthropic` extra)
- Docs: https://vibetrading.wiki/docs/
- Source: https://github.com/HKUDS/Vibe-Trading

## Prerequisites

On macOS, install Bun and uv. Vibe-Trading needs Python 3.11 or newer; `bun run dev` asks uv for Python 3.13.

```bash
curl -fsSL https://bun.sh/install | bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Run

From this directory:

```bash
bun run dev
```

That creates `sidecar/.venv` on first launch, installs Vibe-Trading, and starts the Vite app at http://127.0.0.1:5173 plus the FastAPI desk at http://127.0.0.1:8000. The desk starts `vibe-trading serve` on http://127.0.0.1:8899. The page calls `/api` through the Vite proxy and does not talk to the Vibe-Trading server directly.

Open the page and click **Run**. With no LLM key, the run is the shipped sample and the page shows a replay banner. **Replay sample** plays that sample even when a key is set.

## Keys

Copy `.env.example` to `.env`. Live sessions need the key for the provider you pick:

- `XAI_API_KEY` — xAI. vibe-trading-ai 0.1.19 has no xAI catalog entry, so the desk runs the OpenAI-compatible client at `https://api.x.ai/v1` with model `grok-4.6`.
- `OPENAI_API_KEY` — OpenAI. Model `gpt-5.5`, the catalog default.
- `ANTHROPIC_API_KEY` — Anthropic. Model `claude-sonnet-4-6`, the catalog default. Optional `ANTHROPIC_WORKSPACE_ID` is sent as the `anthropic-workspace-id` header. The 0.1.19 Anthropic builder does not set that header, so `sidecar/launch_serve.py` adds it.

Do not commit `.env`. Session files and the serve log stay under `sidecar/.run-data`.

## What a finished run shows

Equity versus buy-and-hold, drawdown, the trade list, return, CAGR, Sharpe, max drawdown, win rate, and fees when the payload includes a fee or commission field. Vibe-Trading 0.1.19’s summary metrics do not include a fee total; per-fill fees stay in `fills.jsonl`, which this page does not read. The strategy source comes from `GET /runs/{id}/code`. The run card shows the data source and the date range.

`RELIANCE.NS` is a preset because 0.1.19 classifies `.NS` and `.BO` as `india_equity`. Bare `AAPL` is `us_equity`. `BTC-USDT` is `crypto`. A suffix with no rule, such as `7203.T`, is not matched.

## Sample data

`sidecar/sample_run.json` is an illustrative run. The numbers are round and were not produced by the engine or a model. This demo was built with no LLM key, so the page’s live session path (`vibe-trading serve` plus a model) was not exercised. `vibe-trading run` also needs a model.

`bun run dev` did start `vibe-trading serve` on 127.0.0.1:8899. Its startup check reported the OpenAI-compatible client, yfinance, and OKX as reachable. No session message was sent, so that process did not run a backtest.

The engine itself does run without a key. From the installed 0.1.19 package, `GlobalEquityEngine.run_backtest` was called with an in-memory loader and a 5/20 moving-average signal on a synthetic rising series named `SYNTH` (80 business days from 2024-01-02, source `local`, no network). That run wrote `equity.csv`, `trades.csv`, `fills.jsonl`, and `run_card.json`. The card’s metrics were total return 0.2173, annual return 0.8578, Sharpe 4.04, max drawdown −0.0233, win rate 1.0, and one trade. The summary metrics still had no fee total. Those figures describe the synthetic series only. They are not the sample shown on the page, and they are not a market backtest.

## Tests

```bash
sidecar/.venv/bin/python -m pytest sidecar/tests
```

Run that from this directory. The tests mock the Vibe-Trading HTTP API. They do not call an LLM or the network. `test_markets.py` imports the installed package and checks the NSE rule.
