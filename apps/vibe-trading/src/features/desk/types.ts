export type ModelChoice = {
  id: string
  label: string
  note: string
}

export type ProviderInfo = {
  id: string
  label: string
  env: string
  key_set: boolean
  model: string
  models?: ModelChoice[]
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

export type ReportRow = {
  id: string
  label: string
  unit: "percent" | "number" | "money" | "count"
  tone: "sign" | "sharpe" | "drawdown" | "winrate" | "plain" | "ratio" | "cost"
  signed: boolean
  strategy: number | null
  benchmark: number | null
}

export type RoundTrip = {
  entry_time: string | null
  exit_time: string | null
  entry_price: number | null
  exit_price: number | null
  qty: number | null
  holding_days: number | null
  pnl: number | null
  return_pct: number | null
  fees: number | null
  open: boolean
}

export type DrawdownPeriod = {
  start: string
  trough: string
  recovery: string | null
  depth: number
}

export type ReportNotes = {
  sources: string[]
  start_date: string | null
  end_date: string | null
  first_bar: string | null
  last_bar: string | null
  bars: number
  frequency: string | null
  warmup: string | null
  starting_capital: number | null
  fee_model: string | null
  fees: number | null
  sharpe_note: string | null
  benchmark_source: string | null
  benchmark_detail: string | null
  recorded_benchmark: string | null
}

export type DeskReport = {
  summary: string
  comparison: ReportRow[]
  monthly: { year: number; months: Array<number | null>; marks?: Array<string | null> }[]
  round_trips: RoundTrip[]
  drawdowns: DrawdownPeriod[]
  notes: ReportNotes
  markdown: string
  trades_csv: string
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
  report?: DeskReport
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
  model?: string
  sample?: string
}

export type SseMessage =
  | { event: "meta"; data: RunMeta }
  | { event: "phase"; data: Phase }
  | { event: "result"; data: DeskResult }
  | { event: "error"; data: { message: string } }
  | { event: "done"; data: { mode: string } }
