import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { DrawdownChart, EquityChart } from "./Charts"
import type { DeskResult } from "./types"

function percent(value: number | null): string {
  if (value == null || Number.isNaN(value)) return "n/a"
  return `${(value * 100).toFixed(2)}%`
}

function number(value: number | null, digits = 2): string {
  if (value == null || Number.isNaN(value)) return "n/a"
  return value.toFixed(digits)
}

function money(value: number | null): string {
  if (value == null || Number.isNaN(value)) return "n/a"
  return value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export function Results({ result }: { result: DeskResult }) {
  const metrics = [
    ["Return", percent(result.metrics.total_return)],
    ["CAGR", percent(result.metrics.cagr)],
    ["Sharpe", number(result.metrics.sharpe)],
    ["Max drawdown", percent(result.metrics.max_drawdown)],
    ["Win rate", percent(result.metrics.win_rate)],
    ["Fees", result.metrics.fees_reported ? money(result.metrics.fees) : "Not reported"],
  ] as const
  const shown = result.metrics.benchmark_return == null
    ? metrics
    : ([...metrics, ["Buy and hold", percent(result.metrics.benchmark_return)]] as const)
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
          <p>
            {names}
            {range ? ` · ${range}` : ""}
          </p>
          {result.benchmark_label ? (
            <p className="text-muted-foreground">Benchmark: {result.benchmark_label}</p>
          ) : null}
          <p className="text-muted-foreground">
            Data source: {result.sources.length > 0 ? result.sources.join(", ") : "Not recorded"}
          </p>
          {result.run_id ? <p className="text-muted-foreground">Run {result.run_id}</p> : null}
        </CardContent>
      </Card>

      <div className="grid gap-3 sm:grid-cols-3">
        {shown.map(([label, value]) => (
          <div key={label} className="border border-foreground/15 px-4 py-3">
            <p className="text-xs tracking-widest uppercase text-muted-foreground">{label}</p>
            <p className="mt-2 font-heading text-2xl tracking-wide">{value}</p>
          </div>
        ))}
      </div>
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
            <EquityChart points={result.equity} />
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
                  {result.trades.map((trade, index) => (
                    <tr key={`${trade.time}-${trade.event}-${index}`} className="border-t border-foreground/10">
                      <td className="py-2 pr-3">{trade.time}</td>
                      <td className="py-2 pr-3">{trade.code}</td>
                      <td className="py-2 pr-3">{trade.side}</td>
                      <td className="py-2 pr-3">{trade.event}</td>
                      <td className="py-2 pr-3">{number(trade.price)}</td>
                      <td className="py-2 pr-3">{number(trade.qty, 0)}</td>
                      <td className="py-2">{number(trade.pnl)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

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
