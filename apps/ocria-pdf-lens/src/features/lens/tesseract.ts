import { createWorker } from "tesseract.js"
import type { OcrEngine } from "@llamaindex/liteparse-wasm"

type TessWord = {
  text?: string
  confidence?: number
  bbox?: { x0: number; y0: number; x1: number; y1: number }
}

type TessLine = TessWord & { words?: TessWord[] }
type TessParagraph = { lines?: TessLine[] }
type TessBlock = { paragraphs?: TessParagraph[] }
type TessPage = { blocks?: TessBlock[] | null; words?: TessWord[]; lines?: TessLine[] }

export type TessLog = { status: string; progress: number }

let workerPromise: Promise<Awaited<ReturnType<typeof createWorker>>> | null = null
let onLog: ((message: TessLog) => void) | null = null

export function setTesseractLogger(listener: ((message: TessLog) => void) | null) {
  onLog = listener
}

function worker() {
  workerPromise ??= createWorker("eng", 1, {
    logger: (message) => {
      onLog?.({ status: message.status, progress: message.progress })
    },
  })
  return workerPromise
}

function lineResults(page: TessPage): TessLine[] {
  if (page.lines && page.lines.length > 0) return page.lines
  const lines: TessLine[] = []
  for (const block of page.blocks ?? []) {
    for (const paragraph of block.paragraphs ?? []) {
      lines.push(...(paragraph.lines ?? []))
    }
  }
  if (lines.length > 0) return lines
  return page.words ?? []
}

export function createTesseractEngine(): OcrEngine {
  return {
    async recognize(imageData) {
      const engine = await worker()
      const copy = new Uint8Array(imageData.byteLength)
      copy.set(imageData)
      const blob = new Blob([copy], { type: "image/png" })
      const result = await engine.recognize(blob, {}, { text: true, blocks: true })
      const page = result.data as TessPage
      const lines = lineResults(page)
      return lines
        .map((line) => {
          const text = (line.text ?? "").trim()
          const bbox = line.bbox
          if (!text || !bbox) return null
          const confidence = line.confidence ?? 0
          return {
            text,
            bbox: [bbox.x0, bbox.y0, bbox.x1, bbox.y1] as [number, number, number, number],
            confidence: confidence > 1 ? Math.min(1, confidence / 100) : Math.max(0, confidence),
          }
        })
        .filter((item): item is NonNullable<typeof item> => item !== null)
    },
  }
}
