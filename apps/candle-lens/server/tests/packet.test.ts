import { expect, test } from "bun:test"
import { initialTrade, nextTrade, regimeOf, riskMap, runLens, scoreFactors, type Bar } from "../lens/packet.ts"
import { weekStart, weeklyBias } from "../lens/weekly.ts"

test("score factors and the na relative-volume ternary", () => {
  const aligned = scoreFactors({
    open: 10,
    close: 12,
    emaFast: 11,
    emaMid: 10,
    emaSlow: 9,
    rsi: 60,
    macdHist: 0.2,
    prevMacdHist: 0.1,
    diPlus: 30,
    diMinus: 10,
    adx: 25,
    relVol: 1.5,
    htf: "UP",
  })
  expect(aligned.long).toEqual({ trend: 20, momentum: 20, strength: 20, volume: 20, htf: 20 })
  expect(aligned.longScore).toBe(100)
  expect(aligned.shortScore).toBe(0)

  const hot = scoreFactors({ ...blank(), close: 12, open: 10, rsi: 80, macdHist: 0.2, prevMacdHist: 0.1, relVol: 1 })
  expect(hot.long.momentum).toBe(14)
  expect(hot.long.volume).toBe(12)
  const quiet = scoreFactors({ ...blank(), close: 12, open: 10, relVol: 0.4 })
  expect(quiet.long.volume).toBe(6)
  const missing = scoreFactors({ ...blank(), close: 12, open: 10, relVol: null })
  expect(missing.long.volume).toBe(6)
  const oversold = scoreFactors({ ...blank(), close: 8, open: 10, rsi: 20, macdHist: -0.2, prevMacdHist: -0.1, relVol: 2, htf: "DOWN" })
  expect(oversold.short.momentum).toBe(14)
  expect(oversold.short.volume).toBe(20)
  expect(oversold.short.htf).toBe(20)
  const flat = scoreFactors({ ...blank(), htf: "FLAT" })
  const unavailable = scoreFactors({ ...blank(), htf: "N/A" })
  expect(flat.long.htf).toBe(10)
  expect(unavailable.short.htf).toBe(10)
})

test("regime checks high volatility before either trend", () => {
  const trend = { close: 12, emaSlow: 10, emaSlowPast: 9, adx: 25, atrPercentile: 89 }
  expect(regimeOf(trend)).toBe("TREND_UP")
  expect(regimeOf({ ...trend, atrPercentile: 90 })).toBe("HIGH_VOLATILITY")
  expect(regimeOf({ close: 8, emaSlow: 10, emaSlowPast: 11, adx: 25, atrPercentile: 10 })).toBe("TREND_DOWN")
  expect(regimeOf({ close: 10, emaSlow: 10, emaSlowPast: 10, adx: 25, atrPercentile: 10 })).toBe("RANGE")
})

test("risk map is 1.5 ATR, then 1.5R and 3R", () => {
  expect(riskMap("LONG", 100, 2)).toEqual({ entry: 100, stop: 97, target1: 104.5, target2: 109 })
  expect(riskMap("SHORT", 100, 2)).toEqual({ entry: 100, stop: 103, target1: 95.5, target2: 91 })
})

test("a 70-cross opens one trade, ignores the same side, and an opposite setup replaces it", () => {
  let state = initialTrade()
  const opened = nextTrade(state, step(0, { longScore: 72, prevLong: 69, shortScore: 10, prevShort: 10 }))
  expect(opened.event).toBe("LONG_SETUP")
  expect(opened.actions.map((action) => action.type)).toEqual(["open"])
  expect(opened.state.stop).toBe(97)
  state = opened.state

  const held = nextTrade(state, step(1, { longScore: 90, prevLong: 80, low: 99, high: 101 }))
  expect(held.event).toBe("BAR_CLOSE")
  expect(held.actions).toHaveLength(0)
  state = held.state

  const ignored = nextTrade(state, step(2, { longScore: 75, prevLong: 60, low: 99, high: 101 }))
  expect(ignored.event).toBe("BAR_CLOSE")
  expect(ignored.state.side).toBe(1)

  const both = nextTrade(state, step(3, { longScore: 80, prevLong: 60, shortScore: 80, prevShort: 60, low: 99, high: 101 }))
  expect(both.event).toBe("BAR_CLOSE")
  expect(both.actions).toHaveLength(0)

  const blocked = nextTrade(initialTrade(), step(0, { longScore: 80, prevLong: 60, regime: "TREND_DOWN" }))
  expect(blocked.event).toBe("BAR_CLOSE")
  const volatile = nextTrade(initialTrade(), step(0, { longScore: 80, prevLong: 60, regime: "HIGH_VOLATILITY" }))
  expect(volatile.event).toBe("BAR_CLOSE")
  const first = nextTrade(initialTrade(), step(0, { longScore: 80, prevLong: null }))
  expect(first.event).toBe("BAR_CLOSE")

  const replaced = nextTrade(state, step(4, { shortScore: 80, prevShort: 50, longScore: 40, prevLong: 40, low: 99, high: 101 }))
  expect(replaced.event).toBe("SHORT_SETUP")
  expect(replaced.actions.map((action) => action.type)).toEqual(["exit", "open"])
  expect(replaced.state.sideStr).toBe("SHORT")
  expect(replaced.state.status).toBe("ACTIVE")
})

test("the stop is checked before the targets", () => {
  const opened = nextTrade(initialTrade(), step(0, { longScore: 80, prevLong: 60 }))
  const stopped = nextTrade(opened.state, step(1, { low: 90, high: 120, longScore: 40, prevLong: 80 }))
  expect(stopped.actions).toEqual([{ type: "exit", reason: "STOPPED", price: 97 }])
  expect(stopped.state.side).toBe(0)
  expect(stopped.state.sideStr).toBe("LONG")
  expect(stopped.state.status).toBe("STOPPED")

  const touched = nextTrade(opened.state, step(1, { low: 99, high: 105, longScore: 40, prevLong: 80 }))
  expect(touched.event).toBe("TRADE_UPDATE")
  expect(touched.state.status).toBe("TARGET_1_HIT")
  expect(touched.actions).toHaveLength(0)
  const after = nextTrade(touched.state, step(2, { low: 90, high: 100, longScore: 40, prevLong: 40 }))
  expect(after.state.status).toBe("STOPPED_AFTER_T1")
})

test("a swing high is published five bars later and is not revised", () => {
  const bars: Bar[] = []
  for (let index = 0; index < 30; index++) {
    const high = index === 10 ? 50 : 20
    const low = index === 6 ? 4 : 10
    bars.push({ date: `2024-02-${String(index + 1).padStart(2, "0")}`, open: 15, high, low, close: 15, volume: 100 })
  }
  const { packets } = runLens(bars, "TEST")
  expect(packets[14]!.structure.last_swing_high).toBeNull()
  expect(packets[15]!.structure.last_swing_high).toBe(50)
  expect(packets[20]!.structure.last_swing_high).toBe(50)
  expect(packets[11]!.structure.last_swing_low).toBe(4)
})

test("weekly bias uses the previous closed week and not the week still forming", () => {
  expect(weekStart("2024-01-05")).toBe("2024-01-01")
  expect(weekStart("2024-01-08")).toBe("2024-01-08")
  const bars = [
    day("2024-01-01", 10),
    day("2024-01-05", 10),
    day("2024-01-08", 20),
    day("2024-01-12", 30),
    day("2024-01-15", 40),
  ]
  const bias = weeklyBias(bars, 2)
  expect(bias[1]).toMatchObject({ close: null, bias: "FLAT" })
  expect(bias[2]).toMatchObject({ close: 10, bias: "FLAT" })
  expect(bias[3]).toMatchObject({ close: 10 })
  expect(bias[3]!.close).not.toBe(30)
  expect(bias[4]).toMatchObject({ close: 30, ema: 20, bias: "UP" })
  expect(bias[4]!.close).not.toBe(40)
})

function blank() {
  return {
    open: 10,
    close: 10,
    emaFast: null,
    emaMid: null,
    emaSlow: null,
    rsi: null,
    macdHist: null,
    prevMacdHist: null,
    diPlus: null,
    diMinus: null,
    adx: null,
    relVol: null,
    htf: "FLAT" as const,
  }
}

function step(index: number, patch: Partial<Parameters<typeof nextTrade>[1]> = {}) {
  return {
    index,
    high: 101,
    low: 99,
    close: 100,
    atr: 2,
    longScore: 40,
    prevLong: 40,
    shortScore: 10,
    prevShort: 10,
    regime: "RANGE" as const,
    ...patch,
  }
}

function day(date: string, close: number) {
  return { date, close }
}
