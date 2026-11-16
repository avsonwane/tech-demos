import { ArrowDown, ArrowUp } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { DrawdownChart, EquityChart } from "./Charts"
import { ReportView } from "./Report"
import { band, formatStat, toneClass, toneWord, type Tone } from "./tone"
import type { DeskResult, Trade } from "./types"

function number(value: number | null, digits = 2): string {
  if (value == null || Number.isNaN(value)) return "n/a"
  return value.toFixed(digits)
}

function money(value: number | null): string {
  if (value == null || Number.isNaN(value)) return "n/a"
  return value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function tradeSide(trade: Trade): "buy" | "sell" | null {
  const event = trade.event.toLowerCase()
  const side = trade.side.toLowerCase()
  if (event === "exit" || side === "sell" || side === "short") return "sell"
  if (event === "entry" || side === "buy" || side === "long") return "buy"
  return null
}

function pnlTone(value: number | null): Tone {
  if (value == null || value === 0) return "plain"
  return value > 0 ? "gain" : "loss"
}

export function Results({ result, model }: { result: DeskResult; model?: string | null }) {
  const tiles: { label: string; text: string; tone: Tone; word: string | null }[] = [
    { label: "Return", text: formatStat(result.metrics.total_return, "percent", true), tone: band("sign", result.metrics.total_return), word: null },
    { label: "CAGR", text: formatStat(result.metrics.cagr, "percent", true), tone: band("sign", result.metrics.cagr), word: null },
    { label: "Sharpe", text: formatStat(result.metrics.sharpe, "number", true), tone: band("sharpe", result.metrics.sharpe), word: toneWord("sharpe", result.metrics.sharpe) },
    { label: "Max drawdown", text: formatStat(result.metrics.max_drawdown, "percent", true), tone: band("drawdown", result.metrics.max_drawdown), word: toneWord("drawdown", result.metrics.max_drawdown) },
    { label: "Win rate", text: formatStat(result.metrics.win_rate, "percent", false), tone: band("winrate", result.metrics.win_rate), word: toneWord("winrate", result.metrics.win_rate) },
    { label: "Fees", text: result.metrics.fees_reported ? money(result.metrics.fees) : "Not reported", tone: "plain", word: null },
  ]
  if (result.metrics.benchmark_return != null) {
    tiles.push({
      label: "Buy and hold",
      text: formatStat(result.metrics.benchmark_return, "percent", true),
      tone: band("sign", result.metrics.benchmark_return),
      word: null,
    })
  }
  const range = [result.start_date, result.end_date].filter(Boolean).join(" – ")
  const names = result.codes.join(", ") || "Unspecified"

  return (
    <div className="mt-4 grid gap-6">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center gap-2">
            <CardTitle>{result.strategy_label ?? "Run card"}</CardTitle>
            {result.illustrative ? <Badge variant="secondary">Illustrative</Badge> : <Badge>Live</Badge>}
          </div>
        </CardHeader>
        <CardContent className="grid gap-2 text-sm">
          {result.strategy_warning ? (
            <p className="border border-[var(--amber)] bg-[var(--amber-bg)] px-3 py-2 text-[var(--amber)]" role="status">
              {result.strategy_warning}
            </p>
          ) : null}
          <p>
            {names}
            {range ? ` · ${range}` : ""}
          </p>
          {result.benchmark_label ? (
            <p className="text-muted-foreground">
              Benchmark: {result.benchmark_label}
              {result.report?.notes.benchmark_source ? ` · ${result.report.notes.benchmark_source}` : ""}
            </p>
          ) : null}
          <p className="text-muted-foreground">
            Data source: {result.sources.length > 0 ? result.sources.join(", ") : "Not recorded"}
          </p>
          {model ? <p className="text-muted-foreground">Model: {model}</p> : null}
          {result.run_id ? <p className="text-muted-foreground">Run {result.run_id}</p> : null}
        </CardContent>
      </Card>

      <div className="grid gap-3 sm:grid-cols-3">
        {tiles.map((tile) => (
          <div key={tile.label} className={`border border-foreground/15 px-4 py-3 ${toneClass(tile.tone)}`}>
            <p className="text-xs tracking-widest uppercase opacity-80">{tile.label}</p>
            <p className="mt-2 flex items-center gap-2 font-heading text-2xl tracking-wide">
              {tile.tone === "gain" && !tile.word ? <ArrowUp aria-hidden className="size-5" /> : null}
              {tile.tone === "loss" && !tile.word ? <ArrowDown aria-hidden className="size-5" /> : null}
              {tile.text}
            </p>
            {tile.word ? <p className="mt-1 text-xs tracking-widest uppercase">{tile.word}</p> : null}
          </div>
        ))}
      </div>
      <p className="text-xs leading-relaxed text-muted-foreground">
        Green is a gain and red is a loss, with a plus or a minus on the number. Sharpe below 0.5 is low, 0.5–1 is
        mid, and above 1 is high. Max drawdown shallower than 10% is shallow, 10–20% is moderate, and deeper than 20%
        is deep. Win rate below 40% is low, 40–60% is mid, and above 60% is high.
      </p>
      {result.metrics.fees_reported ? null : (
        <p className="text-sm text-muted-foreground">
          Vibe-Trading’s summary metrics do not include a fee total for this run. Per-fill fees stay in the run’s
          fills file.
        </p>
      )}

      {result.equity.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Curves</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-8">
            <EquityChart points={result.equity} trades={result.trades} />
            <DrawdownChart points={result.equity} />
          </CardContent>
        </Card>
      ) : (
        <p className="text-sm text-muted-foreground">This run did not include an equity curve.</p>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Trades</CardTitle>
        </CardHeader>
        <CardContent>
          {result.trades.length === 0 ? (
            <p className="text-sm text-muted-foreground">No trades were recorded.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="text-xs tracking-widest uppercase text-muted-foreground">
                  <tr>
                    <th className="py-2 pr-3 font-medium">Time</th>
                    <th className="py-2 pr-3 font-medium">Code</th>
                    <th className="py-2 pr-3 font-medium">Side</th>
                    <th className="py-2 pr-3 font-medium">Event</th>
                    <th className="py-2 pr-3 font-medium">Price</th>
                    <th className="py-2 pr-3 font-medium">Qty</th>
                    <th className="py-2 font-medium">PnL</th>
                  </tr>
                </thead>
                <tbody>
                  {result.trades.map((trade, index) => {
                    const painted = pnlTone(trade.pnl)
                    const side = tradeSide(trade)
                    return (
                      <tr key={`${trade.time}-${trade.event}-${index}`} className={`border-t border-foreground/10 ${toneClass(painted)}`}>
                        <td className="py-2 pr-3">{trade.time}</td>
                        <td className="py-2 pr-3">{trade.code}</td>
                        <td className={`py-2 pr-3 ${side === "buy" ? "text-[var(--gain)]" : side === "sell" ? "text-[var(--loss)]" : ""}`}>
                          {side === "buy" ? "▲ " : side === "sell" ? "▼ " : ""}
                          {trade.side}
                        </td>
                        <td className="py-2 pr-3">{trade.event}</td>
                        <td className="py-2 pr-3">{number(trade.price)}</td>
                        <td className="py-2 pr-3">{number(trade.qty, 0)}</td>
                        <td className="py-2">
                          {painted === "gain" ? <ArrowUp aria-hidden className="mr-1 inline size-3.5" /> : null}
                          {painted === "loss" ? <ArrowDown aria-hidden className="mr-1 inline size-3.5" /> : null}
                          {trade.pnl == null ? "n/a" : formatStat(trade.pnl, "money", true)}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {result.report ? (
        <ReportView
          report={result.report}
          strategy={result.strategy_label ?? "Strategy"}
          benchmark={result.benchmark_label ?? "Buy and hold"}
        />
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Strategy code</CardTitle>
        </CardHeader>
        <CardContent>
          {result.code ? (
            <pre className="overflow-x-auto text-xs leading-relaxed">{result.code}</pre>
          ) : (
            <p className="text-sm text-muted-foreground">The run did not include signal_engine.py.</p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
