import type { EquityPoint, Trade } from "./types"

type ChartProps = {
  points: EquityPoint[]
  trades?: Trade[]
}

function extent(values: number[]): { min: number; max: number } {
  let min = values[0] ?? 0
  let max = values[0] ?? 0
  for (const value of values) {
    if (value < min) min = value
    if (value > max) max = value
  }
  if (min === max) {
    min -= 1
    max += 1
  }
  return { min, max }
}

function path(values: Array<number | null>, width: number, height: number, min: number, max: number): string {
  const usable = values
    .map((value, index) => (value == null ? null : { index, value }))
    .filter((point): point is { index: number; value: number } => point != null)
  if (usable.length === 0) return ""
  const step = values.length === 1 ? 0 : width / (values.length - 1)
  return usable
    .map((point, order) => {
      const x = point.index * step
      const y = height - ((point.value - min) / (max - min)) * height
      return `${order === 0 ? "M" : "L"}${x.toFixed(2)} ${y.toFixed(2)}`
    })
    .join(" ")
}

function stamp(value: string): number {
  const parsed = Date.parse(value.slice(0, 10))
  return Number.isNaN(parsed) ? Number.NaN : parsed
}

function markerPoint(
  points: EquityPoint[],
  time: string,
  width: number,
  height: number,
  min: number,
  max: number,
): { x: number; y: number } | null {
  if (points.length === 0) return null
  const target = stamp(time)
  const times = points.map((point) => stamp(point.time))
  if (Number.isNaN(target) || times.some((value) => Number.isNaN(value))) return null
  const first = times[0]
  const last = times[times.length - 1]
  const ratio = last === first ? 0 : (target - first) / (last - first)
  const x = Math.min(width, Math.max(0, ratio * width))
  let lower = 0
  for (let index = 0; index < times.length; index += 1) {
    if (times[index] <= target) lower = index
  }
  const upper = Math.min(points.length - 1, lower + (times[lower] === target ? 0 : 1))
  const span = times[upper] - times[lower]
  const mix = span === 0 ? 0 : (target - times[lower]) / span
  const equity = points[lower].equity + (points[upper].equity - points[lower].equity) * mix
  const y = height - ((equity - min) / (max - min)) * height
  return { x, y }
}

function sideOf(trade: Trade): "buy" | "sell" | null {
  const event = trade.event.toLowerCase()
  const side = trade.side.toLowerCase()
  if (event === "exit" || side === "sell" || side === "short") return "sell"
  if (event === "entry" || side === "buy" || side === "long") return "buy"
  return null
}

export function EquityChart({ points, trades = [] }: ChartProps) {
  const width = 640
  const height = 220
  const values = points.flatMap((point) =>
    point.benchmark == null ? [point.equity] : [point.equity, point.benchmark],
  )
  const { min, max } = extent(values)
  const equity = path(
    points.map((point) => point.equity),
    width,
    height,
    min,
    max,
  )
  const benchmark = path(
    points.map((point) => point.benchmark),
    width,
    height,
    min,
    max,
  )
  const rising = points.length > 0 && points[points.length - 1].equity >= points[0].equity
  const marks = trades.flatMap((trade, index) => {
    const side = sideOf(trade)
    const place = markerPoint(points, trade.time, width, height, min, max)
    if (!side || !place) return []
    return [{ ...place, side, index, price: trade.price, time: trade.time.slice(0, 10) }]
  })
  return (
    <figure>
      <figcaption className="mb-3 flex flex-wrap gap-x-4 gap-y-1 text-xs tracking-widest uppercase text-muted-foreground">
        <span className={rising ? "text-[var(--gain)]" : "text-[var(--loss)]"}>
          {rising ? "▲" : "▼"} Strategy
        </span>
        <span style={{ color: "var(--benchmark-line)" }}>— — Buy and hold</span>
        <span className="text-[var(--gain)]">▲ Buy</span>
        <span className="text-[var(--loss)]">▼ Sell</span>
      </figcaption>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="Equity curve. The solid line is the strategy and the dashed line is buy-and-hold. Triangles mark buys and sells."
        className="h-56 w-full"
      >
        <path d={equity} fill="none" stroke={rising ? "var(--gain)" : "var(--loss)"} strokeWidth="2.5" />
        {benchmark ? (
          <path
            d={benchmark}
            fill="none"
            stroke="var(--benchmark-line)"
            strokeWidth="1.5"
            strokeDasharray="5 5"
          />
        ) : null}
        {marks.map((mark) => {
          const size = 7
          const up = mark.side === "buy"
          const pointsAttr = up
            ? `${mark.x},${mark.y - size} ${mark.x - size},${mark.y + size} ${mark.x + size},${mark.y + size}`
            : `${mark.x},${mark.y + size} ${mark.x - size},${mark.y - size} ${mark.x + size},${mark.y - size}`
          const label = `${up ? "Buy" : "Sell"} ${mark.time}${mark.price == null ? "" : ` at ${mark.price}`}`
          return (
            <polygon
              key={`${mark.time}-${mark.side}-${mark.index}`}
              points={pointsAttr}
              fill={up ? "var(--gain)" : "var(--loss)"}
              stroke="var(--background)"
              strokeWidth="1"
            >
              <title>{label}</title>
            </polygon>
          )
        })}
      </svg>
      <p className="mt-2 text-xs text-muted-foreground">
        Triangles mark buys and sells from the trade file. Their height sits on the equity line.
      </p>
    </figure>
  )
}

export function DrawdownChart({ points }: ChartProps) {
  const width = 640
  const height = 160
  const values = points.map((point) => point.drawdown)
  const min = Math.min(0, ...values)
  const max = 0
  const span = max - min || 1
  const line = path(values, width, height, min, max)
  const step = values.length === 1 ? 0 : width / (values.length - 1)
  const area = [
    `M0 ${height}`,
    ...values.map((value, index) => {
      const y = height - ((value - min) / span) * height
      return `L${(index * step).toFixed(2)} ${y.toFixed(2)}`
    }),
    `L${width} ${height} Z`,
  ].join(" ")
  return (
    <figure>
      <figcaption className="mb-3 text-xs tracking-widest uppercase text-[var(--loss)]">▼ Drawdown</figcaption>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Drawdown from the running peak, shaded red" className="h-40 w-full">
        <path d={area} fill="var(--drawdown-fill)" />
        <path d={line} fill="none" stroke="var(--loss)" strokeWidth="1.5" />
      </svg>
    </figure>
  )
}
