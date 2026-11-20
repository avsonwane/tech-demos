import { expect, test } from "bun:test"
import { candlePattern, type Candle } from "../lens/patterns.ts"

function candle(open: number, high: number, low: number, close: number): Candle {
  return { open, high, low, close }
}

test("patterns follow the Pine priority, including shapes that also match a later rule", () => {
  const bear = candle(5, 5.2, 3.8, 4)
  expect(candlePattern(candle(1, 1, 1, 1), bear, 1)).toBe("FLAT")
  // Engulfing that is also a doji (body under 10% of range).
  expect(candlePattern(candle(3.95, 20, 3, 5.05), bear, 1)).toBe("BULLISH_ENGULFING")
  const bull = candle(4, 5.2, 3.8, 5)
  expect(candlePattern(candle(5.05, 6, 3, 3.95), bull, 1)).toBe("BEARISH_ENGULFING")
  // Doji that would otherwise be a hammer.
  expect(candlePattern(candle(10, 11, 5, 10.2), bull, 1)).toBe("DOJI")
  // Hammer that is also a wide range.
  expect(candlePattern(candle(10, 11.2, 8, 11), bull, 1)).toBe("HAMMER")
  expect(candlePattern(candle(11, 13, 10.8, 10), bull, 1)).toBe("SHOOTING_STAR")
  expect(candlePattern(candle(10, 11, 9.95, 10.95), bull, 10)).toBe("BULLISH_MARUBOZU")
  expect(candlePattern(candle(11, 11.05, 10, 10.05), bull, 10)).toBe("BEARISH_MARUBOZU")
  expect(candlePattern(candle(10.2, 10.8, 9.4, 10.6), candle(10, 11, 9, 10.5), 10)).toBe("INSIDE_BAR")
  // Outside bar that is also a wide range.
  expect(candlePattern(candle(10, 12, 8, 11), candle(10.2, 10.8, 9.5, 10.4), 1)).toBe("OUTSIDE_BAR")
  expect(candlePattern(candle(10, 12, 9.5, 11.5), bull, 1)).toBe("WIDE_RANGE_BULL")
  expect(candlePattern(candle(11.5, 12, 9.5, 10), bull, 1)).toBe("WIDE_RANGE_BEAR")
  expect(candlePattern(candle(10, 11, 9.5, 10.5), candle(10, 11, 9, 10), 2)).toBe("NONE")
})
