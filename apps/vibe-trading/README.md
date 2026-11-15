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
- `ANTHROPIC_API_KEY` — Anthropic. Model `claude-sonnet-5-5`. The 0.1.19 catalog default is `claude-sonnet-4-6`. `claude-sonnet-5-5` and `claude-fable-5*` reject a non-default temperature, and the 0.1.19 client sends 0.0, so `sidecar/launch_serve.py` clears `temperature`, `top_p`, and `top_k` for those models before the request. Optional `ANTHROPIC_WORKSPACE_ID` is sent as the `anthropic-workspace-id` header. The 0.1.19 Anthropic builder does not set that header, so the same wrapper adds it.

Do not commit `.env`. Session files and the serve log stay under `sidecar/.run-data`.

## What a finished run shows

Equity versus buy-and-hold, drawdown, the trade list, return, CAGR, Sharpe, max drawdown, win rate, and fees. Vibe-Trading 0.1.19’s summary metrics do not include a fee total. The desk sums `fee` or `commission` on the trade rows, and when those are absent it sums `artifacts/fills.jsonl`.

When a run writes the requested strategy in a subdirectory (the live RELIANCE.NS session used `sma/`) and leaves buy-and-hold at the run root, the run card, the curves, the trades, and the generated code are the strategy. Buy-and-hold is the benchmark line and its return is labeled separately. The strategy source is that subdirectory’s `signal_engine.py`.

The timeline marks a step done when its events finish. Ground is also done when the backtest progress recorded a data source, which is how a RELIANCE.NS run reports yfinance without a separate fetch tool. A step that never started is skipped once the session ends, so nothing stays on Waiting.

`RELIANCE.NS` is a preset because 0.1.19 classifies `.NS` and `.BO` as `india_equity`. Bare `AAPL` is `us_equity`. `BTC-USDT` is `crypto`. A suffix with no rule, such as `7203.T`, is not matched.

## Sample data

With no key, Replay plays `sidecar/fixtures/reliance_sma/`. That directory is the nested layout from a live RELIANCE.NS 2024 session: buy-and-hold at the root (return −6.04%) and the 20/50 SMA under `sma/` (return +11.6%, Sharpe 0.80, max drawdown −9.59%, 3 trades, fills summing to 7,355). The page shows the SMA as the headline. It does not call a model or refetch bars. `vibe-trading run` still needs a model, and this environment has no key, so a new live session was not run here.

`bun run dev` starts `vibe-trading serve` on 127.0.0.1:8899 and waits on `GET /health`. The package has no `frontend/dist`, so serve prints “No frontend build found” at startup and `GET /` returns 404. This desk does not use that UI and does not request `/`.

The engine itself does run without a key. From the installed 0.1.19 package, `GlobalEquityEngine.run_backtest` was called with an in-memory loader and a 5/20 moving-average signal on a synthetic rising series named `SYNTH` (80 business days from 2024-01-02, source `local`, no network). That run wrote `equity.csv`, `trades.csv`, `fills.jsonl`, and `run_card.json`. The card’s metrics were total return 0.2173, annual return 0.8578, Sharpe 4.04, max drawdown −0.0233, win rate 1.0, and one trade. The summary metrics still had no fee total. Those figures describe the synthetic series only. They are not the sample shown on the page, and they are not a market backtest.

## Tests

```bash
sidecar/.venv/bin/python -m pytest sidecar/tests
```

Run that from this directory. The tests mock the Vibe-Trading HTTP API. They do not call an LLM or the network. `test_markets.py` imports the installed package and checks the NSE rule.
