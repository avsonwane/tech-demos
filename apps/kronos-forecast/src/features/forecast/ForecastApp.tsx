import { useEffect, useState, type FormEvent } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { fetchForecast, fetchHealth } from "@/features/forecast/api"
import { CandleChart } from "@/features/forecast/CandleChart"
import type { ForecastMode, ForecastResponse } from "@/features/forecast/types"

const TIMEFRAMES = [
  { value: "15m", label: "15 minutes" },
  { value: "1h", label: "1 hour" },
  { value: "4h", label: "4 hours" },
  { value: "1d", label: "1 day" },
]

export function ForecastApp() {
  const [symbol, setSymbol] = useState("BTCUSDT")
  const [timeframe, setTimeframe] = useState("1h")
  const [mode, setMode] = useState<ForecastMode>("forecast")
  const [horizon, setHorizon] = useState("24")
  const [holdout, setHoldout] = useState("12")
  const [samples, setSamples] = useState("8")
  const [modelState, setModelState] = useState<"loading" | "ready" | "error">("loading")
  const [modelError, setModelError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<ForecastResponse | null>(null)

  useEffect(() => {
    let stopped = false
    async function poll() {
      while (!stopped) {
        try {
          const health = await fetchHealth()
          if (health.error) {
            setModelState("error")
            setModelError(health.error)
            return
          }
          if (health.ready) {
            setModelState("ready")
            return
          }
        } catch {
          setModelState("loading")
        }
        await new Promise((resolve) => setTimeout(resolve, 1500))
      }
    }
    void poll()
    return () => {
      stopped = true
    }
  }, [])

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setRunning(true)
    setError(null)
    try {
      const next = await fetchForecast({
        symbol: symbol.trim(),
        timeframe,
        horizon: Number(horizon),
        samples: Number(samples),
        mode,
        holdout: Number(holdout),
      })
      setResult(next)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Forecast failed.")
    } finally {
      setRunning(false)
    }
  }

  const busy = modelState !== "ready" || running

  return (
    <div className="mx-auto flex min-h-svh max-w-5xl flex-col gap-8 px-6 py-10">
      <header className="flex flex-col gap-4 border-b border-border pb-6">
        <div className="flex items-center justify-between gap-4">
          <p className="text-[0.625rem] font-semibold tracking-widest text-muted-foreground uppercase">
            Kronos-mini
          </p>
          <Badge variant="secondary">Not financial advice</Badge>
        </div>
        <h1 className="font-heading text-4xl tracking-tight">Forecast fan</h1>
        <p className="max-w-2xl text-sm leading-6 text-muted-foreground">
          Sample a fan of next candles from recent OHLCV. Crypto pairs ending in USDT use Binance public
          klines. Other tickers, such as AAPL, use Yahoo Finance. Nothing here is a trade.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Market</CardTitle>
          <CardDescription>
            {modelState === "loading" && "Loading Kronos-mini. The first start downloads the weights."}
            {modelState === "ready" && "Model is on CPU and ready to sample."}
            {modelState === "error" && (modelError ?? "The model failed to load.")}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form className="grid gap-6 md:grid-cols-6" onSubmit={onSubmit}>
            <div className="flex flex-col gap-2 md:col-span-2">
              <Label htmlFor="symbol">Symbol</Label>
              <Input
                id="symbol"
                value={symbol}
                onChange={(event) => setSymbol(event.target.value.toUpperCase())}
                placeholder="BTCUSDT"
                autoCapitalize="characters"
                spellCheck={false}
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label>Timeframe</Label>
              <Select value={timeframe} onValueChange={(value) => setTimeframe(value)}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {TIMEFRAMES.map((item) => (
                    <SelectItem key={item.value} value={item.value}>
                      {item.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-2">
              <Label>Mode</Label>
              <Select value={mode} onValueChange={(value) => setMode(value as ForecastMode)}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="forecast">Forecast</SelectItem>
                  <SelectItem value="test">Test</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {mode === "forecast" ? (
              <div className="flex flex-col gap-2">
                <Label>Horizon</Label>
                <Select value={horizon} onValueChange={setHorizon}>
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="12">12 bars</SelectItem>
                    <SelectItem value="24">24 bars</SelectItem>
                    <SelectItem value="48">48 bars</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                <Label>Holdout</Label>
                <Select value={holdout} onValueChange={setHoldout}>
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="8">Last 8</SelectItem>
                    <SelectItem value="12">Last 12</SelectItem>
                    <SelectItem value="24">Last 24</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}
            <div className="flex flex-col gap-2">
              <Label>Paths</Label>
              <Select value={samples} onValueChange={setSamples}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="4">4</SelectItem>
                  <SelectItem value="8">8</SelectItem>
                  <SelectItem value="12">12</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="md:col-span-6">
              <Button type="submit" disabled={busy}>
                {running ? "Sampling…" : mode === "test" ? "Run blind test" : "Run forecast"}
              </Button>
            </div>
          </form>
          {error ? <p className="mt-4 text-sm text-destructive">{error}</p> : null}
        </CardContent>
      </Card>

      {result ? (
        <>
          <Card>
            <CardHeader>
              <CardTitle>
                {result.symbol} · {result.timeframe}
              </CardTitle>
              <CardDescription>
                Olive and rose candles are the latest history. The model still reads up to 400 bars.
                Stone lines are sampled closes. The dark line is the median.
                {result.mode === "test" ? " Blue candles are the held-out actual bars." : ""}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <CandleChart result={result} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Summary</CardTitle>
              <CardDescription>
                {result.paths.length} paths in {result.elapsedSeconds.toFixed(1)}s on CPU.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-3 text-sm leading-6">
              <p>{result.summary.text}</p>
              {result.score ? <p>{result.score.text}</p> : null}
              <p className="font-semibold tracking-widest uppercase">{result.disclaimer}</p>
            </CardContent>
          </Card>
        </>
      ) : null}
    </div>
  )
}
