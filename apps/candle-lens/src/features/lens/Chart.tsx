import { useEffect, useRef } from "react"
import {
  CandlestickSeries,
  ColorType,
  LineSeries,
  LineStyle,
  createChart,
  createSeriesMarkers,
  type ISeriesApi,
  type SeriesMarker,
  type Time,
} from "lightweight-charts"
import type { Bar, Packet } from "@/features/lens/types"

type ChartProps = {
  bars: Bar[]
  emaFast: (number | null)[]
  emaMid: (number | null)[]
  emaSlow: (number | null)[]
  packets: Packet[]
  selected: number
  onSelect: (index: number) => void
}

function businessDay(date: string): Time {
  const [year, month, day] = date.split("-").map(Number)
  return { year: year ?? 1970, month: month ?? 1, day: day ?? 1 }
}

function timeKey(time: Time): string {
  if (typeof time === "number") return new Date(time * 1000).toISOString().slice(0, 10)
  if (typeof time === "string") return time
  const month = String(time.month).padStart(2, "0")
  const day = String(time.day).padStart(2, "0")
  return `${time.year}-${month}-${day}`
}

function linePoints(bars: Bar[], values: (number | null)[]) {
  const points: { time: Time; value: number }[] = []
  bars.forEach((bar, index) => {
    const value = values[index]
    if (value == null) return
    points.push({ time: businessDay(bar.date), value })
  })
  return points
}

export function CandleChart({ bars, emaFast, emaMid, emaSlow, packets, selected, onSelect }: ChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null)
  const onSelectRef = useRef(onSelect)

  useEffect(() => {
    onSelectRef.current = onSelect
  })

  useEffect(() => {
    const container = containerRef.current
    if (!container || bars.length === 0) return
    const chart = createChart(container, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#57534e",
        fontFamily: "Noto Sans Variable, sans-serif",
      },
      grid: {
        vertLines: { color: "rgba(68, 64, 60, 0.08)" },
        horzLines: { color: "rgba(68, 64, 60, 0.08)" },
      },
      rightPriceScale: { borderColor: "rgba(68, 64, 60, 0.16)" },
      timeScale: { borderColor: "rgba(68, 64, 60, 0.16)" },
      crosshair: { vertLine: { labelBackgroundColor: "#44403c" }, horzLine: { labelBackgroundColor: "#44403c" } },
    })
    const candles = chart.addSeries(CandlestickSeries, {
      upColor: "#3f6212",
      downColor: "#9f1239",
      borderVisible: false,
      wickUpColor: "#3f6212",
      wickDownColor: "#9f1239",
      priceLineVisible: false,
    })
    candles.setData(
      bars.map((bar) => ({
        time: businessDay(bar.date),
        open: bar.open,
        high: bar.high,
        low: bar.low,
        close: bar.close,
      })),
    )
    const fast = chart.addSeries(LineSeries, { color: "#78716c", lineWidth: 1, priceLineVisible: false, lastValueVisible: false })
    const mid = chart.addSeries(LineSeries, { color: "#a16207", lineWidth: 1, priceLineVisible: false, lastValueVisible: false })
    const slow = chart.addSeries(LineSeries, { color: "#1c1917", lineWidth: 2, priceLineVisible: false, lastValueVisible: false })
    fast.setData(linePoints(bars, emaFast))
    mid.setData(linePoints(bars, emaMid))
    slow.setData(linePoints(bars, emaSlow))
    const markers: SeriesMarker<Time>[] = []
    packets.forEach((packet, index) => {
      const bar = bars[index]
      if (!bar) return
      if (packet.event === "LONG_SETUP") {
        markers.push({ time: businessDay(bar.date), position: "belowBar", color: "#3f6212", shape: "arrowUp", text: "L" })
      } else if (packet.event === "SHORT_SETUP") {
        markers.push({ time: businessDay(bar.date), position: "aboveBar", color: "#9f1239", shape: "arrowDown", text: "S" })
      }
    })
    createSeriesMarkers(candles, markers)
    seriesRef.current = candles
    chart.timeScale().fitContent()
    const pick = (time: Time | undefined) => {
      if (!time) return
      const key = timeKey(time)
      const index = bars.findIndex((bar) => bar.date === key)
      if (index >= 0) onSelectRef.current(index)
    }
    chart.subscribeClick((param) => pick(param.time))
    chart.subscribeCrosshairMove((param) => pick(param.time))
    return () => {
      seriesRef.current = null
      chart.remove()
    }
  }, [bars, emaFast, emaMid, emaSlow, packets])

  useEffect(() => {
    const series = seriesRef.current
    const trade = packets[selected]?.trade
    if (!series || !trade) return
    const lines = [
      trade.entry != null ? series.createPriceLine({ price: trade.entry, color: "#1c1917", lineWidth: 1, lineStyle: LineStyle.Solid, axisLabelVisible: true, title: "Entry" }) : null,
      trade.stop != null ? series.createPriceLine({ price: trade.stop, color: "#9f1239", lineWidth: 1, lineStyle: LineStyle.Dashed, axisLabelVisible: true, title: "Stop" }) : null,
      trade.target_1 != null ? series.createPriceLine({ price: trade.target_1, color: "#3f6212", lineWidth: 1, lineStyle: LineStyle.Dashed, axisLabelVisible: true, title: "1.5R" }) : null,
      trade.target_2 != null ? series.createPriceLine({ price: trade.target_2, color: "#3f6212", lineWidth: 2, lineStyle: LineStyle.Solid, axisLabelVisible: true, title: "3R" }) : null,
    ].filter((line) => line != null)
    return () => {
      for (const line of lines) series.removePriceLine(line)
    }
  }, [packets, selected])

  return <div ref={containerRef} data-testid="candle-chart" className="h-64 w-full" />
}
