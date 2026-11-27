import { fixtureDocument } from "./fixture"
import { ensureOcria } from "./model"
import {
  SAMPLE_NAME,
  loadSampleFile,
  parseWithOcria,
  parseWithTesseract,
  type ParseProgress,
} from "./parse"
import { createTesseractEngine, setTesseractLogger, type TessLog } from "./tesseract"
import type { LoadedFile, ShapedDocument } from "./types"

export interface BootResult {
  file: LoadedFile
  doc: ShapedDocument
  fixtureReason: string | null
}

let bootPromise: Promise<BootResult> | null = null
const parseListeners = new Set<(progress: ParseProgress & { engine: string }) => void>()

export function subscribeParse(
  listener: (progress: ParseProgress & { engine: string }) => void,
): () => void {
  parseListeners.add(listener)
  return () => parseListeners.delete(listener)
}

function emitParse(engine: string, progress: ParseProgress) {
  for (const listener of parseListeners) listener({ ...progress, engine })
}

async function runBoot(): Promise<BootResult> {
  const file = await loadSampleFile()
  try {
    const ocria = await ensureOcria()
    const doc = await parseWithOcria(ocria, file, (progress) => emitParse("ocria-nano", progress))
    return { file, doc, fixtureReason: null }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    return { file, doc: fixtureDocument(file.name || SAMPLE_NAME), fixtureReason: message }
  }
}

export function bootSample(): Promise<BootResult> {
  bootPromise ??= runBoot()
  return bootPromise
}

export function retrySample(): Promise<BootResult> {
  bootPromise = null
  return bootSample()
}

export async function parseOcriaFile(file: LoadedFile): Promise<ShapedDocument> {
  const ocria = await ensureOcria()
  return parseWithOcria(ocria, file, (progress) => emitParse("ocria-nano", progress))
}

export async function parseTesseractFile(
  file: LoadedFile,
  onLog: (message: TessLog) => void,
): Promise<ShapedDocument> {
  setTesseractLogger(onLog)
  try {
    return await parseWithTesseract(createTesseractEngine(), file, (progress) => {
      emitParse("tesseract", progress)
    })
  } finally {
    setTesseractLogger(null)
  }
}
