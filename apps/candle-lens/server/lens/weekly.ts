// Daily-data higher timeframe: a fully closed week, the Pine `[1] + lookahead_on` rule.
// The week that contains the bar is never used. Weekly EMA is computed on closed weeks only.

import { ema } from "./indicators.ts"

export type DatedClose = { date: string; close: number }

export type HtfBias = "UP" | "DOWN" | "FLAT" | "N/A"

export type HtfPoint = {
  close: number | null
  ema: number | null
  bias: HtfBias
}

/** Monday (UTC) of the week containing `YYYY-MM-DD`. */
export function weekStart(date: string): string {
  const day = new Date(`${date}T00:00:00Z`)
  const weekday = day.getUTCDay()
  const back = weekday === 0 ? 6 : weekday - 1
  day.setUTCDate(day.getUTCDate() - back)
  return day.toISOString().slice(0, 10)
}

type Week = { key: string; close: number }

/**
 * For each daily bar, the previous fully closed week's close and EMA.
 * A week closes when the next week starts, so Friday still sees the prior week.
 */
export function weeklyBias(bars: DatedClose[], emaLength: number): HtfPoint[] {
  const weeks: Week[] = []
  const weekIndex: number[] = []
  for (const bar of bars) {
    const key = weekStart(bar.date)
    const last = weeks[weeks.length - 1]
    if (last && last.key === key) last.close = bar.close
    else weeks.push({ key, close: bar.close })
    weekIndex.push(weeks.length - 1)
  }
  const weekEma = ema(
    weeks.map((week) => week.close),
    emaLength,
  )
  return bars.map((_, index) => {
    const previous = weekIndex[index]! - 1
    if (previous < 0) return { close: null, ema: null, bias: "FLAT" as const }
    const close = weeks[previous]!.close
    const average = weekEma[previous] ?? null
    return { close, ema: average, bias: biasOf(close, average) }
  })
}

export function biasOf(close: number | null, average: number | null): HtfBias {
  if (close == null || average == null) return "FLAT"
  if (close > average) return "UP"
  if (close < average) return "DOWN"
  return "FLAT"
}

/** Higher-timeframe factor. FLAT and N/A are both 10, matching the Pine ternary. */
export function htfPoints(bias: HtfBias, side: "long" | "short"): number {
  if (side === "long") return bias === "UP" ? 20 : bias === "DOWN" ? 0 : 10
  return bias === "DOWN" ? 20 : bias === "UP" ? 0 : 10
}
