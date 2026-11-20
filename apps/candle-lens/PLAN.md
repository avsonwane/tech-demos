# Candle Lens

## Goal

A single-user page that ports AI Agent Lens (Pine Script v6, MIT) to TypeScript, runs it on free daily candles, and lets you inspect each bar's packet, ask Claude for a second opinion, and check whether trading only the official score-70 setups beats buy-and-hold after fees.

Source: [roan-maverick/tradingview-indicator-for-ai-agents](https://github.com/roan-maverick/tradingview-indicator-for-ai-agents) and the bookmark [RohOnChain, 2026-11-17](https://x.com/RohOnChain/status/2121262884105974022).

## Single-user MVP

- One page with symbol chips for `RELIANCE.NS` (default), `^NSEI`, and `BTC-USD`. Daily Yahoo Finance bars only. A date window defaults to 2024-01-01 through 2024-12-31, with earlier bars fetched only as indicator warmup (EMA 200, ATR percentile 100, weekly EMA 50).
- A candlestick chart. Click a closed candle to inspect its `ai-agent-lens/v1` JSON packet, the five-factor long and short scores, and the entry, 1.5×ATR stop, and 1.5R / 3R targets drawn on the chart. The latest bar is selected on load.
- An **Ask the agent** button sends the selected packet to Claude and shows LONG, SHORT, WAIT, or SKIP, plus `why_this_could_fail`. The model picker matches `apps/vibe-trading`: `claude-sonnet-5-5` default, `claude-opus-5-5` and `claude-fable-5-2` optional. With no `ANTHROPIC_API_KEY`, the button plays a labeled illustrative sample and the page shows a banner. The core chart, packet, and backtest work without a key.
- A **Reality check** strip: take the indicator's official setups (score crosses 70 on a closed bar, with the regime filters below), apply fees and slippage, and compare return, CAGR, Sharpe, max drawdown, win rate, trade count, and fees with buy-and-hold over the same evaluation window.
- Visible line: "Research and paper trading only, not financial advice."
- `bun install && bun run dev` starts the Vite page and a Bun API. The browser talks only to `/api`. No paid market-data key.

## Out of scope

Live trading, brokers, orders, TradingView webhooks or a packet receiver, intraday timeframes, a multi-symbol watchlist or alerts, and any edit outside `apps/candle-lens/` plus the tracking entry for this bookmark.

## Vertical slices

1. Scaffold Vite and the Bun API so `bun run dev` serves a page that can call `/api/health` (reports whether an Anthropic key is present, never the key itself).
2. Fetch daily OHLCV through the API and render a candlestick chart with symbol chips and a date window.
3. Port the packet builder, attach click-to-inspect (JSON, score breakdown, entry / stop / targets on the chart), and cover it with parity tests.
4. Add the Reality check strip versus buy-and-hold, with fees and slippage.
5. Wire Ask the agent: live Claude call when a key is set, illustrative sample when it is not.

## Stack

- **Vite + React + TypeScript** via `bunx create-vite` (`react-ts`, skip the immediate install). One screen.
- **`bunfig.toml`** with `[install] minimumReleaseAge = 259200`, written before `bun install` or `bun add`.
- **shadcn/ui preset Sera** (`--preset sera --base radix`), matching the other desks. Add components as needed: button, card, badge, select, separator, scroll-area.
- **lightweight-charts** (Apache-2.0), already used in `apps/kronos-forecast`. Candles, EMA lines, and price lines for entry, stop, and targets on one time scale. Click and crosshair select a bar.
- **Bun API** in `server/`, started by `scripts/dev.ts` next to Vite. The packet builder, backtest, and Anthropic call are TypeScript. Vite proxies `/api` to the API. The key never ships to the browser.
- **Yahoo Finance** via the public chart API from the Bun server. Adjusted OHLC for equities (scale by `adjclose / close`). Cache under `server/.cache` (gitignored). If a live fetch fails, the page can still load a shipped fixture for one symbol, labeled as a fixture.
- **`@anthropic-ai/sdk`** for Ask the agent.
- **`bun:test`** for the packet builder, indicators, backtest math, and the Anthropic request wrapper.

Ports default to API `8011` and Vite `5175` (`DESK_PORT`, `VITE_PORT`) so they do not collide with trading-agents / kronos (`8000` / `5173`) or vibe-trading (`8010` / `5174`).

## Packet port (Pine defaults, closed bars only)

Port `docs/SPECIFICATION.md` and `ai-agent-lens.pine` faithfully. Implement the indicators in TypeScript to match Pine; do not trust a third-party TA library for the scored values.

| Piece | Rule |
| --- | --- |
| EMA 20 / 50 / 200 | Pine `ta.ema`: SMA seed, then α = 2 / (length + 1). |
| RSI 14, MACD 12 / 26 / 9, ATR 14, DMI / ADX 14 | Wilder / Pine `ta.rsi`, `ta.macd`, `ta.atr`, `ta.dmi`. |
| ATR percentile | Pine `ta.percentrank(ATR, 100)`, 0 to 100. HIGH_VOLATILITY at >= 90. |
| Relative volume | volume / SMA(volume, 20). Missing or zero volume is `null`. |
| Regime | First match: HIGH_VOLATILITY, else TREND_UP (close > EMA 200, EMA 200 rising over 5 bars, ADX >= 20), else TREND_DOWN (mirror), else RANGE. |
| Scores | Five factors, 20 points each, long and short independent. Trend 7+7+6 on the EMA stack and close vs EMA 20. Momentum: RSI > 50 gives 10, or 4 if RSI >= 75; +5 MACD hist > 0; +5 hist rising. Strength: 10 if DI+ > DI-, +10 if also ADX >= 20. Volume: 20 / 12 / 6 on a bullish bar at relVol >= 1.5 / >= 1.0 / otherwise. HTF: 20 if UP, 10 if FLAT or N/A, 0 if DOWN. Short is the exact mirror (RSI oversold at <= 25). Follow the Pine ternary when relative volume is `na` (a bullish bar still gets 6). |
| Setups | A setup fires when that side's score crosses up through 70, the regime is not the opposite trend, and HIGH_VOLATILITY is blocked (default on). If both fire, neither is taken. Same-direction setups are ignored while a trade is open; an opposite setup replaces it. Entry is the signal bar close. Stop is 1.5 × ATR. Targets are 1.5R and 3R. On later bars the stop is checked first. |
| Patterns | First match: FLAT, BULLISH / BEARISH_ENGULFING, DOJI, HAMMER, SHOOTING_STAR, MARUBOZU, INSIDE_BAR, OUTSIDE_BAR, WIDE_RANGE_BULL / BEAR, else NONE. |
| Swings | Confirmed pivots with 5 bars each side, published 5 bars later and never moved. Bias BULLISH / BEARISH / MIXED from the last two swing highs and lows. BREAK_UP / BREAK_DOWN when close crosses the last swing. |

### Daily-data equivalents

- **Higher timeframe** defaults to `W`, not `240` (a 4h bias on daily bars would always be N/A). Weekly bars are aggregated from the daily series, and only a fully closed week is used (the `[1] + lookahead_on` rule).
- **VWAP** is a calendar-year anchored VWAP of `hlc3`. Previous-day high and low stay the previous daily bar.

`timeframe` in the packet is `D`. `symbol` uses a Yahoo-style ticker. Volume on `^NSEI` is often empty; those fields are `null`.

## Ask the agent

The system prompt is `agent/AGENT_PROMPT.md` from the upstream repo, filled in for this desk: research and paper trading only, daily bars, the selected symbol, no order placement. The user message is the raw packet. The reply is the official JSON plus the three-line summary, shown as a card that always includes `decision` and `why_this_could_fail`.

Anthropic conventions, copied from `apps/vibe-trading` (not a shared module):

- Key from `ANTHROPIC_API_KEY` in `apps/candle-lens/.env`. Never commit `.env` or print the key in logs, health payloads, or the UI.
- Page list: `claude-sonnet-5-5` (default), `claude-opus-5-5`, `claude-fable-5-2`. `ANTHROPIC_MODEL` overrides the default; the page selection wins for that request. An unknown id is rejected.
- Optional `ANTHROPIC_WORKSPACE_ID` is sent as `anthropic-workspace-id`.
- Claude 5 models are not sent `temperature`, `top_p`, or `top_k`. A 400 `invalid_request_error` that mentions those fields is retried once without them.
- No key: `/api/health` returns `anthropic: false`, and Ask the agent loads `server/sample_signal.json` against `server/sample_packet.json`, both labeled illustrative, without calling the network.

## Reality check

A fee-aware backtest of the official setup rule, not "stay in the market on every bar the score is above 70."

- The evaluation window is the date range on the form, never the warmup start. Buy-and-hold is one entry and one exit on the first and last close in that window, with the same fee model charged once each way.
- India names (`.NS` / `.BO`) use the vibe-trading India delivery schedule: slippage 10 bps, STT 10 bps, exchange 0.297 bps, SEBI 0.01 bps, stamp duty 1.5 bps on buys, GST 18% on brokerage, exchange, and SEBI. `^NSEI` and `BTC-USD` use 10 bps slippage and 10 bps fee each way.
- Starting capital is ₹1,00,000 for India names and $10,000 for `BTC-USD` and `^NSEI`. Entry, stop, and targets get slippage; the stop is still checked first. The strip notes that the Pine trade tracker itself has no fees.
- On RELIANCE.NS for 2024-01-01 to 2024-12-31, buy-and-hold after India fees should be close to −6.23% if the adjusted Yahoo closes match. That's a cross-check, not a hard gate.

## Layout

```
apps/candle-lens/
  PLAN.md
  README.md
  .env.example
  bunfig.toml
  scripts/dev.ts          API + Vite
  server/                 Bun API: market, agent, health
  server/lens/            packet builder, indicators, backtest
  server/tests/
  server/sample_packet.json
  server/sample_signal.json
  src/features/lens/      page, chart, packet pane, agent card, strip
  src/components/ui/
```

The README covers what it demos, the source link, the MIT attribution, how to run it, and that it is research and paper trading only.

## Testing

`bun test` covers: EMA / RSI / MACD / ATR / DMI on a hand-computed fixture; each candle pattern in priority order; score factors and the 70-cross setup; regime order; swing confirmation delay; weekly HTF with no lookahead; risk-map arithmetic; backtest fees and the buy-and-hold window; the Anthropic wrapper (model list, no Claude 5 sampling fields, workspace header, 400 retry, no-key sample); and that logs and health never contain a key value. No test calls an LLM or Yahoo.

The demo PR must include at least one screenshot and at least one video of the running app.

## Deferred

Intraday bars and session VWAP, a TradingView webhook receiver, token streaming of the agent reply, and a repo-level formatter hook.
