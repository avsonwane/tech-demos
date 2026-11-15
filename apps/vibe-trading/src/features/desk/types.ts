export type ProviderInfo = {
  id: string
  label: string
  env: string
  key_set: boolean
  model: string
  note: string
}

export type Preset = {
  id: string
  label: string
  prompt: string
}

export type Health = {
  ok: boolean
  advice: string
  providers: ProviderInfo[]
  presets: Preset[]
  nse: { accepted: boolean; market: string; example: string }
  sample: { label: string; source: string }
  serve: { running: boolean; error: string | null }
}

export type Phase = {
  id: string
  title: string
  status: "waiting" | "working" | "done" | "skipped"
  body: string
}

export type EquityPoint = {
  time: string
  equity: number
  benchmark: number | null
  drawdown: number
}

export type Trade = {
  time: string
  code: string
  side: string
  price: number | null
  qty: number | null
  pnl: number | null
  event: string
}

export type DeskMetrics = {
  total_return: number | null
  cagr: number | null
  sharpe: number | null
  max_drawdown: number | null
  win_rate: number | null
  benchmark_return: number | null
  fees: number | null
  fees_reported: boolean
}

export type DeskResult = {
  run_id: string | null
  status: string | null
  strategy_label: string | null
  benchmark_label: string | null
  codes: string[]
  start_date: string | null
  end_date: string | null
  sources: string[]
  metrics: DeskMetrics
  equity: EquityPoint[]
  trades: Trade[]
  code: string
  illustrative: boolean
}

export type RunMeta = {
  mode: "replay" | "live"
  banner: string | null
  reason: string | null
  provider: string
  model: string
  prompt: string
}

export type RunRequest = {
  prompt: string
  provider: string
  mode: "auto" | "live" | "replay"
}

export type SseMessage =
  | { event: "meta"; data: RunMeta }
  | { event: "phase"; data: Phase }
  | { event: "result"; data: DeskResult }
  | { event: "error"; data: { message: string } }
  | { event: "done"; data: { mode: string } }
