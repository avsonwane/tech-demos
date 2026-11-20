import { expect, test } from "bun:test"
import { readFileSync } from "node:fs"
import { join } from "node:path"
import { indiaRates, runBacktest, type CostModel } from "../lens/backtest.ts"
import type { Action, Bar } from "../lens/packet.ts"

test("India delivery rates match the vibe-trading schedule", () => {
  const { buyRate, sellRate } = indiaRates()
  const gst = (0.0000297 + 0.000001) * 0.18
  expect(buyRate).toBeCloseTo(0.0000297 + 0.000001 + gst + 0.001 + 0.00015, 12)
  expect(sellRate).toBeCloseTo(0.0000297 + 0.000001 + gst + 0.001, 12)
})

test("buy-and-hold uses the evaluation window, not the warmup close", () => {
  const costs = zeroCosts()
  const bars = [bar("2023-12-29", 50), bar("2024-01-02", 100), bar("2024-06-03", 100), bar("2024-12-31", 90)]
  const reality = runBacktest(bars, bars.map(() => []), "RELIANCE.NS", "2024-01-02", "2024-12-31", costs)
  expect(reality.buyHold.returnPct).toBeCloseTo(-10, 8)
  expect(reality.strategy.returnPct).toBeCloseTo(0, 8)
  expect(reality.strategy.tradeCount).toBe(0)
  expect(reality.buyHold.tradeCount).toBe(1)
})

test("entry, stop, and target fills include slippage, and the stop is the exit when both are touched", () => {
  const costs: CostModel = { ...zeroCosts(), slippage: 0.001, buyRate: 0.001, sellRate: 0.001, currency: "USD" }
  const bars = [bar("2024-01-02", 100), bar("2024-01-03", 100, 80, 130)]
  const actions: Action[][] = [
    [{ type: "open", side: "LONG", entry: 100, stop: 90, target1: 115, target2: 130 }],
    [{ type: "exit", reason: "STOPPED", price: 90 }],
  ]
  const reality = runBacktest(bars, actions, "BTC-USD", "2024-01-02", "2024-01-03", costs)
  const shares = 100_000 / (100 * 1.001 * 1.001)
  const stopFill = 90 * 0.999
  const end = shares * stopFill * (1 - 0.001)
  expect(reality.strategy.endingEquity).toBeCloseTo(end, 6)
  expect(reality.strategy.fees).toBeCloseTo(shares * 100 * 1.001 * 0.001 + shares * stopFill * 0.001, 4)
  expect(reality.strategy.tradeCount).toBe(1)
  expect(reality.currency).toBe("USD")
})

test("RELIANCE.NS 2024 buy-and-hold after India fees is about -6.23%", () => {
  const fixture = JSON.parse(readFileSync(join(import.meta.dir, "..", "fixtures", "RELIANCE.NS.json"), "utf8")) as { bars: Bar[] }
  const actions = fixture.bars.map(() => [] as Action[])
  const reality = runBacktest(fixture.bars, actions, "RELIANCE.NS", "2024-01-01", "2024-12-31")
  expect(reality.buyHold.returnPct).toBeCloseTo(-6.23, 2)
  expect(reality.capital).toBe(100_000)
  expect(reality.currency).toBe("INR")
  expect(reality.feeNote).toContain("Pine trade tracker itself has no fees")
})

function zeroCosts(): CostModel {
  return { slippage: 0, buyRate: 0, sellRate: 0, capital: 100_000, currency: "INR", note: "zero" }
}

function bar(date: string, close: number, low = close, high = close): Bar {
  return { date, open: close, high, low, close, volume: 1 }
}
