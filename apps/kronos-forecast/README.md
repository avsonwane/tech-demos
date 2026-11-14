# Kronos forecast

A single-user demo of [Kronos](https://github.com/shiyu-coder/Kronos), an MIT-licensed foundation model for financial candlesticks. Enter a symbol, fetch free OHLCV, and draw a fan of Monte Carlo paths from **Kronos-mini** (4.1M parameters) on CPU. Test mode hides the last N bars, forecasts them blind, overlays the actual candles, and reports a direction-hit count plus close MAPE.

This is a research demo. **Not financial advice.**

## Sources

- Model code: [shiyu-coder/Kronos](https://github.com/shiyu-coder/Kronos) (MIT), vendored under `sidecar/vendor/model` at commit `67b630e67f6a18c9e9be918d9b4337c960db1e9a`
- Weights: [NeoQuasar/Kronos-mini](https://huggingface.co/NeoQuasar/Kronos-mini) and [NeoQuasar/Kronos-Tokenizer-2k](https://huggingface.co/NeoQuasar/Kronos-Tokenizer-2k)
- Paper: [arXiv:2508.02739](https://arxiv.org/abs/2508.02739)
- Official live demo (UX reference): [shiyu-coder.github.io/Kronos-demo](https://shiyu-coder.github.io/Kronos-demo/)
- Bookmark: [https://x.com/slash1sol/status/2119531516892213633](https://x.com/slash1sol/status/2119531516892213633)

`KronosPredictor.predict` averages its samples. This demo passes `return_samples` through the vendored inference so each path stays on the chart.

## Run

Requires [Bun](https://bun.sh) and [uv](https://docs.astral.sh/uv/).

```bash
cd apps/kronos-forecast
bun install
bun run dev
```

Open http://127.0.0.1:5173/

`bun run dev` creates `sidecar/.venv` on first run, installs the CPU PyTorch wheel plus `sidecar/requirements.txt`, then starts the FastAPI sidecar on port 8000 and Vite on port 5173. The first launch also downloads the mini weights into `sidecar/.cache` (not committed).

Crypto symbols ending in `USDT` (for example `BTCUSDT`) load from Binance public klines. Other tickers (for example `AAPL`) load from Yahoo Finance. No API key.

## Limits

- CPU and Kronos-mini only. No fine-tuning, Kronos-large, trading, or broker connections.
- One forecast at a time. Defaults are 400 bars of context, 24 bars ahead, and 8 paths.
- `api.binance.com` returns HTTP 451 in some regions. The sidecar tries `data-api.binance.vision` first.
- Equity intraday bars can include session gaps. Daily equity timestamps step on business days when the history has no weekend bars. Crypto keeps a fixed bar spacing, including weekends.
