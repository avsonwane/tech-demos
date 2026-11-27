import init, { OcriaNano } from "@llamaindex/liteparse-wasm"

export type ModelPhase =
  | { phase: "idle" }
  | { phase: "wasm" }
  | { phase: "download"; loaded: number; total: number | null }
  | { phase: "ready"; hasLayout: boolean }
  | { phase: "error"; message: string }

type Listener = (phase: ModelPhase) => void

let lastPhase: ModelPhase = { phase: "idle" }
const listeners = new Set<Listener>()
let loading: Promise<OcriaNano> | null = null
let loaded: OcriaNano | null = null

function emit(phase: ModelPhase) {
  lastPhase = phase
  for (const listener of listeners) listener(phase)
}

export function subscribeModel(listener: Listener): () => void {
  listeners.add(listener)
  listener(lastPhase)
  return () => listeners.delete(listener)
}

export function ocriaHandle(): OcriaNano | null {
  return loaded
}

export function resetModel(): void {
  loading = null
  loaded = null
  emit({ phase: "idle" })
}

async function fromUrlWithProgress(): Promise<OcriaNano> {
  const original = globalThis.fetch.bind(globalThis)
  let loadedBytes = 0
  const declared: number[] = []

  globalThis.fetch = async (input, initRequest) => {
    const response = await original(input, initRequest)
    const length = Number(response.headers.get("content-length") || "0")
    if (Number.isFinite(length) && length > 0) declared.push(length)
    if (!response.body) return response
    const reader = response.body.getReader()
    const chunks: Uint8Array[] = []
    let size = 0
    while (true) {
      const step = await reader.read()
      if (step.done) break
      if (!step.value) continue
      chunks.push(step.value)
      size += step.value.byteLength
      loadedBytes += step.value.byteLength
      const total = declared.reduce((sum, value) => sum + value, 0)
      emit({
        phase: "download",
        loaded: loadedBytes,
        total: total > 0 ? total : null,
      })
    }
    const body = new Uint8Array(size)
    let offset = 0
    for (const chunk of chunks) {
      body.set(chunk, offset)
      offset += chunk.byteLength
    }
    return new Response(body, {
      status: response.status,
      statusText: response.statusText,
      headers: new Headers(response.headers),
    })
  }

  try {
    return await OcriaNano.fromUrl()
  } finally {
    globalThis.fetch = original
  }
}

async function pull(): Promise<OcriaNano> {
  emit({ phase: "wasm" })
  await init()
  emit({ phase: "download", loaded: 0, total: null })
  const ocria = await fromUrlWithProgress()
  loaded = ocria
  emit({ phase: "ready", hasLayout: ocria.hasLayoutModel })
  return ocria
}

export function ensureOcria(): Promise<OcriaNano> {
  if (loaded) return Promise.resolve(loaded)
  if (!loading) {
    loading = pull().catch((error: unknown) => {
      loading = null
      loaded = null
      const message = error instanceof Error ? error.message : String(error)
      emit({ phase: "error", message })
      throw error
    })
  }
  return loading
}
