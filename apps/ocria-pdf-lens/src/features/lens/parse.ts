import { LiteParse, type OcriaNano, type OcrEngine } from "@llamaindex/liteparse-wasm"
import { shapePage } from "./shape"
import type { LoadedFile, ParseEngine, RawPage, ShapedDocument, ShapedPage } from "./types"

interface WasmPage {
  pageNum: number
  width: number
  height: number
  text?: string
  markdown?: string
  textItems?: RawPage["textItems"]
  blocks?: RawPage["blocks"]
}

interface WasmBatch {
  result?: { pages?: WasmPage[] }
}

export interface ParseProgress {
  page: number
  total: number | null
}

function asRaw(page: WasmPage): RawPage {
  return {
    pageNum: page.pageNum,
    width: page.width,
    height: page.height,
    text: page.text,
    markdown: page.markdown,
    textItems: page.textItems,
    blocks: page.blocks,
  }
}

async function parseBatched(
  parser: LiteParse,
  bytes: Uint8Array,
  onPage: (page: number, total: number | null) => void,
): Promise<ShapedPage[]> {
  const session = await parser.openBatchSession(bytes, 1)
  try {
    const total = session.totalPages
    const pages: ShapedPage[] = []
    let index = 0
    while (index < total) {
      onPage(index + 1, total)
      const started = performance.now()
      const batch = (await session.nextBatch()) as WasmBatch | undefined
      const elapsed = performance.now() - started
      const batchPages = batch?.result?.pages ?? []
      if (batchPages.length === 0) break
      for (const page of batchPages) {
        pages.push(shapePage(asRaw(page), elapsed))
        index += 1
      }
    }
    return pages
  } finally {
    session.free()
  }
}

async function run(
  parser: LiteParse,
  file: LoadedFile,
  engine: ParseEngine,
  onPage: (progress: ParseProgress) => void,
): Promise<ShapedDocument> {
  try {
    const pages = await parseBatched(parser, file.bytes.slice(), (page, total) => {
      onPage({ page, total })
    })
    return { sourceName: file.name, engine, pages }
  } finally {
    parser.free()
  }
}

const PARSE_OPTIONS = {
  ocrEnabled: true,
  outputFormat: "markdown" as const,
  extractBlocks: true,
  imageMode: "off" as const,
  numWorkers: 1,
}

export function parseWithOcria(
  ocria: OcriaNano,
  file: LoadedFile,
  onPage: (progress: ParseProgress) => void,
): Promise<ShapedDocument> {
  const parser = LiteParse.withOcriaNano(PARSE_OPTIONS, ocria)
  return run(parser, file, "ocria-nano", onPage)
}

export function parseWithTesseract(
  engine: OcrEngine,
  file: LoadedFile,
  onPage: (progress: ParseProgress) => void,
): Promise<ShapedDocument> {
  const parser = new LiteParse({
    ...PARSE_OPTIONS,
    ocrLanguage: "eng",
    ocrEngine: engine,
  })
  return run(parser, file, "tesseract", onPage)
}

export function fileFromDrop(file: File): Promise<LoadedFile> {
  const mime = file.type || guessMime(file.name)
  const kind = mime === "application/pdf" || file.name.toLowerCase().endsWith(".pdf") ? "pdf" : "image"
  if (kind === "image" && !/^image\/(png|jpeg)$/.test(mime) && !/\.(png|jpe?g)$/i.test(file.name)) {
    return Promise.reject(new Error("Drop a PDF, PNG, or JPEG."))
  }
  return file.arrayBuffer().then((buffer) => ({
    name: file.name,
    bytes: new Uint8Array(buffer),
    mime: kind === "pdf" ? "application/pdf" : mime || "image/png",
    kind,
  }))
}

function guessMime(name: string): string {
  if (name.toLowerCase().endsWith(".pdf")) return "application/pdf"
  if (name.toLowerCase().endsWith(".png")) return "image/png"
  if (/\.jpe?g$/i.test(name)) return "image/jpeg"
  return ""
}

export const SAMPLE_NAME = "invoice-scan.pdf"
export const SAMPLE_URL = "/sample/invoice-scan.pdf"

export async function loadSampleFile(): Promise<LoadedFile> {
  const response = await fetch(SAMPLE_URL)
  if (!response.ok) throw new Error(`Sample PDF failed to load (${response.status}).`)
  return {
    name: SAMPLE_NAME,
    bytes: new Uint8Array(await response.arrayBuffer()),
    mime: "application/pdf",
    kind: "pdf",
  }
}
