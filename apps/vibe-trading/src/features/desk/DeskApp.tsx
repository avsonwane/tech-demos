import { useEffect, useMemo, useRef, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { Textarea } from "@/components/ui/textarea"
import { fetchHealth, streamRun } from "./api"
import { Results } from "./Results"
import { Timeline } from "./Timeline"
import type { DeskResult, Health, Phase, RunMeta, RunRequest } from "./types"

const FALLBACK_PROMPT =
  "Backtest a 20/50 SMA crossover on AAPL for 2024 vs buy-and-hold, report max drawdown"

export function DeskApp() {
  const [health, setHealth] = useState<Health | null>(null)
  const [healthError, setHealthError] = useState<string | null>(null)
  const [prompt, setPrompt] = useState(FALLBACK_PROMPT)
  const [providerId, setProviderId] = useState("xai")
  const [status, setStatus] = useState<"idle" | "running" | "done" | "error">("idle")
  const [meta, setMeta] = useState<RunMeta | null>(null)
  const [phases, setPhases] = useState<Record<string, Phase>>({})
  const [result, setResult] = useState<DeskResult | null>(null)
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
          next.providers.find((provider) => provider.key_set) ??
          next.providers.find((provider) => provider.id === "xai")
        if (preferred) setProviderId(preferred.id)
        if (next.presets[0]) setPrompt(next.presets[0].prompt)
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return
        setHealthError(reason instanceof Error ? reason.message : "The backtest sidecar is not available.")
      })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    if (status !== "running" && status !== "done") return
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" })
  }, [phases, result, status])

  const provider = useMemo(
    () => health?.providers.find((item) => item.id === providerId),
    [health, providerId],
  )

  async function start(mode: RunRequest["mode"]) {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    setStatus("running")
    setMeta(null)
    setPhases({})
    setResult(null)
    setError(null)
    try {
      await streamRun(
        { prompt: prompt.trim(), provider: providerId, mode },
        (message) => {
          if (message.event === "meta") {
            setMeta(message.data)
            return
          }
          if (message.event === "phase") {
            setPhases((current) => ({ ...current, [message.data.id]: message.data }))
            return
          }
          if (message.event === "result") {
            setResult(message.data)
            return
          }
          if (message.event === "error") {
            setError(message.data.message)
            setStatus("error")
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
  const started = status !== "idle" || Object.keys(phases).length > 0

  return (
    <main className="mx-auto w-full max-w-5xl px-5 py-12">
      <p className="text-xs font-semibold tracking-widest uppercase text-muted-foreground">Paper research desk</p>
      <h1 className="mt-2 font-heading text-5xl tracking-wide">Vibe Backtest</h1>
      <p className="mt-4 max-w-2xl text-sm leading-relaxed">
        Describe a strategy in plain English. Vibe-Trading plans it, fetches bars, writes the strategy, and runs the
        backtest. This page keeps the equity curve, the drawdown, the trades, and the generated code.
      </p>
      <p className="mt-3 text-sm font-medium">Research/simulation only, not financial advice.</p>

      <Separator className="my-8" />

      <Card>
        <CardHeader>
          <CardTitle>Prompt</CardTitle>
          <CardDescription>
            NSE names such as RELIANCE.NS use Vibe-Trading’s India equity rules. Nothing is sent to a broker.
          </CardDescription>
        </CardHeader>
        <form
          onSubmit={(event) => {
            event.preventDefault()
            void start("auto")
          }}
        >
          <CardContent className="grid gap-6">
            <div className="flex flex-wrap gap-2">
              {(health?.presets ?? []).map((preset) => (
                <Button
                  key={preset.id}
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={running}
                  onClick={() => setPrompt(preset.prompt)}
                >
                  {preset.label}
                </Button>
              ))}
            </div>
            <div className="grid gap-2">
              <Label htmlFor="prompt">Strategy</Label>
              <Textarea
                id="prompt"
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
                rows={4}
                disabled={running}
                required
                spellCheck
              />
            </div>
            <div className="grid gap-2 sm:max-w-xs">
              <Label htmlFor="provider">Provider</Label>
              <Select value={providerId} onValueChange={setProviderId} disabled={running || !health}>
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
              {provider ? (
                <p className="text-sm text-muted-foreground">
                  {provider.model}. {provider.note}
                </p>
              ) : null}
            </div>
          </CardContent>
          <CardFooter className="flex flex-wrap items-center gap-3">
            <Button type="submit" disabled={running || !health || !prompt.trim()}>
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

      {healthError ? <p className="mt-4 text-sm text-destructive">{healthError}</p> : null}
      {health?.serve.error ? (
        <p className="mt-4 text-sm text-muted-foreground">
          The Vibe-Trading server is not up ({health.serve.error}). Replay still runs.
        </p>
      ) : null}

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
            {meta.provider} · {meta.model}
          </span>
        </div>
      ) : null}

      {error ? <p className="mt-4 text-sm text-destructive">{error}</p> : null}

      {status === "idle" ? (
        <p className="mt-10 text-sm text-muted-foreground">
          The timeline fills as the plan, the data fetch, the strategy code, and the backtest arrive.
        </p>
      ) : null}

      {started ? <Timeline phases={phases} running={running} /> : null}
      {result ? <Results result={result} /> : null}
      <div ref={bottomRef} />

      <Separator className="my-10" />
      <footer className="grid gap-2 text-sm text-muted-foreground">
        <p>Research/simulation only, not financial advice.</p>
        <p className="flex flex-wrap gap-x-4 gap-y-1">
          <a className="underline underline-offset-4" href="https://github.com/HKUDS/Vibe-Trading">
            Vibe-Trading
          </a>
          <a className="underline underline-offset-4" href="https://vibetrading.wiki/docs/">
            Docs
          </a>
          <a className="underline underline-offset-4" href="https://pypi.org/project/vibe-trading-ai/">
            PyPI
          </a>
        </p>
      </footer>
    </main>
  )
}
