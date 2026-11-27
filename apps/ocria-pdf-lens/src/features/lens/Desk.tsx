import { useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { ExtractPanel } from "./ExtractPanel"
import { fixtureDocument } from "./fixture"
import { formatBytes, formatMs } from "./format"
import { PageStage } from "./PageStage"
import { fileFromDrop, loadSampleFile, SAMPLE_NAME } from "./parse"
import {
  bootSample,
  parseOcriaFile,
  parseTesseractFile,
  retrySample,
  subscribeParse,
} from "./session"
import { resetModel, subscribeModel, type ModelPhase } from "./model"
import type { LoadedFile, ParseEngine, ShapedDocument, ShapedPage } from "./types"

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

function pageAt(doc: ShapedDocument | null, index: number): ShapedPage | null {
  if (!doc || doc.pages.length === 0) return null
  return doc.pages[Math.min(index, doc.pages.length - 1)] ?? null
}

function timeLabel(page: ShapedPage, engine: ParseEngine): string {
  if (engine === "fixture") return "not timed"
  return formatMs(page.ms)
}

export function Desk() {
  const inputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<LoadedFile | null>(null)
  const [doc, setDoc] = useState<ShapedDocument | null>(null)
  const [tess, setTess] = useState<ShapedDocument | null>(null)
  const [compare, setCompare] = useState(false)
  const [pageIndex, setPageIndex] = useState(0)
  const [hit, setHit] = useState<{ engine: ParseEngine; id: string } | null>(null)
  const [layers, setLayers] = useState({ text: true, table: true, layout: true })
  const [dragOver, setDragOver] = useState(false)
  const [activity, setActivity] = useState("Opening the bundled scan…")
  const [download, setDownload] = useState<{ loaded: number; total: number | null } | null>(null)
  const [fixtureReason, setFixtureReason] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [tessError, setTessError] = useState<string | null>(null)
  const [busy, setBusy] = useState(true)
  const [hasLayout, setHasLayout] = useState<boolean | null>(null)

  useEffect(() => {
    const unsubModel = subscribeModel((phase) => applyModel(phase, setActivity, setDownload, setHasLayout))
    const unsubParse = subscribeParse((progress) => {
      const label = progress.engine === "tesseract" ? "Tesseract.js" : "OCRia-nano-1"
      const total = progress.total ? ` of ${progress.total}` : ""
      setActivity(`Reading page ${progress.page}${total} with ${label}…`)
    })
    let cancel = false
    void bootSample().then((result) => {
      if (cancel) return
      setFile(result.file)
      setDoc(result.doc)
      setFixtureReason(result.fixtureReason)
      setBusy(false)
      setActivity("")
    })
    return () => {
      cancel = true
      unsubModel()
      unsubParse()
    }
  }, [])

  async function runOcria(next: LoadedFile) {
    setBusy(true)
    setError(null)
    setFixtureReason(null)
    setTess(null)
    setCompare(false)
    setHit(null)
    setPageIndex(0)
    setDoc(null)
    setFile(next)
    try {
      const parsed = await parseOcriaFile(next)
      setDoc(parsed)
      setActivity("")
    } catch (caught) {
      const reason = messageOf(caught)
      if (next.name === SAMPLE_NAME) {
        setDoc(fixtureDocument(SAMPLE_NAME))
        setFixtureReason(reason)
      } else {
        setError(reason)
      }
      setActivity("")
    } finally {
      setBusy(false)
    }
  }

  async function onSample() {
    try {
      await runOcria(await loadSampleFile())
    } catch (caught) {
      setError(messageOf(caught))
      setBusy(false)
    }
  }

  async function onFiles(list: FileList | null) {
    const first = list?.[0]
    if (!first) return
    try {
      await runOcria(await fileFromDrop(first))
    } catch (caught) {
      setError(messageOf(caught))
    }
  }

  async function onCompare() {
    if (!file || doc?.engine === "fixture") return
    if (tess) {
      setCompare((value) => !value)
      return
    }
    setBusy(true)
    setTessError(null)
    setCompare(true)
    try {
      const parsed = await parseTesseractFile(file, (log) => {
        const pct = Math.round(log.progress * 100)
        setActivity(`Tesseract.js · ${log.status} ${pct}%`)
      })
      setTess(parsed)
      setActivity("")
    } catch (caught) {
      setTessError(messageOf(caught))
      setCompare(false)
      setActivity("")
    } finally {
      setBusy(false)
    }
  }

  const ocriaPage = pageAt(doc, pageIndex)
  const tessPage = pageAt(tess, pageIndex)
  const showCompare = compare && tess && tessPage && file

  return (
    <div
      className="flex h-svh flex-col"
      onDragOver={(event) => {
        event.preventDefault()
        setDragOver(true)
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(event) => {
        event.preventDefault()
        setDragOver(false)
        void onFiles(event.dataTransfer.files)
      }}
    >
      <header className="flex flex-wrap items-end justify-between gap-4 border-b border-foreground/10 px-5 py-4">
        <div>
          <p className="text-xs font-semibold tracking-widest text-muted-foreground uppercase">Local CPU OCR</p>
          <h1 className="font-heading text-3xl leading-none">OCRia PDF Lens</h1>
          <p className="mt-1 max-w-xl text-sm text-muted-foreground">
            OCRia-nano-1 through LiteParse, in this browser. The file is not uploaded.
            {hasLayout ? " LayoutNet is loaded." : ""}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button type="button" variant="outline" disabled={busy} onClick={() => void onSample()}>
            Bundled sample
          </Button>
          <Button type="button" disabled={busy} onClick={() => inputRef.current?.click()}>
            Drop a PDF
          </Button>
          <Button
            type="button"
            variant={showCompare ? "default" : "outline"}
            disabled={busy || !doc || doc.engine === "fixture"}
            onClick={() => void onCompare()}
          >
            {showCompare ? "Hide Tesseract" : "Compare Tesseract"}
          </Button>
          <input
            ref={inputRef}
            type="file"
            accept="application/pdf,image/png,image/jpeg,.pdf,.png,.jpg,.jpeg"
            className="hidden"
            onChange={(event) => {
              void onFiles(event.target.files)
              event.target.value = ""
            }}
          />
        </div>
      </header>

      {fixtureReason ? (
        <div className="border-b border-foreground/10 bg-muted px-5 py-3 text-sm" data-testid="fixture-banner">
          <p className="font-semibold tracking-widest uppercase">Fixture mode</p>
          <p className="mt-1">
            OCRia-nano-1 did not load ({fixtureReason}). This is a saved reading of the bundled sample, not a live parse. The timer is blank.
          </p>
          <Button
            type="button"
            variant="outline"
            className="mt-2"
            onClick={() => {
              resetModel()
              setBusy(true)
              setFixtureReason(null)
              void retrySample().then((result) => {
                setFile(result.file)
                setDoc(result.doc)
                setFixtureReason(result.fixtureReason)
                setBusy(false)
              })
            }}
          >
            Retry model download
          </Button>
        </div>
      ) : null}

      {activity ? (
        <div className="border-b border-foreground/10 px-5 py-2" data-testid="activity">
          <p className="text-sm">{activity}</p>
          {download ? (
            <div className="mt-2 h-1 overflow-hidden bg-muted">
              <div
                className={download.total ? "h-full bg-primary" : "lens-indeterminate h-full bg-primary"}
                style={
                  download.total
                    ? { width: `${Math.min(100, (download.loaded / download.total) * 100)}%` }
                    : undefined
                }
              />
            </div>
          ) : null}
        </div>
      ) : null}

      {error ? <p className="px-5 py-2 text-sm text-destructive">{error}</p> : null}
      {tessError ? <p className="px-5 py-2 text-sm text-destructive">{tessError}</p> : null}

      {doc && ocriaPage && file ? (
        <main className={`min-h-0 flex-1 overflow-auto px-5 py-4 ${dragOver ? "bg-primary/5" : ""}`}>
          <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
            <div className="flex flex-wrap gap-2">
              {doc.pages.map((page, index) => (
                <button
                  key={page.pageNum}
                  type="button"
                  data-testid={`page-tab-${page.pageNum}`}
                  className={`border px-3 py-2 text-left ${index === pageIndex ? "border-foreground" : "border-foreground/15"}`}
                  onClick={() => {
                    setPageIndex(index)
                    setHit(null)
                  }}
                >
                  <span className="block text-xs font-semibold tracking-widest uppercase">Page {page.pageNum}</span>
                  <span className="font-heading text-2xl tabular-nums" data-testid="page-ms">
                    {timeLabel(page, doc.engine)}
                  </span>
                  {showCompare && tess?.pages[index] ? (
                    <span className="block text-xs text-muted-foreground">
                      Tesseract {timeLabel(tess.pages[index], tess.engine)}
                    </span>
                  ) : null}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap gap-2 text-xs font-semibold tracking-widest uppercase">
              <LayerButton on={layers.text} label="Text" swatch="bg-sky-500" onClick={() => setLayers((value) => ({ ...value, text: !value.text }))} />
              <LayerButton on={layers.table} label="Tables" swatch="bg-amber-500" onClick={() => setLayers((value) => ({ ...value, table: !value.table }))} />
              <LayerButton on={layers.layout} label="Layout" swatch="bg-violet-500" onClick={() => setLayers((value) => ({ ...value, layout: !value.layout }))} />
            </div>
          </div>

          {showCompare && tessPage ? (
            <div className="grid gap-6 xl:grid-cols-2 xl:items-start">
              <EngineColumn
                title="OCRia-nano-1"
                file={file}
                page={ocriaPage}
                engine={doc.engine}
                hitId={hit?.engine === doc.engine ? hit.id : null}
                layers={layers}
                onHit={(id) => setHit(id ? { engine: doc.engine, id } : null)}
              />
              <EngineColumn
                title="Tesseract.js"
                file={file}
                page={tessPage}
                engine={tess.engine}
                hitId={hit?.engine === tess.engine ? hit.id : null}
                layers={layers}
                onHit={(id) => setHit(id ? { engine: tess.engine, id } : null)}
              />
            </div>
          ) : (
            <div className="grid min-h-0 gap-6 lg:grid-cols-[minmax(0,1.15fr)_minmax(18rem,0.85fr)]">
              <section>
                <EngineTitle title="OCRia-nano-1" page={ocriaPage} engine={doc.engine} />
                <PageStage
                  file={file}
                  page={ocriaPage}
                  hitId={hit?.engine === doc.engine ? hit.id : null}
                  showText={layers.text}
                  showTable={layers.table}
                  showLayout={layers.layout}
                  onHit={(id) => setHit(id ? { engine: doc.engine, id } : null)}
                />
              </section>
              <ExtractPanel
                page={ocriaPage}
                hitId={hit?.engine === doc.engine ? hit.id : null}
                onHit={(id) => setHit(id ? { engine: doc.engine, id } : null)}
              />
            </div>
          )}
          <p className="mt-4 text-xs text-muted-foreground">{file.name}</p>
        </main>
      ) : (
        <main className="flex flex-1 items-center justify-center px-5 text-sm text-muted-foreground">
          {busy ? "Preparing the desk…" : "Drop a PDF or image to begin."}
        </main>
      )}
    </div>
  )
}

function EngineColumn({
  title,
  file,
  page,
  engine,
  hitId,
  layers,
  onHit,
}: {
  title: string
  file: LoadedFile
  page: ShapedPage
  engine: ParseEngine
  hitId: string | null
  layers: { text: boolean; table: boolean; layout: boolean }
  onHit: (id: string | null) => void
}) {
  return (
    <section className="flex min-w-0 flex-col gap-4">
      <EngineTitle title={title} page={page} engine={engine} />
      <PageStage
        file={file}
        page={page}
        hitId={hitId}
        showText={layers.text}
        showTable={layers.table}
        showLayout={layers.layout}
        onHit={onHit}
      />
      <ExtractPanel page={page} hitId={hitId} onHit={onHit} />
    </section>
  )
}

function EngineTitle({ title, page, engine }: { title: string; page: ShapedPage; engine: ParseEngine }) {
  return (
    <div className="mb-2 flex items-baseline justify-between gap-3">
      <h2 className="font-heading text-lg tracking-wide uppercase">{title}</h2>
      <p className="font-heading text-xl tabular-nums" data-testid={`time-${engine}`}>
        {timeLabel(page, engine)}
      </p>
    </div>
  )
}

function LayerButton({
  on,
  label,
  swatch,
  onClick,
}: {
  on: boolean
  label: string
  swatch: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      aria-pressed={on}
      className={`inline-flex items-center gap-2 border px-2 py-1 ${on ? "border-foreground" : "border-foreground/15 text-muted-foreground"}`}
      onClick={onClick}
    >
      <span className={`size-2 ${swatch}`} />
      {label}
    </button>
  )
}

function applyModel(
  phase: ModelPhase,
  setActivity: (value: string) => void,
  setDownload: (value: { loaded: number; total: number | null } | null) => void,
  setHasLayout: (value: boolean) => void,
) {
  if (phase.phase === "wasm") {
    setDownload(null)
    setActivity("Loading the LiteParse parser…")
  } else if (phase.phase === "download") {
    const total = phase.total ? ` / ${formatBytes(phase.total)}` : ""
    setDownload({ loaded: phase.loaded, total: phase.total })
    setActivity(`Downloading OCRia-nano-1 · ${formatBytes(phase.loaded)}${total}`)
  } else if (phase.phase === "ready") {
    setDownload(null)
    setHasLayout(phase.hasLayout)
  }
}
