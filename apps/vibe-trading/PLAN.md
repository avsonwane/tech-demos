# Vibe Backtest desk

## Goal

A single-user page where a plain-English strategy prompt runs through Vibe-Trading and ends as a backtest: equity against buy-and-hold, drawdown, trades, metrics, generated code, and the data source on the run card.

## Single-user MVP

- One prompt box with three presets: a 2024 AAPL 20/50 SMA crossover versus buy-and-hold, the same idea on BTC-USDT, and the same idea on RELIANCE.NS.
- `vibe-trading-ai` 0.1.19 market rules accept `.NS` / `.BO` as `india_equity` (`matched_market` in `backtest/engines/_market_hooks.py`). The RELIANCE.NS chip stays. AAPL is `us_equity`. BTC-USDT is `crypto`.
- A vertical timeline fills as the session stream reports plan, data fetch, code generation, and backtest execution.
- When the run finishes, the page shows the equity curve against buy-and-hold, a drawdown chart, the trade list, return, CAGR (`annual_return`), Sharpe, max drawdown, win rate, and fees when the payload includes a fee or commission field. It also shows the generated strategy source and the run card’s data source plus date range.
- Paper and research only. The page says “Research/simulation only, not financial advice.” No broker connector, no live order, no Shadow Account auth.
- Replay: `sidecar/sample_run.json` is an illustrative run, labeled as such. With no key for the chosen provider, Run plays that file and the page shows a replay banner. Replay sample does the same when a key is present.
- `bun run dev` creates the Python env on first launch, starts Vite, and starts the FastAPI desk, which starts `vibe-trading serve` on 127.0.0.1:8899. The browser talks only to `/api` on the desk.

## Out of scope

Live trading, broker login, Shadow Account, swarm teams, the alpha zoo, scheduled research, paper-account stepping, and Vibe-Trading’s own web UI.

## Vertical slices

1. Scaffold Vite and the desk so `bun run dev` serves a page that can call `/api/health`, including a replay of the sample run.
2. Parse session SSE events into the four timeline phases and parse `GET /runs/{run_id}` plus `GET /runs/{run_id}/code` into the results view. Tests use a mocked HTTP client.
3. Wire a live session: create a session, send the prompt, follow `/sessions/{id}/events`, then load the run. Provider keys are mapped onto Vibe-Trading’s `LANGCHAIN_*` settings before `serve` starts.

## Stack

- **Vite + React + TypeScript** via `bunx create-vite` (`react-ts`, `--no-immediate`). One screen. A Next.js app would only proxy the Python agent.
- **shadcn/ui preset Sera** (`--preset sera --base radix`), matching `apps/trading-agents`. Components added as needed: button, card, input, label, textarea, badge, separator.
- **FastAPI + uvicorn** for the desk API. Vibe-Trading’s own server stays on 8899. The desk is the only process the browser proxies to, so replay works when that server is still booting and so broker routes never reach the page.
- **vibe-trading-ai 0.1.19** with the `anthropic` extra, from PyPI, MIT. The native Anthropic adapter is that extra (`langchain-anthropic`). OpenAI and the xAI mapping use the OpenAI-compatible client already in the base install.
- **uv + Python 3.13** (library supports 3.11+). `bun run dev` creates `sidecar/.venv`. `VIBE_TRADING_HOME` is `sidecar/.run-data` (gitignored).
- **`bunfig.toml`** with `[install] minimumReleaseAge = 259200`, written before `bun install`.
- **Inline SVG charts.** Two series on one page do not need a chart library.

## Provider mapping

The form lists xAI, OpenAI, and Anthropic. The first with a key is the default, xAI first. The desk restarts `vibe-trading serve` with a child environment when the selection changes. The parent process keeps the real keys.

| Desk | Child environment |
| --- | --- |
| xAI (`XAI_API_KEY`) | `LANGCHAIN_PROVIDER=openai`, `OPENAI_API_KEY` set from `XAI_API_KEY`, `OPENAI_BASE_URL=https://api.x.ai/v1`, model `grok-4.6`. The 0.1.19 catalog has no xAI provider. |
| OpenAI (`OPENAI_API_KEY`) | `LANGCHAIN_PROVIDER=openai`, `OPENAI_BASE_URL=https://api.openai.com/v1`, model `gpt-5.5` (the catalog default). |
| Anthropic (`ANTHROPIC_API_KEY`) | `LANGCHAIN_PROVIDER=anthropic`. The page offers `claude-sonnet-5-5` (default), `claude-opus-5-5`, and `claude-fable-5-2`. `ANTHROPIC_MODEL` overrides the default; the page selection wins for that run. Opus and Fable cost several times more than Sonnet. Optional `ANTHROPIC_WORKSPACE_ID` is sent as `anthropic-workspace-id`. Every `claude-sonnet-5*`, `claude-opus-5*`, `claude-fable-5*`, and `claude-haiku-5*` model is sent with no `temperature`, `top_p`, or `top_k`. A 400 `invalid_request_error` that mentions those fields is retried once without them. Claude 4 keeps its sampling params. |

## Session and result contract (0.1.19)

- `POST /sessions` `{title, config?}` → `session_id`.
- `POST /sessions/{id}/messages` `{content}`.
- `GET /sessions/{id}/events?replay=active` SSE. Frames use `event:` plus JSON `data`. Tool calls are `tool_call` (`tool`, `arguments`). Progress is `tool_progress` and `tool_heartbeat`. Results are `tool_result` (`tool`, `status`, `preview`). Data fetch is `get_market_data`. Code is `write_file` / `edit_file`. Execution is `backtest`. Earlier assistant text is the plan. `attempt.completed` carries `run_dir`; the run id is that directory name. `attempt.failed` and `attempt.cancelled` end the turn.
- `GET /runs/{run_id}` includes `metrics`, `artifacts_equity_csv` (timestamp, equity, drawdown, benchmark_equity), `artifacts_trades_csv`, and `run_card` (`data_sources`, `backtest.start_date`, `backtest.end_date`, `backtest.codes`). The equity preview omits the benchmark, so the desk prefers the full CSV rows.
- `GET /runs/{run_id}/code` returns `{ "signal_engine.py": "<source>" }`.
- Summary metrics in 0.1.19 have return, annual return, Sharpe, max drawdown, and win rate. They do not have a fee total. The desk sums trade `fee` / `commission` columns, then `fills.jsonl`, and says fees were not reported only when neither is present.
- A nested strategy directory (for example `sma/`) is the headline. Buy-and-hold at the run root is the benchmark. Ground is done when the backtest recorded a data source, and every step is done or skipped after a terminal event.

## Layout

```
apps/vibe-trading/
  src/features/desk/     page, timeline, charts, results, SSE client
  src/components/ui/     shadcn components actually used
  scripts/dev.ts         sidecar + Vite
  sidecar/app.py         FastAPI desk
  sidecar/proxy.py       HTTP client for vibe-trading serve
  sidecar/events.py      SSE phase reducer
  sidecar/results.py     run payload parser
  sidecar/providers.py   key → LANGCHAIN_* child env
  sidecar/launch_serve.py
  sidecar/sample_run.json
  sidecar/tests/
```

## Testing and hooks

Pytest covers the mocked session proxy, the phase reducer (including a finished run with no separate data-fetch tool), the run parser, the nested `sma/` fixture, fill-fee summing, the provider env mapping, the Anthropic workspace header, Claude 5 sampling removal, the 400 sampling retry, the WELSPUN.NS Yahoo rejection, the replay stream, and that `RELIANCE.NS` still classifies as `india_equity`. No test calls an LLM or the network. No git hooks: the repo has no hook runner.

Ports default to desk `8010`, Vite `5174`, and Vibe-Trading `8899` (`DESK_PORT`, `VITE_PORT`, `VIBE_PORT`). `bun run dev` runs `bun install` when `node_modules` is missing, and a busy port exits with `lsof -ti tcp:<port> | xargs kill`.

The review report is computed from equity, trades, and fills. Sharpe is copied from the run metrics when the equity file is not a daily series. Sortino, volatility, and a monthly cell stay blank in that case. The RELIANCE fixture is that case.

## Deferred

- Token-by-token chat. The timeline updates on tool and phase events.
- Swarm, alpha bench, options, and portfolio screens.
- A per-fill fee breakdown on the trade table. The card shows one summed total.
- A repo-level formatter hook.
