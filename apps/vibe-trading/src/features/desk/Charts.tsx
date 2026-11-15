import type { EquityPoint } from "./types"

type ChartProps = {
  points: EquityPoint[]
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

export function EquityChart({ points }: ChartProps) {
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
  return (
    <figure>
      <figcaption className="mb-3 flex flex-wrap gap-x-4 gap-y-1 text-xs tracking-widest uppercase text-muted-foreground">
        <span>Equity</span>
        <span className="text-foreground">Strategy</span>
        <span>Buy and hold</span>
      </figcaption>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="Equity curve of the strategy and buy-and-hold"
        className="h-56 w-full"
      >
        <path d={equity} fill="none" stroke="var(--foreground)" strokeWidth="2" />
        {benchmark ? (
          <path d={benchmark} fill="none" stroke="var(--muted-foreground)" strokeWidth="1.5" strokeDasharray="4 4" />
        ) : null}
      </svg>
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
      <figcaption className="mb-3 text-xs tracking-widest uppercase text-muted-foreground">Drawdown</figcaption>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Drawdown from the running peak" className="h-40 w-full">
        <path d={area} fill="var(--muted)" />
        <path d={line} fill="none" stroke="var(--foreground)" strokeWidth="1.5" />
      </svg>
    </figure>
  )
}
