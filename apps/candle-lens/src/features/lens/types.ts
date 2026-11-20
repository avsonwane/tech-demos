export type Health = {
  ok: true
  anthropic: boolean
  models: { id: string; label: string; note: string }[]
  defaultModel: string
}

export type Bar = {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number | null
}

export type Factors = {
  trend: number
  momentum: number
  strength: number
  volume: number
  htf: number
}

export type Packet = {
  schema: string
  event: string
  symbol: string
  timeframe: string
  time: string
  state_code: string
  candle: { pattern: string; direction: string }
  regime: string
  scores: {
    long: number
    short: number
    threshold: number
    long_factors: Factors
    short_factors: Factors
  }
  trade: {
    side: string
    status: string
    entry: number | null
    stop: number | null
    target_1: number | null
    target_2: number | null
    bars_since_entry: number | null
  }
  trend: { htf_bias: string; stack: string; slow_slope: string }
  [key: string]: unknown
}

export type Metrics = {
  returnPct: number
  cagrPct: number | null
  sharpe: number | null
  maxDrawdownPct: number
  winRatePct: number | null
  tradeCount: number
  fees: number
  endingEquity: number
}

export type MarketResponse = {
  symbol: string
  start: string
  end: string
  source: "yahoo" | "fixture"
  currency: "INR" | "USD"
  capital: number
  feeNote: string
  bars: Bar[]
  emaFast: (number | null)[]
  emaMid: (number | null)[]
  emaSlow: (number | null)[]
  packets: Packet[]
  reality: { strategy: Metrics; buyHold: Metrics }
}

export type AgentReply = {
  illustrative: boolean
  label: string | null
  model: string | null
  decision: string
  why_this_could_fail: string
  summary: string[]
  signal: Record<string, unknown>
}
