// Candle patterns in the Pine `f_pattern` order.
// First match wins. Ported from ai-agent-lens.pine (MIT, © 2026 roan-maverick).

export type Candle = {
  open: number
  high: number
  low: number
  close: number
}

export type Pattern =
  | "FLAT"
  | "BULLISH_ENGULFING"
  | "BEARISH_ENGULFING"
  | "DOJI"
  | "HAMMER"
  | "SHOOTING_STAR"
  | "BULLISH_MARUBOZU"
  | "BEARISH_MARUBOZU"
  | "INSIDE_BAR"
  | "OUTSIDE_BAR"
  | "WIDE_RANGE_BULL"
  | "WIDE_RANGE_BEAR"
  | "NONE"

export function candlePattern(current: Candle, previous: Candle | null, atr: number | null): Pattern {
  const range = current.high - current.low
  const body = Math.abs(current.close - current.open)
  const upper = current.high - Math.max(current.open, current.close)
  const lower = Math.min(current.open, current.close) - current.low
  if (range <= 0) return "FLAT"
  if (
    previous &&
    current.close > current.open &&
    previous.close < previous.open &&
    current.close >= previous.open &&
    current.open <= previous.close
  ) {
    return "BULLISH_ENGULFING"
  }
  if (
    previous &&
    current.close < current.open &&
    previous.close > previous.open &&
    current.open >= previous.close &&
    current.close <= previous.open
  ) {
    return "BEARISH_ENGULFING"
  }
  if (body / range <= 0.1) return "DOJI"
  if (lower >= 2 * body && upper <= 0.15 * range) return "HAMMER"
  if (upper >= 2 * body && lower <= 0.15 * range) return "SHOOTING_STAR"
  if (body / range >= 0.9) return current.close > current.open ? "BULLISH_MARUBOZU" : "BEARISH_MARUBOZU"
  if (previous && current.high < previous.high && current.low > previous.low) return "INSIDE_BAR"
  if (previous && current.high > previous.high && current.low < previous.low) return "OUTSIDE_BAR"
  if (atr != null && atr > 0 && range >= 1.8 * atr) {
    return current.close > current.open ? "WIDE_RANGE_BULL" : "WIDE_RANGE_BEAR"
  }
  return "NONE"
}
