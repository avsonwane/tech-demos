import { useEffect, useMemo, useRef, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { fetchHealth, streamRun } from "./api"
import { Timeline } from "./Timeline"
import type { Health, ProviderInfo, RunMeta, RunRequest, Stage } from "./types"

function todayLocal(): string {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, "0")
  const day = String(now.getDate()).padStart(2, "0")
  return `${now.getFullYear()}-${month}-${day}`
}

function providerLabel(health: Health | null, id: string): string {
  return health?.providers.find((provider) => provider.id === id)?.label ?? id
}

export function DeskApp() {
  const [health, setHealth] = useState<Health | null>(null)
  const [healthError, setHealthError] = useState<string | null>(null)
  const [ticker, setTicker] = useState("NVDA")
  const [asOf, setAsOf] = useState(todayLocal)
  const [providerId, setProviderId] = useState("xai")
  const [quickModel, setQuickModel] = useState("grok-4.6")
  const [deepModel, setDeepModel] = useState("grok-4.6")
  const [rounds, setRounds] = useState("1")
  const [status, setStatus] = useState<"idle" | "running" | "done" | "error">("idle")
  const [meta, setMeta] = useState<RunMeta | null>(null)
  const [stages, setStages] = useState<Record<string, Stage>>({})
  const [error, setError] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    fetchHealth(controller.signal)
      .then((next) => {
        setHealth(next)
        const preferred =
          next.providers.find((provider) => provider.id === "xai" && provider.key_set) ??
          next.providers.find((provider) => provider.id === "openai" && provider.key_set) ??
          next.providers.find((provider) => provider.id === "xai")
        if (preferred) {
          setProviderId(preferred.id)
          setQuickModel(preferred.quick_default)
          setDeepModel(preferred.deep_default)
        }
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return
        setHealthError(reason instanceof Error ? reason.message : "The research sidecar is not available.")
      })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    if (status !== "running" && status !== "done") return
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" })
  }, [stages, status])

  const provider: ProviderInfo | undefined = useMemo(
    () => health?.providers.find((item) => item.id === providerId),
    [health, providerId],
  )

  function onProvider(nextId: string) {
    setProviderId(nextId)
    const next = health?.providers.find((item) => item.id === nextId)
    if (!next) return
    setQuickModel(next.quick_default)
    setDeepModel(next.deep_default)
  }

  async function start(mode: RunRequest["mode"]) {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    setStatus("running")
    setMeta(null)
    setStages({})
    setError(null)
    const body: RunRequest = {
      ticker: ticker.trim(),
      as_of: asOf,
      provider: providerId,
      quick_model: quickModel,
      deep_model: deepModel,
      debate_rounds: Number(rounds),
      mode,
    }
    try {
      await streamRun(
        body,
        (message) => {
          if (message.event === "meta") {
            setMeta(message.data)
            return
          }
          if (message.event === "stage") {
            setStages((current) => ({ ...current, [message.data.id]: message.data }))
            return
          }
          if (message.event === "error") {
            setError(message.data.message)
            setStatus("error")
            return
          }
          if (message.event === "done") {
            setStatus((current) => (current === "error" ? current : "done"))
          }
        },
        controller.signal,
      )
      setStatus((current) => (current === "running" ? "done" : current))
    } catch (reason) {
      if (controller.signal.aborted) return
      setError(reason instanceof Error ? reason.message : "The run failed.")
      setStatus("error")
    }
  }

  const running = status === "running"
  const stageCount = Object.keys(stages).length

  return (
    <main className="mx-auto w-full max-w-3xl px-5 py-12">
      <p className="text-xs font-semibold tracking-widest uppercase text-muted-foreground">Paper research desk</p>
      <h1 className="mt-2 font-heading text-5xl tracking-wide">TradingAgents</h1>
      <p className="mt-4 max-w-xl text-sm leading-relaxed">
        Analysts write reports, a bull and a bear debate them, a trader proposes an action, and a risk team makes
        the final paper decision.
      </p>
      <p className="mt-3 text-sm font-medium">Research/simulation only, not financial advice.</p>

      <Separator className="my-8" />

      <Card>
        <CardHeader>
          <CardTitle>Run</CardTitle>
          <CardDescription>One Yahoo Finance ticker and one as-of date. Nothing is sent to a broker.</CardDescription>
        </CardHeader>
        <form
          onSubmit={(event) => {
            event.preventDefault()
            void start("auto")
          }}
        >
          <CardContent className="grid gap-6 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="ticker">Ticker</Label>
              <Input
                id="ticker"
                value={ticker}
                onChange={(event) => setTicker(event.target.value)}
                placeholder="NVDA"
                autoCapitalize="characters"
                spellCheck={false}
                disabled={running}
                required
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="as-of">As-of date</Label>
              <Input id="as-of" type="date" value={asOf} max={todayLocal()} onChange={(event) => setAsOf(event.target.value)} disabled={running} required />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="provider">Provider</Label>
              <Select value={providerId} onValueChange={onProvider} disabled={running || !health}>
                <SelectTrigger id="provider" className="w-full">
                  <SelectValue placeholder="Provider" />
                </SelectTrigger>
                <SelectContent position="popper">
                  {(health?.providers ?? []).map((item) => (
                    <SelectItem key={item.id} value={item.id}>
                      {item.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="rounds">Debate rounds</Label>
              <Select value={rounds} onValueChange={setRounds} disabled={running}>
                <SelectTrigger id="rounds" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent position="popper">
                  <SelectItem value="1">1 round</SelectItem>
                  <SelectItem value="2">2 rounds</SelectItem>
                  <SelectItem value="3">3 rounds</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="quick-model">Quick model</Label>
              <Select value={quickModel} onValueChange={setQuickModel} disabled={running || !provider}>
                <SelectTrigger id="quick-model" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent position="popper">
                  {(provider?.quick ?? []).map((model) => (
                    <SelectItem key={model.id} value={model.id}>
                      {model.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="deep-model">Deep model</Label>
              <Select value={deepModel} onValueChange={setDeepModel} disabled={running || !provider}>
                <SelectTrigger id="deep-model" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent position="popper">
                  {(provider?.deep ?? []).map((model) => (
                    <SelectItem key={model.id} value={model.id}>
                      {model.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </CardContent>
          <CardFooter className="flex flex-wrap items-center gap-3">
            <Button type="submit" disabled={running || !health}>
              {running ? "Running" : "Run"}
            </Button>
            <Button type="button" variant="outline" disabled={running || !health} onClick={() => void start("replay")}>
              Replay sample
            </Button>
            {provider && !provider.key_set ? (
              <p className="text-sm text-muted-foreground">{provider.env} is not set. Run plays the sample.</p>
            ) : null}
          </CardFooter>
        </form>
      </Card>

      <p className="mt-4 text-sm text-muted-foreground">
        Prices, indicators, news, and filings use Yahoo Finance and SEC EDGAR. FRED macro data is skipped when
        FRED_API_KEY is unset. Alpha Vantage is not used. One rounds value sets both the research debate and the
        risk team.
      </p>
      {healthError ? <p className="mt-3 text-sm text-destructive">{healthError}</p> : null}

      {meta?.mode === "replay" ? (
        <div role="status" className="mt-8 border border-foreground/15 bg-muted px-4 py-3">
          <p className="text-xs font-semibold tracking-widest uppercase">Replay mode</p>
          <p className="mt-2 text-sm leading-relaxed">{meta.banner}</p>
          {meta.reason ? <p className="mt-2 text-sm text-muted-foreground">{meta.reason}</p> : null}
        </div>
      ) : null}

      {meta ? (
        <div className="mt-8 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
          <Badge>{meta.mode === "replay" ? "Sample" : "Live"}</Badge>
          <span>
            {meta.ticker} · {meta.as_of} · {providerLabel(health, meta.provider)} {meta.quick_model} / {meta.deep_model} ·{" "}
            {meta.debate_rounds} {meta.debate_rounds === 1 ? "round" : "rounds"}
          </span>
        </div>
      ) : null}

      {error ? <p className="mt-4 text-sm text-destructive">{error}</p> : null}

      {status === "idle" && stageCount === 0 ? (
        <p className="mt-10 text-sm text-muted-foreground">
          The timeline fills as each analyst, debate turn, and the paper decision arrives.
        </p>
      ) : null}

      {status !== "idle" || stageCount > 0 ? <Timeline stages={stages} running={running} /> : null}
      <div ref={bottomRef} />

      <Separator className="my-10" />
      <footer className="grid gap-2 text-sm text-muted-foreground">
        <p>Research/simulation only, not financial advice.</p>
        <p className="flex flex-wrap gap-x-4 gap-y-1">
          <a className="underline underline-offset-4" href="https://github.com/TauricResearch/TradingAgents">
            TradingAgents
          </a>
          <a className="underline underline-offset-4" href="https://arxiv.org/abs/2412.20138">
            arXiv:2412.20138
          </a>
          <a className="underline underline-offset-4" href="https://x.com/gusik4ever/status/2119044302319853924">
            Source bookmark
          </a>
        </p>
      </footer>
    </main>
  )
}
