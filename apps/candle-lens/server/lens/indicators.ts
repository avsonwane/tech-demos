// Pine ta.* equivalents for AI Agent Lens.
// Ported from ai-agent-lens.pine (MIT, © 2026 roan-maverick).
// https://github.com/roan-maverick/tradingview-indicator-for-ai-agents

export type Series = (number | null)[]

/** Pine `ta.sma`. Null when the window is short or contains a null. */
export function sma(values: Series, length: number): Series {
  return values.map((_, index) => {
    if (index < length - 1) return null
    let sum = 0
    for (let cursor = index - length + 1; cursor <= index; cursor++) {
      const value = values[cursor]
      if (value == null) return null
      sum += value
    }
    return sum / length
  })
}

/**
 * Pine `ta.ema`: SMA seed, then α = 2 / (length + 1).
 * A null previous value reseeds from the current window, matching `na(ema[1]) ? sma : ...`.
 */
export function ema(values: Series, length: number): Series {
  return smooth(values, length, 2 / (length + 1))
}

/** Pine `ta.rma`: SMA seed, then α = 1 / length. Used by RSI, ATR, and DMI. */
export function rma(values: Series, length: number): Series {
  return smooth(values, length, 1 / length)
}

function smooth(values: Series, length: number, alpha: number): Series {
  const out: Series = Array(values.length).fill(null)
  for (let index = 0; index < values.length; index++) {
    const previous = index > 0 ? out[index - 1] : null
    const value = values[index]
    if (previous != null && value != null) {
      out[index] = alpha * value + (1 - alpha) * previous
      continue
    }
    if (index < length - 1) continue
    let sum = 0
    let ok = true
    for (let cursor = index - length + 1; cursor <= index; cursor++) {
      const sample = values[cursor]
      if (sample == null) {
        ok = false
        break
      }
      sum += sample
    }
    if (ok) out[index] = sum / length
  }
  return out
}

/** Pine `ta.rsi`. The first change is null, so the RMA seed starts one bar later. */
export function rsi(closes: number[], length: number): Series {
  const change: Series = closes.map((close, index) => (index === 0 ? null : close - closes[index - 1]!))
  const gains = change.map((value) => (value == null ? null : Math.max(value, 0)))
  const losses = change.map((value) => (value == null ? null : Math.max(-value, 0)))
  const avgGain = rma(gains, length)
  const avgLoss = rma(losses, length)
  return closes.map((_, index) => {
    const gain = avgGain[index]
    const loss = avgLoss[index]
    if (gain == null || loss == null) return null
    if (loss === 0) return 100
    if (gain === 0) return 0
    return 100 - 100 / (1 + gain / loss)
  })
}

/** Pine `ta.macd`: EMA fast − EMA slow, signal EMA, histogram. */
export function macd(
  closes: number[],
  fast: number,
  slow: number,
  signal: number,
): { line: Series; signal: Series; hist: Series } {
  const fastEma = ema(closes, fast)
  const slowEma = ema(closes, slow)
  const line = closes.map((_, index) => {
    const fastValue = fastEma[index]
    const slowValue = slowEma[index]
    if (fastValue == null || slowValue == null) return null
    return fastValue - slowValue
  })
  const signalLine = ema(line, signal)
  const hist = line.map((value, index) => {
    const signalValue = signalLine[index]
    if (value == null || signalValue == null) return null
    return value - signalValue
  })
  return { line, signal: signalLine, hist }
}

/** Pine `ta.tr` then `ta.atr`. The first bar's true range is high − low. */
export function trueRange(highs: number[], lows: number[], closes: number[]): number[] {
  return highs.map((high, index) => {
    const range = high - lows[index]!
    if (index === 0) return range
    const previous = closes[index - 1]!
    return Math.max(range, Math.abs(high - previous), Math.abs(lows[index]! - previous))
  })
}

export function atr(highs: number[], lows: number[], closes: number[], length: number): Series {
  return rma(trueRange(highs, lows, closes), length)
}

/**
 * Pine `ta.percentrank`: percent of the previous `length` values that are `<=` the current value.
 * The current bar is not part of the count. Null history entries do not count; the divisor stays `length`.
 */
export function percentRank(values: Series, length: number): Series {
  return values.map((value, index) => {
    if (value == null || index < length) return null
    let count = 0
    for (let ago = 1; ago <= length; ago++) {
      const previous = values[index - ago]
      if (previous != null && previous <= value) count += 1
    }
    return (100 * count) / length
  })
}

export type Dmi = { plus: Series; minus: Series; adx: Series }

/**
 * Pine `ta.dmi(length, length)`.
 * `ta.change` is null on the first bar, so +DM/−DM seed one bar after true range.
 * `fixnan` holds the last directional index through a gap.
 */
export function dmi(highs: number[], lows: number[], closes: number[], length: number): Dmi {
  const up: Series = highs.map((high, index) => (index === 0 ? null : high - highs[index - 1]!))
  const down: Series = lows.map((low, index) => (index === 0 ? null : lows[index - 1]! - low))
  const plusDm: Series = up.map((value, index) => {
    if (value == null) return null
    const downMove = down[index]
    if (downMove == null) return null
    return value > downMove && value > 0 ? value : 0
  })
  const minusDm: Series = down.map((value, index) => {
    if (value == null) return null
    const upMove = up[index]
    if (upMove == null) return null
    return value > upMove && value > 0 ? value : 0
  })
  const trur = rma(trueRange(highs, lows, closes), length)
  const plusRma = rma(plusDm, length)
  const minusRma = rma(minusDm, length)
  const rawPlus = ratio(plusRma, trur)
  const rawMinus = ratio(minusRma, trur)
  const plus = fixnan(rawPlus)
  const minus = fixnan(rawMinus)
  const dx: Series = plus.map((plusValue, index) => {
    const minusValue = minus[index]
    if (plusValue == null || minusValue == null) return null
    const sum = plusValue + minusValue
    return Math.abs(plusValue - minusValue) / (sum === 0 ? 1 : sum)
  })
  const adx = rma(dx, length).map((value) => (value == null ? null : 100 * value))
  return { plus, minus, adx }
}

function ratio(numerator: Series, denominator: Series): Series {
  return numerator.map((value, index) => {
    const base = denominator[index]
    if (value == null || base == null || base === 0) return null
    return (100 * value) / base
  })
}

function fixnan(values: Series): Series {
  let last: number | null = null
  return values.map((value) => {
    if (value != null && Number.isFinite(value)) {
      last = value
      return value
    }
    return last
  })
}

/** Confirmed pivots. The value is published `strength` bars after the pivot and never revised. */
export function pivots(values: number[], strength: number, mode: "high" | "low" = "high"): Series {
  const out: Series = Array(values.length).fill(null)
  for (let index = strength; index < values.length - strength; index++) {
    const pivot = values[index]!
    let extreme = true
    for (let offset = 1; offset <= strength; offset++) {
      const left = values[index - offset]!
      const right = values[index + offset]!
      const blocked = mode === "high" ? left >= pivot || right >= pivot : left <= pivot || right <= pivot
      if (blocked) {
        extreme = false
        break
      }
    }
    if (extreme) out[index + strength] = pivot
  }
  return out
}
