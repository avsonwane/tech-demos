import type { ForecastRequest, ForecastResponse } from "@/features/forecast/types"

export async function fetchHealth(): Promise<{ ready: boolean; error: string | null }> {
  const response = await fetch("/api/health")
  if (!response.ok) {
    throw new Error("The forecast service is not responding.")
  }
  const body = (await response.json()) as { ready: boolean; error: string | null }
  return body
}

export async function fetchForecast(request: ForecastRequest): Promise<ForecastResponse> {
  const response = await fetch("/api/forecast", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  })
  const body = (await response.json().catch(() => ({}))) as { detail?: string }
  if (!response.ok) {
    const detail = typeof body.detail === "string" ? body.detail : `Request failed (${response.status}).`
    throw new Error(detail)
  }
  return body as ForecastResponse
}
