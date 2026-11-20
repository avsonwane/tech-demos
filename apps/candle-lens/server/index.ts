import { existsSync, readFileSync } from "node:fs"
import { join } from "node:path"
import { askAgent, healthBody, redact, secretValues, type Env } from "./agent.ts"
import { costModel, runBacktest } from "./lens/backtest.ts"
import { runLens, type Bar } from "./lens/packet.ts"
import { assertRange, isSymbol, loadBars } from "./market.ts"

function loadEnvFile(file: string): void {
  if (!existsSync(file)) return
  for (const line of readFileSync(file, "utf8").split("\n")) {
    const trimmed = line.trim()
    if (!trimmed || trimmed.startsWith("#")) continue
    const eq = trimmed.indexOf("=")
    if (eq < 0) continue
    const key = trimmed.slice(0, eq).trim()
    if (!key || process.env[key] !== undefined) continue
    let value = trimmed.slice(eq + 1).trim()
    if ((value.startsWith("\"") && value.endsWith("\"")) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1)
    }
    process.env[key] = value
  }
}

loadEnvFile(join(import.meta.dir, "..", ".env"))

const env = process.env as Env
const port = Number(process.env.DESK_PORT || 8011)

function log(message: string): void {
  console.log(redact(message, secretValues(env)))
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  })
}

function fail(error: unknown, status = 400): Response {
  const message = error instanceof Error ? error.message : "Request failed."
  return json({ error: redact(message, secretValues(env)) }, status)
}

function desk(symbol: string, start: string, end: string, bars: Bar[], source: "yahoo" | "fixture") {
  const lens = runLens(bars, symbol)
  const visible = bars.map((bar, index) => ({ bar, index })).filter(({ bar }) => bar.date >= start && bar.date <= end)
  const costs = costModel(symbol)
  const reality = runBacktest(bars, lens.actions, symbol, start, end, costs)
  return {
    symbol,
    start,
    end,
    source,
    currency: costs.currency,
    capital: costs.capital,
    feeNote: reality.feeNote,
    bars: visible.map(({ bar }) => bar),
    emaFast: visible.map(({ index }) => lens.emaFast[index] ?? null),
    emaMid: visible.map(({ index }) => lens.emaMid[index] ?? null),
    emaSlow: visible.map(({ index }) => lens.emaSlow[index] ?? null),
    packets: visible.map(({ index }) => lens.packets[index]),
    reality: { strategy: reality.strategy, buyHold: reality.buyHold },
  }
}

Bun.serve({
  hostname: "127.0.0.1",
  port,
  async fetch(request) {
    const url = new URL(request.url)
    try {
      if (url.pathname === "/api/health" && request.method === "GET") return json(healthBody(env))
      if (url.pathname === "/api/market" && request.method === "GET") {
        const symbol = url.searchParams.get("symbol") ?? ""
        const start = url.searchParams.get("start") ?? ""
        const end = url.searchParams.get("end") ?? ""
        if (!isSymbol(symbol)) return json({ error: "Unknown symbol." }, 400)
        assertRange(start, end)
        log(`GET /api/market ${symbol} ${start} ${end}`)
        const loaded = await loadBars(symbol, start, end)
        return json(desk(symbol, start, end, loaded.bars, loaded.source))
      }
      if (url.pathname === "/api/agent" && request.method === "POST") {
        const body = (await request.json()) as { symbol?: string; model?: string; packet?: unknown }
        const symbol = body.symbol ?? ""
        if (!isSymbol(symbol)) return json({ error: "Unknown symbol." }, 400)
        if (!body.packet || typeof body.packet !== "object") return json({ error: "A packet is required." }, 400)
        const costs = costModel(symbol)
        log(`POST /api/agent ${symbol}`)
        const result = await askAgent({
          env,
          symbol,
          capital: costs.capital,
          currency: costs.currency,
          packet: body.packet,
          model: body.model,
        })
        return json(result)
      }
      return json({ error: "Not found." }, 404)
    } catch (error) {
      const message = error instanceof Error ? error.message : ""
      const status = message === "Unknown Anthropic model." ? 400 : 502
      log(message || "request failed")
      return fail(error, status)
    }
  },
})

log(`Candle Lens API http://127.0.0.1:${port}`)
