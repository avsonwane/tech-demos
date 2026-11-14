export type ModelOption = {
  id: string
  label: string
}

export type ProviderInfo = {
  id: string
  label: string
  env: string
  key_set: boolean
  quick: ModelOption[]
  deep: ModelOption[]
  quick_default: string
  deep_default: string
}

export type Health = {
  ok: boolean
  advice: string
  providers: ProviderInfo[]
  sample: {
    ticker: string
    as_of: string
    label: string
    source: string
  }
}

export type Stage = {
  id: string
  phase: "analyst" | "debate" | "plan" | "trader" | "risk" | "decision"
  role: string
  title: string
  body: string
  status: "complete" | "skipped"
  action?: "BUY" | "HOLD" | "SELL" | "REVIEW"
  rating?: string
}

export type RunMeta = {
  mode: "live" | "replay"
  banner: string | null
  reason: string | null
  ticker: string
  as_of: string
  provider: string
  quick_model: string
  deep_model: string
  debate_rounds: number
  india_mode?: boolean
  currency?: "INR" | "USD"
}

export type SourceRow = {
  id: string
  label: string
  status: "ok" | "failed" | "skipped" | "blocked"
  detail: string
}

export type RunRequest = {
  ticker: string
  as_of: string
  provider: string
  quick_model: string
  deep_model: string
  debate_rounds: number
  mode: "auto" | "replay"
  india_mode: boolean
}

export type SseMessage =
  | { event: "meta"; data: RunMeta }
  | { event: "sources"; data: { sources: SourceRow[] } }
  | { event: "stage"; data: Stage }
  | { event: "done"; data: { mode: string } }
  | { event: "error"; data: { message: string } }
