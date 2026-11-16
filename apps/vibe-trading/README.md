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
bun install
bun run dev
```

`bun install` puts `vite` on `PATH`. `bun run dev` runs it again when `node_modules` is missing, then creates `sidecar/.venv` on first launch and installs Vibe-Trading.

The page is http://127.0.0.1:5174. The FastAPI desk is http://127.0.0.1:8010. `vibe-trading serve` is http://127.0.0.1:8899. The Vite proxy sends `/api` to the desk port. These are not the trading-agents ports (8000 and 5173).

Set `DESK_PORT`, `VITE_PORT`, and `VIBE_PORT` in `.env` to move them. The proxy follows `DESK_PORT`. If the chosen port is already taken, `bun run dev` stops and names it:

```bash
lsof -ti tcp:8010 | xargs kill
```

Replace `8010` with the port from the message. The same line is printed for the Vite port and the Vibe-Trading port.

Open the page and click **Run**. With no LLM key, the run is the shipped sample and the page shows a replay banner. **Replay sample** plays that sample even when a key is set. **Daily sample** plays a flat layout whose equity file is a daily series, so the report can be reviewed with a full year of bars.

## Keys

Copy `.env.example` to `.env`. Live sessions need the key for the provider you pick:

- `XAI_API_KEY` — xAI. vibe-trading-ai 0.1.19 has no xAI catalog entry, so the desk runs the OpenAI-compatible client at `https://api.x.ai/v1` with model `grok-4.6`.
- `OPENAI_API_KEY` — OpenAI. Model `gpt-5.5`, the catalog default.
- `ANTHROPIC_API_KEY` — Anthropic. The page lists `claude-sonnet-5-5` (the default), `claude-opus-5-5`, and `claude-fable-5-2`. Opus and Fable cost several times more than Sonnet. `ANTHROPIC_MODEL` in `.env` changes the default; the model you pick on the page is the one used for that run, and the run card shows it. Claude 5 models (`claude-sonnet-5*`, `claude-opus-5*`, `claude-fable-5*`, `claude-haiku-5*`) are not sent `temperature`, `top_p`, or `top_k`. If Anthropic still returns HTTP 400 `invalid_request_error` for one of those fields, the desk retries once without them and logs a warning. Claude 4 keeps the sampling values it was given. Optional `ANTHROPIC_WORKSPACE_ID` is sent as the `anthropic-workspace-id` header. The 0.1.19 Anthropic builder does not set that header, so the same wrapper adds it.

Do not commit `.env`. Session files and the serve log stay under `sidecar/.run-data`.

## What a finished run shows

Equity versus a dashed buy-and-hold line, a red-shaded drawdown, and buy and sell marks on the curve. Gains are green and losses are red, each with a sign or an arrow. Sharpe, max drawdown, and win rate also carry a low / mid / high or shallow / moderate / deep label.

Below the charts, a report compares the strategy with buy-and-hold (return, CAGR, Sharpe, Sortino, max drawdown, volatility, win rate, profit factor, average win and loss, best and worst trade, time in market, closed trades, and fees as a share of PnL). It also has a monthly-return heatmap, round trips, the largest drawdown periods, a summary computed from those numbers, and the data notes (source, date range, frequency, warmup, starting capital, fee model, benchmark source). **Download report** saves Markdown. **Download trades CSV** saves the round trips. A figure that the equity, trades, and fills files cannot support is an em dash.

Return, CAGR, and max drawdown use the run's initial cash (`initial_cash` on the run card or in `config.json`) as the base, so the report matches the run card. When that figure is missing, the base is the first equity bar. Sharpe is copied from the run metrics when the run recorded one. The note that the file is not a daily series appears only when the bars are not a daily series. Sortino, volatility, and a monthly cell stay blank in that case. The nested RELIANCE sample is that case: three equity bars, so its heatmap is blank. Warmup is the requested start through the first equity bar. The fee model is the rate or bps recorded on the config or the fills, and stays a dash only when neither has one. The summary names the longest stretch out of the market, including the stretch after the last exit.

Buy-and-hold in the comparison table and on the chart is computed from the run's price bars for every run. Live Vibe-Trading 0.1.19 writes `artifacts/ohlcv_<TICKER>.csv` (`trade_date,open,high,low,close,volume`). `bars.csv`, `price_series.csv`, and any other OHLCV file in `artifacts/` are read the same way. When that folder has no price file, the desk downloads the ticker's daily closes from Yahoo Finance for the requested dates. It buys the first close on or after the requested start and sells the last close, charging slippage and fees once each way. India names use the delivery schedule, and a config key overrides the default. A separate buy-and-hold folder, or the equity file's benchmark column, is quoted in the notes and is not the table. The RELIANCE fixtures share one `ohlcv_RELIANCE.NS.csv`, so both show −7.14%. That hold is one trade and is in the market for the whole window. `yfinance` and `yahoo` both display as Yahoo Finance (yfinance). On a daily series, a month before the first equity bar shows 0.00% as warmup, and the first month with bars is measured from starting capital. The card title comes from the strategy code. A prompt names it only when the code does not. A constant signal (`pd.Series(1.0)` or a flat zero) under a rule such as a 20/50 SMA crossover is titled Always long or Always flat, and the card and the report show a warning. A live session in that state is asked to rewrite the signal once.

Vibe-Trading 0.1.19’s summary metrics do not include a fee total. The desk sums `fee` or `commission` on the trade rows, and when those are absent it sums `artifacts/fills.jsonl`.

When a run writes the requested strategy in a subdirectory (the live RELIANCE.NS session used `sma/`) and leaves buy-and-hold at the run root, the run card, the curves, the trades, and the generated code are the strategy. Buy-and-hold is the benchmark line and its return is labeled separately. The strategy source is that subdirectory’s `signal_engine.py`.

The timeline marks a step done when its events finish. Ground is also done when the backtest progress recorded a data source, which is how a RELIANCE.NS run reports yfinance without a separate fetch tool. A step that never started is skipped once the session ends, so nothing stays on Waiting.

`RELIANCE.NS` is a preset because 0.1.19 classifies `.NS` and `.BO` as `india_equity`. Bare `AAPL` is `us_equity`. `BTC-USDT` is `crypto`. A suffix with no rule, such as `7203.T`, is not matched.

Before a live or auto run, a symbol with an exchange suffix is checked with a short Yahoo Finance history call. `WELSPUN.NS` is not a Yahoo symbol (the listed names are `WELSPUNLIV.NS`, `WELCORP.NS`, and `WELENT.NS`). The page stops with: `No price data for WELSPUN.NS on Yahoo Finance. Check the ticker symbol.` An empty bar set or a missing timezone from the run uses the same sentence. **Replay sample** does not call Yahoo.

## Sample data

With no key, Replay plays `sidecar/fixtures/reliance_sma/`. That directory is the nested layout from a live RELIANCE.NS 2024 session: the 20/50 SMA under `sma/` (return +11.6%, Sharpe 0.80, max drawdown −9.59%, 3 trades, fills summing to 7,355) and a buy-and-hold folder the table does not use. The page shows the SMA as the headline. It does not call a model or refetch bars. `vibe-trading run` still needs a model, and this environment has no key, so a new live session was not run here.

**Daily sample** plays `sidecar/fixtures/reliance_daily/`. That layout has no `sma/` or `bh/` directory. The engine is `code/signal_engine.py` at the run root and initial cash is 1,000,000. It uses the same `ohlcv_RELIANCE.NS.csv` as the nested sample, so buy-and-hold is also −7.14%. The equity file is one bar per weekday in 2024. The banner says it is a saved layout, not a live session.

**Constant signal** plays `sidecar/fixtures/reliance_constant/`. The prompt asks for a 20/50 SMA crossover and `signal_engine.py` returns `pd.Series(1.0)`. The card is titled Always long and the report shows the warning. Buy-and-hold is still −7.14% from `ohlcv_RELIANCE.NS.csv`.

`bun run dev` starts `vibe-trading serve` on 127.0.0.1:8899 (or `VIBE_PORT`) and waits on `GET /health`. The package has no `frontend/dist`, so serve prints “No frontend build found” at startup and `GET /` returns 404. This desk does not use that UI and does not request `/`.

The engine itself does run without a key. From the installed 0.1.19 package, `GlobalEquityEngine.run_backtest` was called with an in-memory loader and a 5/20 moving-average signal on a synthetic rising series named `SYNTH` (80 business days from 2024-01-02, source `local`, no network). That run wrote `equity.csv`, `trades.csv`, `fills.jsonl`, and `run_card.json`. The card’s metrics were total return 0.2173, annual return 0.8578, Sharpe 4.04, max drawdown −0.0233, win rate 1.0, and one trade. The summary metrics still had no fee total. Those figures describe the synthetic series only. They are not the sample shown on the page, and they are not a market backtest.

## Tests

```bash
sidecar/.venv/bin/python -m pytest sidecar/tests
```

Run that from this directory. The tests mock the Vibe-Trading HTTP API. They do not call an LLM or the network. `test_markets.py` imports the installed package and checks the NSE rule.
