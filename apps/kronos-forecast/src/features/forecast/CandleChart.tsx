import { useEffect, useRef } from "react"
import {
  CandlestickSeries,
  ColorType,
  LineSeries,
  createChart,
  type UTCTimestamp,
} from "lightweight-charts"
import type { ForecastResponse } from "@/features/forecast/types"

type CandleChartProps = {
  result: ForecastResponse
}

function asTime(time: number): UTCTimestamp {
  return time as UTCTimestamp
}

export function CandleChart({ result }: CandleChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

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
      rightPriceScale: { borderColor: "rgba(68, 64, 60, 0.15)" },
      timeScale: {
        borderColor: "rgba(68, 64, 60, 0.15)",
        timeVisible: result.timeframe !== "1d",
        secondsVisible: false,
      },
    })

    const visible = result.history.slice(-96)
    const history = chart.addSeries(CandlestickSeries, {
      upColor: "#3f6212",
      downColor: "#9f1239",
      borderVisible: false,
      wickUpColor: "#3f6212",
      wickDownColor: "#9f1239",
      priceLineVisible: false,
    })
    history.setData(
      visible.map((bar) => ({
        time: asTime(bar.time),
        open: bar.open,
        high: bar.high,
        low: bar.low,
        close: bar.close,
      })),
    )

    const anchor = visible[visible.length - 1]
    for (const path of result.paths) {
      const line = chart.addSeries(LineSeries, {
        color: "rgba(87, 83, 78, 0.45)",
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      })
      line.setData([
        { time: asTime(anchor.time), value: anchor.close },
        ...result.forecastTimes.map((time, index) => ({
          time: asTime(time),
          value: path.close[index] ?? anchor.close,
        })),
      ])
    }

    const median = chart.addSeries(LineSeries, {
      color: "#1c1917",
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
    })
    median.setData([
      { time: asTime(anchor.time), value: anchor.close },
      ...result.median.map((bar) => ({ time: asTime(bar.time), value: bar.close })),
    ])

    if (result.actuals && result.actuals.length > 0) {
      const actuals = chart.addSeries(CandlestickSeries, {
        upColor: "#1d4ed8",
        downColor: "#1e3a8a",
        borderVisible: false,
        wickUpColor: "#1d4ed8",
        wickDownColor: "#1e3a8a",
        priceLineVisible: false,
      })
      actuals.setData(
        result.actuals.map((bar) => ({
          time: asTime(bar.time),
          open: bar.open,
          high: bar.high,
          low: bar.low,
          close: bar.close,
        })),
      )
    }

    chart.timeScale().fitContent()
    return () => chart.remove()
  }, [result])

  return <div ref={containerRef} className="h-[28rem] w-full" />
}
