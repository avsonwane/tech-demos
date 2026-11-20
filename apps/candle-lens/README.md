# Candle Lens

A one-page port of [AI Agent Lens](https://github.com/roan-maverick/tradingview-indicator-for-ai-agents) (Pine Script v6, MIT, © 2026 roan-maverick). It runs the indicator on free daily Yahoo Finance bars, shows each closed candle's `ai-agent-lens/v1` packet, asks Claude for a second opinion, and checks whether the official score-70 setups beat buy-and-hold after fees.

The indicator logic follows `ai-agent-lens.pine` where that file differs from `docs/SPECIFICATION.md`. On daily bars the higher timeframe is a fully closed week, and VWAP is anchored to the calendar year.

Source bookmark: [RohOnChain, 2026-11-17](https://x.com/RohOnChain/status/2121262884105974022).

Research and paper trading only. It does not place orders and it does not talk to a broker.

## Run

```bash
cd apps/candle-lens
bun install
bun run dev
```

Open http://127.0.0.1:5175. The API listens on http://127.0.0.1:8011. Copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY` if you want a live Ask the agent call. With no key, that button plays the labeled sample shipped from the upstream examples. The chart, packet, and Reality check work either way.

`bun test` covers the indicator math, candle patterns, the 70-cross setup, weekly lookahead, the fee-aware backtest, and the Anthropic request wrapper. Tests do not call Yahoo or a model.
