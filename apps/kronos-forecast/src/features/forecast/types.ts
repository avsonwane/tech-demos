export type Bar = {
  time: number
  open: number
  high: number
  low: number
  close: number
}

export type ForecastMode = "forecast" | "test"

export type ForecastResponse = {
  symbol: string
  timeframe: string
  mode: ForecastMode
  model: string
  history: Bar[]
  forecastTimes: number[]
  paths: { close: number[] }[]
  median: Bar[]
  summary: {
    direction: "up" | "down" | "flat"
    medianChangePct: number
    spreadPct: number
    text: string
  }
  actuals: Bar[] | null
  score: {
    directionHits: number
    directionTotal: number
    mapePct: number
    text: string
  } | null
  elapsedSeconds: number
  disclaimer: string
}

export type ForecastRequest = {
  symbol: string
  timeframe: string
  horizon: number
  samples: number
  mode: ForecastMode
  holdout: number
}
