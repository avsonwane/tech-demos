import { describe, expect, test } from "bun:test"
import { atr, dmi, ema, macd, percentRank, rsi } from "../lens/indicators.ts"

const closes = [10, 11, 12, 13, 14, 15, 14, 13]
const highs = [11, 12, 13, 14, 15, 16, 15, 14]
const lows = [9, 10, 11, 12, 13, 14, 10, 12]

describe("indicators", () => {
  test("EMA uses an SMA seed and alpha 2 / (length + 1)", () => {
    const values = ema(closes, 3)
    expect(values[2]).toBeCloseTo(11, 8)
    expect(values[3]).toBeCloseTo(12, 8)
    expect(values[5]).toBeCloseTo(14, 8)
    expect(values[6]).toBeCloseTo(14, 8)
    expect(values[7]).toBeCloseTo(13.5, 8)
  })

  test("RSI follows Wilder on the change series", () => {
    const values = rsi(closes, 3)
    expect(values[3]).toBeCloseTo(100, 8)
    expect(values[6]).toBeCloseTo(100 - 100 / 3, 8)
    expect(values[7]).toBeCloseTo(100 - 100 / 1.8, 8)
  })

  test("MACD histogram is the fast/slow EMA difference minus its signal EMA", () => {
    const series = [10, 12, 11, 13, 12, 14]
    const { hist } = macd(series, 2, 3, 2)
    expect(hist[2]).toBeNull()
    expect(hist[3]).toBeCloseTo(1 / 6, 6)
    expect(hist[5]).toBeCloseTo(0.080247, 4)
  })

  test("ATR is Wilder true range, with high-low on the first bar", () => {
    const values = atr(highs, lows, closes, 3)
    expect(values[2]).toBeCloseTo(2, 8)
    expect(values[5]).toBeCloseTo(2, 8)
    expect(values[6]).toBeCloseTo(3, 8)
    expect(values[7]).toBeCloseTo(8 / 3, 8)
  })

  test("DMI seeds directional movement one bar after true range", () => {
    const high = [10, 12, 11, 13, 12]
    const low = [8, 9, 9, 10, 9]
    const close = [9, 11, 10, 12, 11]
    const values = dmi(high, low, close, 2)
    expect(values.plus[2]).toBeCloseTo(100 / 2.25, 6)
    expect(values.minus[2]).toBeCloseTo(0, 6)
    expect(values.adx[2]).toBeNull()
    expect(values.adx[3]).toBeCloseTo(100, 6)
    expect(values.plus[4]).toBeCloseTo(100 * 0.75 / 2.8125, 6)
    expect(values.minus[4]).toBeCloseTo(100 * 0.5 / 2.8125, 6)
    expect(values.adx[4]).toBeCloseTo(60, 6)
  })

  test("percent rank counts earlier values and stays inside 0 to 100", () => {
    const values = percentRank([1, 3, 2, 5, 4], 3)
    expect(values[2]).toBeNull()
    expect(values[3]).toBeCloseTo(100, 8)
    expect(values[4]).toBeCloseTo((200 / 3), 8)
  })
})
