// AI Agent Lens packet builder. Closed bars only.
// Ported from ai-agent-lens.pine and docs/SPECIFICATION.md (MIT, © 2026 roan-maverick).
// Where the Pine source and the spec disagree, this follows the Pine source.
// Daily desk equivalents: timeframe D, weekly HTF, calendar-year VWAP.

import { atr, dmi, ema, macd, percentRank, pivots, rsi, sma } from "./indicators.ts"
import { candlePattern, type Candle, type Pattern } from "./patterns.ts"
import { htfPoints, weeklyBias, type HtfBias } from "./weekly.ts"

export type Bar = {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number | null
}

export type Regime = "HIGH_VOLATILITY" | "TREND_UP" | "TREND_DOWN" | "RANGE"
export type SideName = "NONE" | "LONG" | "SHORT"
export type TradeStatus = "NONE" | "ACTIVE" | "TARGET_1_HIT" | "TARGET_2_HIT" | "STOPPED" | "STOPPED_AFTER_T1"
export type EventName = "BAR_CLOSE" | "LONG_SETUP" | "SHORT_SETUP" | "TRADE_UPDATE"

export type Factors = {
  trend: number
  momentum: number
  strength: number
  volume: number
  htf: number
}

export type ScoreInput = {
  open: number
  close: number
  emaFast: number | null
  emaMid: number | null
  emaSlow: number | null
  rsi: number | null
  macdHist: number | null
  prevMacdHist: number | null
  diPlus: number | null
  diMinus: number | null
  adx: number | null
  relVol: number | null
  htf: HtfBias
}

export type Packet = {
  schema: "ai-agent-lens/v1"
  event: EventName
  symbol: string
  timeframe: "D"
  time: string
  state_code: string
  candle: {
    open: number
    high: number
    low: number
    close: number
    volume: number | null
    direction: "bull" | "bear" | "flat"
    body_pct: number
    upper_wick_pct: number
    lower_wick_pct: number
    range_atr: number | null
    close_position_pct: number
    gap_pct: number | null
    closed_above_prev_high: boolean
    closed_below_prev_low: boolean
    pattern: Pattern
  }
  recent_candles: {
    bars_ago: number
    o: number
    h: number
    l: number
    c: number
    v: number | null
    dir: "bull" | "bear" | "flat"
    body_pct: number
    range_atr: number | null
    pattern: Pattern
  }[]
  regime: Regime
  trend: {
    ema_fast: number | null
    ema_mid: number | null
    ema_slow: number | null
    stack: "BULLISH" | "BEARISH" | "MIXED"
    slow_slope: "RISING" | "FALLING" | "FLAT"
    htf: "W"
    htf_bias: HtfBias
  }
  momentum: { rsi: number | null; macd_hist: number | null; macd_hist_rising: boolean }
  strength: { adx: number | null; di_plus: number | null; di_minus: number | null }
  volatility: { atr: number | null; atr_percentile: number | null }
  volume: { relative: number | null }
  structure: {
    bias: "BULLISH" | "BEARISH" | "MIXED"
    event: "BREAK_UP" | "BREAK_DOWN" | "NONE"
    last_swing_high: number | null
    last_swing_low: number | null
  }
  levels: { prev_day_high: number | null; prev_day_low: number | null; vwap: number | null }
  scores: {
    long: number
    short: number
    threshold: number
    long_factors: Factors
    short_factors: Factors
  }
  trade: {
    side: SideName
    status: TradeStatus
    entry: number | null
    stop: number | null
    target_1: number | null
    target_2: number | null
    bars_since_entry: number | null
  }
  last_setup: { side: SideName; bars_ago: number | null }
}

export type ExitAction = {
  type: "exit"
  reason: "STOPPED" | "STOPPED_AFTER_T1" | "TARGET_2_HIT" | "REPLACED"
  price: number
}

export type OpenAction = {
  type: "open"
  side: "LONG" | "SHORT"
  entry: number
  stop: number
  target1: number
  target2: number
}

export type Action = ExitAction | OpenAction

export type TradeState = {
  side: 0 | 1 | -1
  sideStr: SideName
  status: TradeStatus
  entry: number | null
  stop: number | null
  t1: number | null
  t2: number | null
  bar: number | null
  lastSigBar: number | null
  lastSigSide: SideName
}

export type TradeStep = {
  index: number
  high: number
  low: number
  close: number
  atr: number | null
  longScore: number
  prevLong: number | null
  shortScore: number
  prevShort: number | null
  regime: Regime
}

const THRESHOLD = 70
const STOP_ATR = 1.5
const TARGET_1_R = 1.5
const TARGET_2_R = 3
const SLOPE = 5
const SWING = 5
const RECENT = 5

export function initialTrade(): TradeState {
  return {
    side: 0,
    sideStr: "NONE",
    status: "NONE",
    entry: null,
    stop: null,
    t1: null,
    t2: null,
    bar: null,
    lastSigBar: null,
    lastSigSide: "NONE",
  }
}

function gt(left: number | null, right: number | null): boolean {
  return left != null && right != null && left > right
}

function lt(left: number | null, right: number | null): boolean {
  return left != null && right != null && left < right
}

/** Five factors, 20 points each. A bullish bar with `na` relative volume still scores 6. */
export function scoreFactors(input: ScoreInput): { long: Factors; short: Factors; longScore: number; shortScore: number } {
  const longTrend = (gt(input.emaFast, input.emaMid) ? 7 : 0) + (gt(input.emaMid, input.emaSlow) ? 7 : 0) + (gt(input.close, input.emaFast) ? 6 : 0)
  const shortTrend = (lt(input.emaFast, input.emaMid) ? 7 : 0) + (lt(input.emaMid, input.emaSlow) ? 7 : 0) + (lt(input.close, input.emaFast) ? 6 : 0)
  const rsi = input.rsi
  const longMom =
    (rsi != null && rsi > 50 ? (rsi >= 75 ? 4 : 10) : 0) +
    (gt(input.macdHist, 0) ? 5 : 0) +
    (gt(input.macdHist, input.prevMacdHist) ? 5 : 0)
  const shortMom =
    (rsi != null && rsi < 50 ? (rsi <= 25 ? 4 : 10) : 0) +
    (lt(input.macdHist, 0) ? 5 : 0) +
    (lt(input.macdHist, input.prevMacdHist) ? 5 : 0)
  const plusLeads = gt(input.diPlus, input.diMinus)
  const minusLeads = gt(input.diMinus, input.diPlus)
  const adxTrend = input.adx != null && input.adx >= 20
  const longStr = (plusLeads ? 10 : 0) + (plusLeads && adxTrend ? 10 : 0)
  const shortStr = (minusLeads ? 10 : 0) + (minusLeads && adxTrend ? 10 : 0)
  const bull = input.close > input.open
  const bear = input.close < input.open
  const rel = input.relVol
  const longVol = bull && rel != null && rel >= 1.5 ? 20 : bull && rel != null && rel >= 1 ? 12 : bull ? 6 : 0
  const shortVol = bear && rel != null && rel >= 1.5 ? 20 : bear && rel != null && rel >= 1 ? 12 : bear ? 6 : 0
  const long: Factors = { trend: longTrend, momentum: longMom, strength: longStr, volume: longVol, htf: htfPoints(input.htf, "long") }
  const short: Factors = { trend: shortTrend, momentum: shortMom, strength: shortStr, volume: shortVol, htf: htfPoints(input.htf, "short") }
  return {
    long,
    short,
    longScore: long.trend + long.momentum + long.strength + long.volume + long.htf,
    shortScore: short.trend + short.momentum + short.strength + short.volume + short.htf,
  }
}

export function regimeOf(input: {
  close: number
  emaSlow: number | null
  emaSlowPast: number | null
  adx: number | null
  atrPercentile: number | null
}): Regime {
  if (input.atrPercentile != null && input.atrPercentile >= 90) return "HIGH_VOLATILITY"
  const trending = input.adx != null && input.adx >= 20
  const rising = gt(input.emaSlow, input.emaSlowPast)
  const falling = lt(input.emaSlow, input.emaSlowPast)
  if (gt(input.close, input.emaSlow) && rising && trending) return "TREND_UP"
  if (lt(input.close, input.emaSlow) && falling && trending) return "TREND_DOWN"
  return "RANGE"
}

/** Risk map from the signal close. Long stop is entry − 1.5×ATR; targets are 1.5R and 3R. */
export function riskMap(side: "LONG" | "SHORT", close: number, atrValue: number): { entry: number; stop: number; target1: number; target2: number } {
  const entry = close
  if (side === "LONG") {
    const stop = close - STOP_ATR * atrValue
    const risk = entry - stop
    return { entry, stop, target1: entry + TARGET_1_R * risk, target2: entry + TARGET_2_R * risk }
  }
  const stop = close + STOP_ATR * atrValue
  const risk = stop - entry
  return { entry, stop, target1: entry - TARGET_1_R * risk, target2: entry - TARGET_2_R * risk }
}

export function nextTrade(state: TradeState, step: TradeStep): { state: TradeState; event: EventName; actions: Action[] } {
  const next: TradeState = { ...state }
  const actions: Action[] = []
  const statusBefore = state.status
  let openedLong = false
  let openedShort = false
  const longCond =
    step.longScore >= THRESHOLD &&
    step.prevLong != null &&
    step.prevLong < THRESHOLD &&
    step.regime !== "TREND_DOWN" &&
    step.regime !== "HIGH_VOLATILITY"
  const shortCond =
    step.shortScore >= THRESHOLD &&
    step.prevShort != null &&
    step.prevShort < THRESHOLD &&
    step.regime !== "TREND_UP" &&
    step.regime !== "HIGH_VOLATILITY"
  const longSig = longCond && !shortCond
  const shortSig = shortCond && !longCond

  if (next.side !== 0 && next.bar != null && step.index > next.bar && next.stop != null && next.t1 != null && next.t2 != null) {
    if (next.side === 1) {
      if (step.low <= next.stop) {
        const reason = next.status === "TARGET_1_HIT" ? "STOPPED_AFTER_T1" : "STOPPED"
        actions.push({ type: "exit", reason, price: next.stop })
        next.status = reason
        next.side = 0
      } else if (step.high >= next.t2) {
        actions.push({ type: "exit", reason: "TARGET_2_HIT", price: next.t2 })
        next.status = "TARGET_2_HIT"
        next.side = 0
      } else if (step.high >= next.t1 && next.status === "ACTIVE") {
        next.status = "TARGET_1_HIT"
      }
    } else if (step.high >= next.stop) {
      const reason = next.status === "TARGET_1_HIT" ? "STOPPED_AFTER_T1" : "STOPPED"
      actions.push({ type: "exit", reason, price: next.stop })
      next.status = reason
      next.side = 0
    } else if (step.low <= next.t2) {
      actions.push({ type: "exit", reason: "TARGET_2_HIT", price: next.t2 })
      next.status = "TARGET_2_HIT"
      next.side = 0
    } else if (step.low <= next.t1 && next.status === "ACTIVE") {
      next.status = "TARGET_1_HIT"
    }
  }

  const atrValue = step.atr
  if (longSig && next.side !== 1 && atrValue != null && atrValue > 0) {
    if (next.side !== 0 && next.stop != null) {
      actions.push({ type: "exit", reason: "REPLACED", price: step.close })
    }
    const map = riskMap("LONG", step.close, atrValue)
    openedLong = true
    next.side = 1
    next.sideStr = "LONG"
    next.entry = map.entry
    next.stop = map.stop
    next.t1 = map.target1
    next.t2 = map.target2
    next.bar = step.index
    next.status = "ACTIVE"
    next.lastSigBar = step.index
    next.lastSigSide = "LONG"
    actions.push({ type: "open", side: "LONG", entry: map.entry, stop: map.stop, target1: map.target1, target2: map.target2 })
  } else if (shortSig && next.side !== -1 && atrValue != null && atrValue > 0) {
    if (next.side !== 0 && next.stop != null) {
      actions.push({ type: "exit", reason: "REPLACED", price: step.close })
    }
    const map = riskMap("SHORT", step.close, atrValue)
    openedShort = true
    next.side = -1
    next.sideStr = "SHORT"
    next.entry = map.entry
    next.stop = map.stop
    next.t1 = map.target1
    next.t2 = map.target2
    next.bar = step.index
    next.status = "ACTIVE"
    next.lastSigBar = step.index
    next.lastSigSide = "SHORT"
    actions.push({ type: "open", side: "SHORT", entry: map.entry, stop: map.stop, target1: map.target1, target2: map.target2 })
  }

  const tradeUpdate = next.status !== statusBefore && !openedLong && !openedShort
  const event: EventName = openedLong ? "LONG_SETUP" : openedShort ? "SHORT_SETUP" : tradeUpdate ? "TRADE_UPDATE" : "BAR_CLOSE"
  return { state: next, event, actions }
}

function direction(open: number, close: number): "bull" | "bear" | "flat" {
  if (close > open) return "bull"
  if (close < open) return "bear"
  return "flat"
}

function anatomy(bar: Bar, atrValue: number | null, previous: Bar | null) {
  const range = bar.high - bar.low
  const pattern = candlePattern(bar, previous, atrValue)
  return {
    direction: direction(bar.open, bar.close),
    body_pct: range > 0 ? (Math.abs(bar.close - bar.open) / range) * 100 : 0,
    upper_wick_pct: range > 0 ? ((bar.high - Math.max(bar.open, bar.close)) / range) * 100 : 0,
    lower_wick_pct: range > 0 ? ((Math.min(bar.open, bar.close) - bar.low) / range) * 100 : 0,
    range_atr: atrValue != null && atrValue > 0 ? range / atrValue : null,
    close_position_pct: range > 0 ? ((bar.close - bar.low) / range) * 100 : 50,
    gap_pct: previous && previous.close > 0 ? ((bar.open - previous.close) / previous.close) * 100 : null,
    closed_above_prev_high: previous ? bar.close > previous.high : false,
    closed_below_prev_low: previous ? bar.close < previous.low : false,
    pattern,
  }
}

function yearVwap(bars: Bar[]): (number | null)[] {
  let year = ""
  let priceVolume = 0
  let volume = 0
  return bars.map((bar) => {
    const nextYear = bar.date.slice(0, 4)
    if (nextYear !== year) {
      year = nextYear
      priceVolume = 0
      volume = 0
    }
    if (bar.volume != null && bar.volume > 0) {
      const typical = (bar.high + bar.low + bar.close) / 3
      priceVolume += typical * bar.volume
      volume += bar.volume
    }
    return volume > 0 ? priceVolume / volume : null
  })
}

export type LensRun = {
  packets: Packet[]
  actions: Action[][]
  emaFast: (number | null)[]
  emaMid: (number | null)[]
  emaSlow: (number | null)[]
}

export function runLens(bars: Bar[], symbol: string): LensRun {
  const closes = bars.map((bar) => bar.close)
  const highs = bars.map((bar) => bar.high)
  const lows = bars.map((bar) => bar.low)
  const volumes = bars.map((bar) => (bar.volume != null && bar.volume > 0 ? bar.volume : null))
  const emaFast = ema(closes, 20)
  const emaMid = ema(closes, 50)
  const emaSlow = ema(closes, 200)
  const rsiValues = rsi(closes, 14)
  const macdHist = macd(closes, 12, 26, 9).hist
  const atrValues = atr(highs, lows, closes, 14)
  const atrPct = percentRank(atrValues, 100)
  const directional = dmi(highs, lows, closes, 14)
  const volAvg = sma(volumes, 20)
  const relVol = volumes.map((value, index) => {
    const average = volAvg[index]
    if (value == null || average == null || average <= 0) return null
    return value / average
  })
  const htf = weeklyBias(bars, 50)
  const vwap = yearVwap(bars)
  const swingHigh = pivots(highs, SWING, "high")
  const swingLow = pivots(lows, SWING, "low")

  let swingH1: number | null = null
  let swingH2: number | null = null
  let swingL1: number | null = null
  let swingL2: number | null = null
  let trade = initialTrade()
  const packets: Packet[] = []
  const actions: Action[][] = []
  const recent: Packet["recent_candles"][number][] = []

  for (let index = 0; index < bars.length; index++) {
    const bar = bars[index]!
    const previous = index > 0 ? bars[index - 1]! : null
    const atrValue = atrValues[index] ?? null
    const scored = scoreFactors({
      open: bar.open,
      close: bar.close,
      emaFast: emaFast[index] ?? null,
      emaMid: emaMid[index] ?? null,
      emaSlow: emaSlow[index] ?? null,
      rsi: rsiValues[index] ?? null,
      macdHist: macdHist[index] ?? null,
      prevMacdHist: index > 0 ? (macdHist[index - 1] ?? null) : null,
      diPlus: directional.plus[index] ?? null,
      diMinus: directional.minus[index] ?? null,
      adx: directional.adx[index] ?? null,
      relVol: relVol[index] ?? null,
      htf: htf[index]!.bias,
    })
    const regime = regimeOf({
      close: bar.close,
      emaSlow: emaSlow[index] ?? null,
      emaSlowPast: index >= SLOPE ? (emaSlow[index - SLOPE] ?? null) : null,
      adx: directional.adx[index] ?? null,
      atrPercentile: atrPct[index] ?? null,
    })
    const stepped = nextTrade(trade, {
      index,
      high: bar.high,
      low: bar.low,
      close: bar.close,
      atr: atrValue,
      longScore: scored.longScore,
      prevLong: index > 0 ? packets[index - 1]!.scores.long : null,
      shortScore: scored.shortScore,
      prevShort: index > 0 ? packets[index - 1]!.scores.short : null,
      regime,
    })
    trade = stepped.state
    actions.push(stepped.actions)

    const confirmedHigh = swingHigh[index] ?? null
    const confirmedLow = swingLow[index] ?? null
    if (confirmedHigh != null) {
      swingH2 = swingH1
      swingH1 = confirmedHigh
    }
    if (confirmedLow != null) {
      swingL2 = swingL1
      swingL1 = confirmedLow
    }
    const structBias: Packet["structure"]["bias"] =
      gt(swingH1, swingH2) && gt(swingL1, swingL2) ? "BULLISH" : lt(swingH1, swingH2) && lt(swingL1, swingL2) ? "BEARISH" : "MIXED"
    const previousClose = previous?.close ?? null
    const breakUp = swingH1 != null && previousClose != null && bar.close > swingH1 && previousClose <= swingH1
    const breakDown = swingL1 != null && previousClose != null && bar.close < swingL1 && previousClose >= swingL1
    const body = anatomy(bar, atrValue, previous)
    const candle: Candle = bar
    const recentRow = {
      bars_ago: 0,
      o: candle.open,
      h: candle.high,
      l: candle.low,
      c: candle.close,
      v: bar.volume != null && bar.volume > 0 ? bar.volume : null,
      dir: body.direction,
      body_pct: body.body_pct,
      range_atr: body.range_atr,
      pattern: body.pattern,
    }
    recent.push(recentRow)
    const window = recent.slice(-RECENT).map((row, offset, all) => ({ ...row, bars_ago: all.length - 1 - offset }))
    const fast = emaFast[index] ?? null
    const mid = emaMid[index] ?? null
    const slow = emaSlow[index] ?? null
    const slowPast = index >= SLOPE ? (emaSlow[index - SLOPE] ?? null) : null
    const stack: Packet["trend"]["stack"] =
      gt(fast, mid) && gt(mid, slow) ? "BULLISH" : lt(fast, mid) && lt(mid, slow) ? "BEARISH" : "MIXED"
    const slope: Packet["trend"]["slow_slope"] = gt(slow, slowPast) ? "RISING" : lt(slow, slowPast) ? "FALLING" : "FLAT"
    const hist = macdHist[index] ?? null
    const prevHist = index > 0 ? (macdHist[index - 1] ?? null) : null
    packets.push({
      schema: "ai-agent-lens/v1",
      event: stepped.event,
      symbol,
      timeframe: "D",
      time: `${bar.date}T00:00:00Z`,
      state_code: `LENS|${symbol}|D|${regime}|L${scored.longScore}|S${scored.shortScore}|${trade.sideStr}:${trade.status}`,
      candle: {
        open: bar.open,
        high: bar.high,
        low: bar.low,
        close: bar.close,
        volume: bar.volume != null && bar.volume > 0 ? bar.volume : null,
        ...body,
      },
      recent_candles: window,
      regime,
      trend: {
        ema_fast: fast,
        ema_mid: mid,
        ema_slow: slow,
        stack,
        slow_slope: slope,
        htf: "W",
        htf_bias: htf[index]!.bias,
      },
      momentum: { rsi: rsiValues[index] ?? null, macd_hist: hist, macd_hist_rising: gt(hist, prevHist) },
      strength: {
        adx: directional.adx[index] ?? null,
        di_plus: directional.plus[index] ?? null,
        di_minus: directional.minus[index] ?? null,
      },
      volatility: { atr: atrValue, atr_percentile: atrPct[index] ?? null },
      volume: { relative: relVol[index] ?? null },
      structure: {
        bias: structBias,
        event: breakUp ? "BREAK_UP" : breakDown ? "BREAK_DOWN" : "NONE",
        last_swing_high: swingH1,
        last_swing_low: swingL1,
      },
      levels: {
        prev_day_high: previous?.high ?? null,
        prev_day_low: previous?.low ?? null,
        vwap: vwap[index] ?? null,
      },
      scores: {
        long: scored.longScore,
        short: scored.shortScore,
        threshold: THRESHOLD,
        long_factors: scored.long,
        short_factors: scored.short,
      },
      trade: {
        side: trade.sideStr,
        status: trade.status,
        entry: trade.entry,
        stop: trade.stop,
        target_1: trade.t1,
        target_2: trade.t2,
        bars_since_entry: trade.bar == null ? null : index - trade.bar,
      },
      last_setup: {
        side: trade.lastSigSide,
        bars_ago: trade.lastSigBar == null ? null : index - trade.lastSigBar,
      },
    })
  }

  return { packets, actions, emaFast, emaMid, emaSlow }
}
