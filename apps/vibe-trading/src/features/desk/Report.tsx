import { ArrowDown, ArrowUp } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { band, formatStat, toneClass, toneWord, type Tone } from "./tone"
import type { DeskReport, ReportRow, RoundTrip } from "./types"

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

function saveFile(filename: string, content: string, type: string) {
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

function Mark({ tone }: { tone: Tone }) {
  if (tone === "gain") return <ArrowUp aria-hidden className="inline size-3.5" />
  if (tone === "loss") return <ArrowDown aria-hidden className="inline size-3.5" />
  return null
}

function Cell({ row, value }: { row: ReportRow; value: number | null }) {
  const painted = band(row.tone, value)
  const word = toneWord(row.tone, value)
  const arrow = row.tone === "sign" || row.tone === "cost" || row.tone === "ratio" ? painted : "plain"
  return (
    <td className={`px-3 py-2 ${toneClass(painted)}`}>
      <span className="inline-flex items-center gap-1">
        <Mark tone={arrow} />
        {formatStat(value, row.unit, row.signed)}
        {word ? <span className="text-xs tracking-wide uppercase">{word}</span> : null}
      </span>
    </td>
  )
}

function tripTone(trip: RoundTrip): Tone {
  if (trip.pnl == null) return "plain"
  if (trip.pnl > 0) return "gain"
  if (trip.pnl < 0) return "loss"
  return "plain"
}

export function ReportView({ report, strategy, benchmark }: { report: DeskReport; strategy: string; benchmark: string }) {
  const notes = report.notes
  return (
    <Card id="detailed-report">
      <CardHeader>
        <CardTitle>Report</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-8">
        {notes.strategy_warning ? (
          <p className="border border-[var(--amber)] bg-[var(--amber-bg)] px-3 py-2 text-sm text-[var(--amber)]" role="status">
            {notes.strategy_warning}
          </p>
        ) : null}
        <p className="text-sm leading-relaxed">{report.summary}</p>
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" size="sm" onClick={() => saveFile("vibe-report.md", report.markdown, "text/markdown")}>
            Download report
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => saveFile("trades.csv", report.trades_csv, "text/csv")}
          >
            Download trades CSV
          </Button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <caption className="mb-2 text-left text-xs tracking-widest uppercase text-muted-foreground">
              Strategy vs benchmark
              {notes.benchmark_source ? ` · ${notes.benchmark_source}` : ""}
            </caption>
            <thead className="text-xs tracking-widest uppercase text-muted-foreground">
              <tr>
                <th className="py-2 pr-3 font-medium">Metric</th>
                <th className="py-2 pr-3 font-medium">{strategy}</th>
                <th className="py-2 font-medium">{benchmark}</th>
              </tr>
            </thead>
            <tbody>
              {report.comparison.map((row) => (
                <tr key={row.id} className="border-t border-foreground/10">
                  <th className="py-2 pr-3 text-left font-medium">{row.label}</th>
                  <Cell row={row} value={row.strategy} />
                  <Cell row={row} value={row.benchmark} />
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-xs leading-relaxed text-muted-foreground">
          Sharpe below 0.5 is low, 0.5–1 is mid, above 1 is high. Max drawdown shallower than 10% is shallow, 10–20% is
          moderate, deeper than 20% is deep. Win rate below 40% is low, 40–60% is mid, above 60% is high. Win rate in
          this table counts closed round trips. The tile above is the engine's win rate. A dash means the files do not
          determine that figure.
        </p>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[44rem] text-left text-sm">
            <caption className="mb-2 text-left text-xs tracking-widest uppercase text-muted-foreground">
              Monthly returns
            </caption>
            <thead className="text-xs tracking-widest uppercase text-muted-foreground">
              <tr>
                <th className="py-2 pr-2 font-medium">Year</th>
                {MONTHS.map((month) => (
                  <th key={month} className="px-1 py-2 font-medium">
                    {month}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {report.monthly.length === 0 ? (
                <tr>
                  <td colSpan={13} className="py-2 text-muted-foreground">
                    No equity bars.
                  </td>
                </tr>
              ) : (
                report.monthly.map((year) => (
                  <tr key={year.year} className="border-t border-foreground/10">
                    <th className="py-2 pr-2 text-left font-medium">{year.year}</th>
                    {year.months.map((value, index) => {
                      const mark = year.marks?.[index]
                      const warmup = mark === "warmup"
                      const painted = warmup || value == null ? "plain" : value > 0 ? "gain" : value < 0 ? "loss" : "plain"
                      const title =
                        mark === "warmup"
                          ? "Warmup: flat before the first equity bar"
                          : mark === "capital"
                            ? "Measured from starting capital. The previous month has no bar."
                            : undefined
                      return (
                        <td
                          key={MONTHS[index]}
                          title={title}
                          className={`px-1 py-2 text-center ${warmup ? "text-muted-foreground" : toneClass(painted)}`}
                        >
                          {value == null ? "—" : formatStat(value, "percent", true)}
                        </td>
                      )
                    })}
                  </tr>
                ))
              )}
            </tbody>
          </table>
          <p className="mt-2 text-xs text-muted-foreground">
            A month before the first equity bar is warmup and shows 0.00%. The first month with bars is measured from
            starting capital when the previous month has none. Later months need the previous month as well.
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <caption className="mb-2 text-left text-xs tracking-widest uppercase text-muted-foreground">
              Round trips
            </caption>
            <thead className="text-xs tracking-widest uppercase text-muted-foreground">
              <tr>
                {["Entry", "Exit", "Entry price", "Exit price", "Days", "PnL", "Return", "Fees"].map((label) => (
                  <th key={label} className="py-2 pr-3 font-medium">
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {report.round_trips.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-2 text-muted-foreground">
                    No trades were recorded.
                  </td>
                </tr>
              ) : (
                report.round_trips.map((trip, index) => {
                  const painted = tripTone(trip)
                  return (
                    <tr key={`${trip.entry_time}-${index}`} className={`border-t border-foreground/10 ${toneClass(painted)}`}>
                      <td className="py-2 pr-3">{trip.entry_time ?? "—"}</td>
                      <td className="py-2 pr-3">{trip.open ? "Open" : (trip.exit_time ?? "—")}</td>
                      <td className="py-2 pr-3">{formatStat(trip.entry_price, "number", false)}</td>
                      <td className="py-2 pr-3">{formatStat(trip.exit_price, "number", false)}</td>
                      <td className="py-2 pr-3">
                        {trip.holding_days == null ? "—" : `${trip.holding_days}${trip.open ? " open" : ""}`}
                      </td>
                      <td className="py-2 pr-3">
                        <span className="inline-flex items-center gap-1">
                          <Mark tone={painted} />
                          {formatStat(trip.pnl, "money", true)}
                        </span>
                      </td>
                      <td className="py-2 pr-3">{formatStat(trip.return_pct, "percent", true)}</td>
                      <td className="py-2 pr-3">{formatStat(trip.fees, "money", false)}</td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <caption className="mb-2 text-left text-xs tracking-widest uppercase text-muted-foreground">
              Largest drawdowns
            </caption>
            <thead className="text-xs tracking-widest uppercase text-muted-foreground">
              <tr>
                {["Start", "Trough", "Recovery", "Depth"].map((label) => (
                  <th key={label} className="py-2 pr-3 font-medium">
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {report.drawdowns.length === 0 ? (
                <tr>
                  <td colSpan={4} className="py-2 text-muted-foreground">
                    The equity file has no drawdown.
                  </td>
                </tr>
              ) : (
                report.drawdowns.map((period) => (
                  <tr key={`${period.start}-${period.trough}`} className="border-t border-foreground/10">
                    <td className="py-2 pr-3">{period.start}</td>
                    <td className="py-2 pr-3">{period.trough}</td>
                    <td className="py-2 pr-3">{period.recovery ?? "—"}</td>
                    <td className={`py-2 pr-3 ${toneClass(band("drawdown", period.depth))}`}>
                      <span className="inline-flex items-center gap-1">
                        <ArrowDown aria-hidden className="inline size-3.5" />
                        {formatStat(period.depth, "percent", true)}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <dl className="grid gap-2 text-sm">
          <div>
            <dt className="text-xs tracking-widest uppercase text-muted-foreground">Data notes</dt>
            <dd className="mt-2 grid gap-1">
              <p>Source: {notes.sources.length > 0 ? notes.sources.join(", ") : "—"}</p>
              <p>
                Requested range: {notes.start_date ?? "—"} to {notes.end_date ?? "—"}
              </p>
              <p>
                Equity bars: {notes.first_bar ?? "—"} to {notes.last_bar ?? "—"} ({notes.bars}), frequency:{" "}
                {notes.frequency ?? "—"}, warmup: {notes.warmup ?? "—"}
              </p>
              <p>
                Starting capital: {formatStat(notes.starting_capital, "money", false)}
                {notes.starting_capital != null ? ". Returns, CAGR, and max drawdown use this as the base." : ""}
              </p>
              <p>Fee model: {notes.fee_model ?? "—"}</p>
              {notes.benchmark_detail ? <p>{notes.benchmark_detail}</p> : notes.benchmark_source ? <p>Benchmark: {notes.benchmark_source}</p> : null}
              {notes.recorded_benchmark ? <p>{notes.recorded_benchmark}</p> : null}
              {notes.strategy_warning ? <p>{notes.strategy_warning}</p> : null}
              <p>Fees: {formatStat(notes.fees, "money", false)}</p>
              {notes.sharpe_note ? <p>{notes.sharpe_note}</p> : null}
              <p>Fees / PnL divides fill fees by closed-trade PnL. Those columns are not rescaled.</p>
            </dd>
          </div>
        </dl>
      </CardContent>
    </Card>
  )
}
