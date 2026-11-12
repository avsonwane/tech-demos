# Kronos forecast demo

## Goal

A single-user page that loads free OHLCV candles, draws them, and overlays a fan of paths sampled from the Kronos-mini candlestick model, plus a blind holdout check.

## Single-user MVP

- Enter a symbol and a timeframe (`15m`, `1h`, `4h`, `1d`). Crypto pairs ending in `USDT` come from the Binance public klines API (no key). Anything else (for example `AAPL`) comes from Yahoo Finance via `yfinance`.
- Candlestick history plus a fan of Monte Carlo close paths from `KronosPredictor`, a stronger median path, and a short plain-English line: median direction versus the last close, and the 10th–90th percentile spread at the horizon.
- Test mode: hold out the last N bars, forecast that window with no access to it, draw the actual candles on top of the fan, and show a direction-hit count plus close MAPE.
- A visible “Not financial advice” note on the page.
- `bun run dev` installs the Python env on first run if needed, then starts the Vite app and the FastAPI sidecar together.

## Out of scope

Trading, orders, brokers, wallets, portfolios, fine-tuning, Kronos-base, Kronos-large, and accounts. Kronos-small is not in the UI (mini only).

## Vertical slices

1. Scaffold the Vite app and the sidecar so `bun run dev` serves a page that can call `/api/health`.
2. Fetch candles through the sidecar and render them.
3. Run Kronos-mini and draw the forecast fan plus the summary sentence.
4. Add test mode (holdout, overlay, hit rate and MAPE).

## Stack

- **Vite + React + TypeScript** via `bunx create-vite` — one screen, so a full Next.js app would only duplicate the Python API.
- **shadcn/ui preset `sera`** — the style described as minimal / editorial. Initialized with `bunx shadcn@latest init` after `bunfig.toml` exists. Components added only as needed (`button`, `card`, `input`, `label`, `select`, `badge`).
- **lightweight-charts** (Apache-2.0) — candlesticks and extra line series on one time scale, no paid license.
- **FastAPI + uvicorn** — Kronos is PyTorch. The browser never runs the model. Vite proxies `/api` to the sidecar so there is no CORS hop.
- **uv + `requirements.txt`** — CPU PyTorch wheel from the official CPU index; the rest from PyPI. `bun run dev` creates `sidecar/.venv` when it is missing.
- **Vendored `model/` from Kronos** at commit `67b630e67f6a18c9e9be918d9b4337c960db1e9a` (MIT). The repo is not a pip package. `KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-2k")` and `Kronos.from_pretrained("NeoQuasar/Kronos-mini")` load the weights. `KronosPredictor` is constructed with `device="cpu"` and `max_context=512`.
- Upstream `predict()` averages `sample_count` paths into one frame. A small local flag on the vendored inference returns the sample axis so the chart can draw the fan. Sampling stays inside Kronos (`T=1.0`, `top_p=0.9`).

## Defaults (CPU)

Lookback 400 bars, horizon 24, 8 paths, test holdout 12. One forecast at a time. Weights cached under `sidecar/.cache` (not committed).

## Data notes

Binance `GET /api/v3/klines` does not send browser CORS headers, so the sidecar fetches it. The public market-data host is `data-api.binance.vision`, with `api.binance.com` as a fallback (`api.binance.com` returns HTTP 451 in some regions). Quote volume is passed through as Kronos `amount`. Equity daily timestamps step on business days when the history has no weekend bars; crypto keeps a fixed bar delta, including weekends.

## Test score

On the holdout window, compare the median close path with the actual closes. Direction hit: sign of each step’s close change matches. Error: mean absolute percentage error of close. The summary also states whether the horizon close is up, down, or flat (flat means absolute move under 0.05%).

## Testing and hooks

Pytest covers scoring, future-timestamp stepping, and Binance row parsing. No test loads the model or the network. No git hooks: this repo has no hook runner, and a per-app formatter hook would live outside `apps/kronos-forecast/`.

## Layout

```
apps/kronos-forecast/
  src/features/forecast/   page, chart, API types
  src/components/ui/       shadcn components actually used
  scripts/dev.ts           sidecar + Vite
  sidecar/app.py           FastAPI
  sidecar/market.py        Binance and yfinance
  sidecar/forecast.py      KronosPredictor fan
  sidecar/scoring.py       pure hit rate and MAPE
  sidecar/vendor/model/    Kronos MIT sources
  sidecar/tests/
```

## Deferred

- Kronos-small / base, longer contexts, and GPU.
- Streaming partial paths, saved runs, and multiple symbols on one chart.
- Calibration, backtests, and fine-tuning.
- A repo-level formatter hook.

## Pull request base

`main` only contains the initial README, so this branch is based on `cursor/bootstrap-tech-demos-monorepo-288e`, which has the monorepo bootstrap.
