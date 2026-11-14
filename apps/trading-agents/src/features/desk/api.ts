import type { Health, RunRequest, SseMessage } from "./types"

export async function fetchHealth(signal?: AbortSignal): Promise<Health> {
  const response = await fetch("/api/health", { signal })
  if (!response.ok) {
    throw new Error(`The research sidecar is not available (${response.status}).`)
  }
  return response.json() as Promise<Health>
}

function parseBlock(block: string): SseMessage | null {
  let event = "message"
  const dataLines: string[] = []
  for (const line of block.split("\n")) {
    if (line.startsWith(":")) continue
    if (line.startsWith("event:")) event = line.slice(6).trim()
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim())
  }
  if (dataLines.length === 0) return null
  const data = JSON.parse(dataLines.join("\n")) as SseMessage["data"]
  if (event === "meta" || event === "sources" || event === "stage" || event === "done" || event === "error") {
    return { event, data } as SseMessage
  }
  return null
}

async function errorDetail(response: Response): Promise<string> {
  const text = await response.text()
  try {
    const body = JSON.parse(text) as { detail?: unknown }
    if (typeof body.detail === "string") return body.detail
  } catch {
    if (text.trim()) return text.trim()
  }
  return `Request failed (${response.status}).`
}

export async function streamRun(
  body: RunRequest,
  onEvent: (message: SseMessage) => void,
  signal: AbortSignal,
): Promise<void> {
  const response = await fetch("/api/run", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(body),
    signal,
  })
  if (!response.ok || !response.body) {
    throw new Error(await errorDetail(response))
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""
  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const blocks = buffer.split("\n\n")
    buffer = blocks.pop() ?? ""
    for (const block of blocks) {
      const message = parseBlock(block)
      if (message) onEvent(message)
    }
  }
}
