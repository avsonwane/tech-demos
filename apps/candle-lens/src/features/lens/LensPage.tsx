import { useEffect, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { askAgent, fetchHealth, fetchMarket } from "@/features/lens/api"
import { CandleChart } from "@/features/lens/Chart"
import type { AgentReply, Health, MarketResponse, Metrics } from "@/features/lens/types"

const SYMBOLS = ["RELIANCE.NS", "^NSEI", "BTC-USD"] as const

const FACTORS = [
  ["trend", "Trend"],
  ["momentum", "Momentum"],
  ["strength", "Strength"],
  ["volume", "Volume"],
  ["htf", "Higher timeframe"],
] as const

export function LensPage() {
  const [health, setHealth] = useState<Health | null>(null)
  const [symbol, setSymbol] = useState<(typeof SYMBOLS)[number]>("RELIANCE.NS")
  const [start, setStart] = useState("2024-01-01")
  const [end, setEnd] = useState("2024-12-31")
  const [active, setActive] = useState({ symbol: "RELIANCE.NS", start: "2024-01-01", end: "2024-12-31" })
  const [data, setData] = useState<MarketResponse | null>(null)
  const [selected, setSelected] = useState(0)
  const [model, setModel] = useState("claude-sonnet-5-5")
  const [reply, setReply] = useState<AgentReply | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [asking, setAsking] = useState(false)

  useEffect(() => {
    fetchHealth()
      .then((body) => {
        setHealth(body)
        setModel(body.defaultModel)
      })
      .catch(() => setHealth(null))
  }, [])

  useEffect(() => {
    let cancelled = false
    fetchMarket(active.symbol, active.start, active.end)
      .then((body) => {
        if (cancelled) return
        setData(body)
        setSelected(Math.max(0, body.packets.length - 1))
      })
      .catch((cause: unknown) => {
        if (cancelled) return
        setData(null)
        setError(cause instanceof Error ? cause.message : "The market request failed.")
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [active])

  const packet = data?.packets[selected]
  const bar = data?.bars[selected]

  async function onAsk() {
    if (!data || !packet) return
    setAsking(true)
    setError(null)
    try {
      setReply(await askAgent(data.symbol, model, packet))
    } catch (cause) {
      setReply(null)
      setError(cause instanceof Error ? cause.message : "Ask the agent failed.")
    } finally {
      setAsking(false)
    }
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="mx-auto flex max-w-6xl flex-wrap items-end justify-between gap-3 px-4 py-3">
          <div>
            <h1 className="font-heading text-3xl leading-none">Candle Lens</h1>
            <p className="mt-1 text-sm text-muted-foreground">Daily AI Agent Lens packets, a second opinion, and a fee-aware check against buy and hold.</p>
          </div>
          <p data-testid="disclaimer" className="text-xs tracking-wide text-muted-foreground">
            Research and paper trading only, not financial advice.
          </p>
        </div>
      </header>
      <main className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex gap-2">
            {SYMBOLS.map((item) => (
              <Button key={item} type="button" size="sm" variant={symbol === item ? "default" : "outline"} onClick={() => {
                setSymbol(item)
                setLoading(true)
                setError(null)
                setReply(null)
                setActive({ symbol: item, start, end })
              }}>
                {item}
              </Button>
            ))}
          </div>
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            Start
            <input className="border-b bg-transparent px-1 py-1 text-sm text-foreground" type="date" value={start} onChange={(event) => setStart(event.target.value)} />
          </label>
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            End
            <input className="border-b bg-transparent px-1 py-1 text-sm text-foreground" type="date" value={end} onChange={(event) => setEnd(event.target.value)} />
          </label>
          <Button type="button" size="sm" variant="secondary" onClick={() => {
            setLoading(true)
            setError(null)
            setReply(null)
            setActive({ symbol, start, end })
          }}>
            Load
          </Button>
          {loading ? <span className="text-sm text-muted-foreground">Loading bars…</span> : null}
        </div>
        {health && !health.anthropic ? (
          <p className="text-sm text-muted-foreground">No ANTHROPIC_API_KEY. Ask the agent plays a labeled sample. The chart, packet, and Reality check work without a key.</p>
        ) : null}
        {data?.source === "fixture" ? (
          <p className="text-sm text-muted-foreground">Live Yahoo data was unavailable. Showing the shipped RELIANCE.NS fixture.</p>
        ) : null}
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        {data && packet && bar ? (
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
            <div className="flex flex-col gap-4">
              <Card size="sm">
                <CardHeader>
                  <CardTitle>Chart</CardTitle>
                  <p className="text-sm text-muted-foreground">
                    {bar.date} · {packet.event} · {packet.regime} · long {packet.scores.long} / short {packet.scores.short}
                  </p>
                </CardHeader>
                <CardContent className="flex flex-col gap-2">
                  <CandleChart
                    bars={data.bars}
                    emaFast={data.emaFast}
                    emaMid={data.emaMid}
                    emaSlow={data.emaSlow}
                    packets={data.packets}
                    selected={selected}
                    onSelect={setSelected}
                  />
                  <p className="text-xs text-muted-foreground">EMA 20, 50, and 200. Entry, stop, 1.5R, and 3R are the selected bar's tracked trade. L and S mark official setups.</p>
                </CardContent>
              </Card>
              <Card size="sm" data-testid="reality-strip">
                <CardHeader>
                  <CardTitle>Reality check</CardTitle>
                  <p className="text-sm text-muted-foreground">
                    {data.symbol} {data.start} to {data.end} · starting {money(data.capital, data.currency)}
                  </p>
                </CardHeader>
                <CardContent className="flex flex-col gap-3">
                  <MetricTable strategy={data.reality.strategy} buyHold={data.reality.buyHold} currency={data.currency} />
                  <Separator />
                  <p className="text-xs text-muted-foreground">{data.feeNote}</p>
                </CardContent>
              </Card>
            </div>
            <div className="flex flex-col gap-4">
              <Card size="sm" data-testid="packet-pane">
                <CardHeader>
                  <CardTitle>Packet</CardTitle>
                  <div className="flex flex-wrap gap-3 text-sm">
                    <Badge>{packet.trade.side}:{packet.trade.status}</Badge>
                    <span className="text-muted-foreground">{packet.trend.stack} · HTF {packet.trend.htf_bias}</span>
                  </div>
                </CardHeader>
                <CardContent className="flex flex-col gap-3">
                  <div className="grid grid-cols-[1.4fr_auto_auto] gap-x-3 gap-y-1 text-sm">
                    <span className="text-muted-foreground">Factor</span>
                    <span className="text-right">Long</span>
                    <span className="text-right">Short</span>
                    {FACTORS.map(([key, label]) => (
                      <FactorRow key={key} label={label} long={packet.scores.long_factors[key]} short={packet.scores.short_factors[key]} />
                    ))}
                  </div>
                  <p className="text-sm">
                    Entry {price(packet.trade.entry)} · Stop {price(packet.trade.stop)} · 1.5R {price(packet.trade.target_1)} · 3R {price(packet.trade.target_2)}
                  </p>
                  <ScrollArea className="h-48 border">
                    <pre className="p-3 text-xs leading-relaxed">{JSON.stringify(packet, null, 2)}</pre>
                  </ScrollArea>
                </CardContent>
              </Card>
              <Card size="sm" data-testid="agent-card">
                <CardHeader>
                  <CardTitle>Ask the agent</CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-3">
                  <div className="flex flex-wrap items-center gap-3">
                    <Select value={model} onValueChange={setModel}>
                      <SelectTrigger className="w-52" aria-label="Model">
                        <SelectValue placeholder="Model" />
                      </SelectTrigger>
                      <SelectContent>
                        {(health?.models ?? [{ id: "claude-sonnet-5-5", label: "claude-sonnet-5-5", note: "" }]).map((item) => (
                          <SelectItem key={item.id} value={item.id}>
                            {item.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Button type="button" data-testid="ask-agent" disabled={asking} onClick={() => void onAsk()}>
                      {asking ? "Asking…" : "Ask the agent"}
                    </Button>
                  </div>
                  {reply ? (
                    <div className="flex flex-col gap-2">
                      {reply.illustrative && reply.label ? <p className="text-sm text-muted-foreground">{reply.label}</p> : null}
                      <div className="flex items-center gap-3">
                        <Badge>{reply.decision}</Badge>
                        {reply.model ? <span className="text-xs text-muted-foreground">{reply.model}</span> : null}
                      </div>
                      <p className="text-sm">
                        <span className="text-muted-foreground">why_this_could_fail. </span>
                        {reply.why_this_could_fail}
                      </p>
                      {reply.summary.length > 0 ? (
                        <ol className="list-decimal pl-4 text-sm text-muted-foreground">
                          {reply.summary.map((line) => (
                            <li key={line}>{line}</li>
                          ))}
                        </ol>
                      ) : null}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">Sends the selected packet. With no key, this plays the upstream illustrative sample.</p>
                  )}
                </CardContent>
              </Card>
            </div>
          </div>
        ) : null}
      </main>
    </div>
  )
}

function FactorRow({ label, long, short }: { label: string; long: number; short: number }) {
  return (
    <>
      <span>{label}</span>
      <span className="text-right tabular-nums">{long}</span>
      <span className="text-right tabular-nums">{short}</span>
    </>
  )
}

function MetricTable({ strategy, buyHold, currency }: { strategy: Metrics; buyHold: Metrics; currency: "INR" | "USD" }) {
  const rows: [string, string, string][] = [
    ["Return", pct(strategy.returnPct), pct(buyHold.returnPct)],
    ["CAGR", pct(strategy.cagrPct), pct(buyHold.cagrPct)],
    ["Sharpe", num(strategy.sharpe), num(buyHold.sharpe)],
    ["Max drawdown", pct(strategy.maxDrawdownPct), pct(buyHold.maxDrawdownPct)],
    ["Win rate", pct(strategy.winRatePct), pct(buyHold.winRatePct)],
    ["Trades", String(strategy.tradeCount), String(buyHold.tradeCount)],
    ["Fees", money(strategy.fees, currency), money(buyHold.fees, currency)],
  ]
  return (
    <div className="grid grid-cols-[1.3fr_1fr_1fr] gap-x-3 gap-y-1 text-sm">
      <span />
      <span className="text-right font-medium">Score-70 setups</span>
      <span className="text-right font-medium">Buy and hold</span>
      {rows.map(([label, left, right]) => (
        <span key={label} className="contents">
          <span className="text-muted-foreground">{label}</span>
          <span className="text-right tabular-nums">{left}</span>
          <span className="text-right tabular-nums">{right}</span>
        </span>
      ))}
    </div>
  )
}

function pct(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return "n/a"
  const sign = value > 0 ? "+" : ""
  return `${sign}${value.toFixed(2)}%`
}

function num(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return "n/a"
  return value.toFixed(2)
}

function money(value: number, currency: "INR" | "USD"): string {
  return new Intl.NumberFormat(currency === "INR" ? "en-IN" : "en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(value)
}

function price(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return "n/a"
  return value.toLocaleString("en-US", { maximumFractionDigits: 2 })
}
