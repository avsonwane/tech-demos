import type { AgentReply, Health, MarketResponse, Packet } from "@/features/lens/types"

async function read<T>(response: Response): Promise<T> {
  const body = (await response.json()) as T & { error?: string }
  if (!response.ok) throw new Error(body.error || `Request failed (${response.status}).`)
  return body
}

export function fetchHealth(): Promise<Health> {
  return fetch("/api/health").then((response) => read<Health>(response))
}

export function fetchMarket(symbol: string, start: string, end: string): Promise<MarketResponse> {
  const query = new URLSearchParams({ symbol, start, end })
  return fetch(`/api/market?${query}`).then((response) => read<MarketResponse>(response))
}

export function askAgent(symbol: string, model: string, packet: Packet): Promise<AgentReply> {
  return fetch("/api/agent", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ symbol, model, packet }),
  }).then((response) => read<AgentReply>(response))
}
