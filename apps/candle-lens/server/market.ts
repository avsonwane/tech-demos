// Daily Yahoo Finance bars. Adjusted OHLC = raw × adjclose / close.
// A shipped RELIANCE.NS fixture is used only when the live fetch fails.

import { mkdirSync, readFileSync, writeFileSync, existsSync } from "node:fs"
import { join } from "node:path"
import type { Bar } from "./lens/packet.ts"

export const SYMBOLS = ["RELIANCE.NS", "^NSEI", "BTC-USD"] as const
export type SymbolId = (typeof SYMBOLS)[number]

const ROOT = import.meta.dir
const CACHE = join(ROOT, ".cache")
const FIXTURE = join(ROOT, "fixtures", "RELIANCE.NS.json")

export function isSymbol(value: string): value is SymbolId {
  return (SYMBOLS as readonly string[]).includes(value)
}

export function warmupStart(start: string): string {
  const day = new Date(`${start}T00:00:00Z`)
  day.setUTCDate(day.getUTCDate() - 2200)
  return day.toISOString().slice(0, 10)
}

export function assertRange(start: string, end: string): void {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(start) || !/^\d{4}-\d{2}-\d{2}$/.test(end)) {
    throw new Error("Dates must be YYYY-MM-DD.")
  }
  if (start > end) throw new Error("The start date is after the end date.")
}

type RawBar = { date: string; open: number; high: number; low: number; close: number; volume: number | null }

export function parseYahoo(payload: unknown): Bar[] {
  const chart = payload as {
    chart?: { result?: { timestamp?: number[]; indicators?: { quote?: { open?: (number | null)[]; high?: (number | null)[]; low?: (number | null)[]; close?: (number | null)[]; volume?: (number | null)[] }[]; adjclose?: { adjclose?: (number | null)[] }[] } }[]; error?: { description?: string } }
  }
  if (chart.chart?.error) throw new Error(chart.chart.error.description || "Yahoo Finance returned an error.")
  const result = chart.chart?.result?.[0]
  const timestamps = result?.timestamp
  const quote = result?.indicators?.quote?.[0]
  const adjusted = result?.indicators?.adjclose?.[0]?.adjclose
  if (!timestamps || !quote) throw new Error("Yahoo Finance returned no candles.")
  const bars: RawBar[] = []
  for (let index = 0; index < timestamps.length; index++) {
    const open = quote.open?.[index]
    const high = quote.high?.[index]
    const low = quote.low?.[index]
    const close = quote.close?.[index]
    if (open == null || high == null || low == null || close == null || close === 0) continue
    const adj = adjusted?.[index]
    const factor = adj != null && Number.isFinite(adj) ? adj / close : 1
    const volume = quote.volume?.[index]
    const date = new Date(timestamps[index]! * 1000).toISOString().slice(0, 10)
    bars.push({
      date,
      open: open * factor,
      high: high * factor,
      low: low * factor,
      close: adj != null && Number.isFinite(adj) ? adj : close,
      volume: volume != null && volume > 0 ? volume : null,
    })
  }
  const deduped = new Map<string, Bar>()
  for (const bar of bars) deduped.set(bar.date, bar)
  return [...deduped.values()].sort((left, right) => (left.date < right.date ? -1 : 1))
}

function readFixture(): Bar[] {
  const parsed = JSON.parse(readFileSync(FIXTURE, "utf8")) as { bars: Bar[] }
  return parsed.bars
}

async function fetchYahoo(symbol: string, start: string, end: string): Promise<Bar[]> {
  const period1 = Math.floor(Date.parse(`${start}T00:00:00Z`) / 1000)
  const period2 = Math.floor(Date.parse(`${end}T00:00:00Z`) / 1000) + 86_400 * 5
  const encoded = encodeURIComponent(symbol)
  const headers = { "User-Agent": "Mozilla/5.0" }
  let last = "Yahoo Finance request failed."
  for (const host of ["query1.finance.yahoo.com", "query2.finance.yahoo.com"]) {
    const url = `https://${host}/v8/finance/chart/${encoded}?period1=${period1}&period2=${period2}&interval=1d&events=div%7Csplit&includeAdjustedClose=true`
    try {
      const response = await fetch(url, { headers, signal: AbortSignal.timeout(20_000) })
      if (!response.ok) {
        last = `Yahoo Finance responded ${response.status}.`
        continue
      }
      return parseYahoo(await response.json())
    } catch (error) {
      last = error instanceof Error ? error.message : last
    }
  }
  throw new Error(last)
}

function cachePath(symbol: string, start: string, end: string): string {
  return join(CACHE, `${encodeURIComponent(symbol)}-${start}-${end}.json`)
}

export async function loadBars(symbol: string, start: string, end: string): Promise<{ bars: Bar[]; source: "yahoo" | "fixture" }> {
  const from = warmupStart(start)
  const file = cachePath(symbol, from, end)
  if (existsSync(file)) {
    const cached = JSON.parse(readFileSync(file, "utf8")) as Bar[]
    return { bars: cached.filter((bar) => bar.date <= end), source: "yahoo" }
  }
  try {
    const bars = (await fetchYahoo(symbol, from, end)).filter((bar) => bar.date >= from && bar.date <= end)
    if (!bars.some((bar) => bar.date >= start && bar.date <= end)) throw new Error("No bars in that window.")
    mkdirSync(CACHE, { recursive: true })
    writeFileSync(file, JSON.stringify(bars))
    return { bars, source: "yahoo" }
  } catch (error) {
    if (symbol !== "RELIANCE.NS") throw error
    const bars = readFixture().filter((bar) => bar.date >= from && bar.date <= end)
    if (!bars.some((bar) => bar.date >= start && bar.date <= end)) throw error
    return { bars, source: "fixture" }
  }
}
