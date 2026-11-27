import { useEffect, useMemo, useRef, useState } from "react"
import * as pdfjs from "pdfjs-dist"
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url"
import { boxToPercent, relatedOverlayIds } from "./geometry"
import type { LoadedFile, OverlayKind, ShapedPage } from "./types"

let workerReady = false

function configurePdf() {
  if (workerReady) return
  pdfjs.GlobalWorkerOptions.workerSrc = workerUrl
  workerReady = true
}

const KIND_CLASS: Record<OverlayKind, string> = {
  text: "border-sky-800/80 bg-sky-500/15",
  table: "border-amber-800/90 bg-amber-500/15",
  heading: "border-violet-800/80 bg-violet-500/10",
  paragraph: "border-emerald-900/70 bg-emerald-600/10",
  list: "border-emerald-900/70 bg-emerald-600/10",
  figure: "border-rose-800/80 bg-rose-500/10",
  code: "border-stone-700/80 bg-stone-500/10",
  rule: "border-stone-600/80 bg-stone-500/20",
  other: "border-stone-700/70 bg-stone-500/10",
}

function fitMedia(node: HTMLCanvasElement | HTMLImageElement) {
  const host = node.parentElement?.parentElement
  const maxWidth = host?.clientWidth || node.clientWidth || 640
  const naturalWidth = node instanceof HTMLCanvasElement ? node.width : node.naturalWidth
  const naturalHeight = node instanceof HTMLCanvasElement ? node.height : node.naturalHeight
  if (!naturalWidth || !naturalHeight) return
  const maxHeight = Math.max(280, window.innerHeight * 0.62)
  const scale = Math.min(maxWidth / naturalWidth, maxHeight / naturalHeight)
  node.style.width = `${Math.max(1, Math.floor(naturalWidth * scale))}px`
  node.style.height = `${Math.max(1, Math.floor(naturalHeight * scale))}px`
}

function stack(kind: OverlayKind): number {
  if (kind === "text") return 3
  if (kind === "table") return 2
  return 1
}

export function PageStage({
  file,
  page,
  hitId,
  showText,
  showTable,
  showLayout,
  onHit,
}: {
  file: LoadedFile
  page: ShapedPage
  hitId: string | null
  showText: boolean
  showTable: boolean
  showLayout: boolean
  onHit: (id: string | null) => void
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const hostRef = useRef<HTMLDivElement>(null)
  const [renderError, setRenderError] = useState<string | null>(null)
  const [painted, setPainted] = useState(false)
  const active = new Set(relatedOverlayIds(page.overlays, hitId))
  const imageUrl = useMemo(() => {
    if (file.kind !== "image") return null
    return URL.createObjectURL(new Blob([file.bytes.slice()], { type: file.mime }))
  }, [file])

  useEffect(() => {
    if (!imageUrl) return
    return () => URL.revokeObjectURL(imageUrl)
  }, [imageUrl])

  useEffect(() => {
    const host = hostRef.current
    if (!host) return
    const observer = new ResizeObserver(() => {
      const media = host.querySelector("canvas, img")
      if (media instanceof HTMLCanvasElement || media instanceof HTMLImageElement) fitMedia(media)
    })
    observer.observe(host)
    return () => observer.disconnect()
  }, [file, page.pageNum, imageUrl])

  useEffect(() => {
    if (file.kind !== "pdf") return
    const canvas = canvasRef.current
    if (!canvas) return
    let cancel = false
    setPainted(false)
    configurePdf()
    const task = pdfjs.getDocument({ data: file.bytes.slice() })
    task.promise
      .then(async (pdf) => {
        const pdfPage = await pdf.getPage(page.pageNum)
        if (cancel) return
        const viewport = pdfPage.getViewport({ scale: 1.5 })
        canvas.width = viewport.width
        canvas.height = viewport.height
        await pdfPage.render({ canvas, viewport }).promise
        if (cancel) return
        fitMedia(canvas)
        setPainted(true)
        setRenderError(null)
      })
      .catch((error: unknown) => {
        if (cancel) return
        setRenderError(error instanceof Error ? error.message : String(error))
      })
    return () => {
      cancel = true
      void task.destroy()
    }
  }, [file, page.pageNum])

  const overlays = page.overlays.filter((overlay) => {
    if (overlay.kind === "text") return showText
    if (overlay.kind === "table") return showTable
    return showLayout
  })

  return (
    <div className="flex min-h-0 flex-col gap-3">
      <div ref={hostRef} className="relative min-h-0 w-full flex-1 overflow-auto bg-[#f7f3ea] ring-1 ring-foreground/10">
        <div className="relative mx-auto w-fit max-w-full">
          {file.kind === "pdf" ? (
            <canvas ref={canvasRef} className="block max-w-full" />
          ) : imageUrl ? (
            <img
              src={imageUrl}
              alt={file.name}
              className="block max-w-full"
              onLoad={(event) => {
                fitMedia(event.currentTarget)
                setPainted(true)
              }}
            />
          ) : null}
          <div className="pointer-events-none absolute inset-0">
            {painted
              ? overlays.map((overlay) => {
              const box = boxToPercent(overlay.box, page)
              const on = active.has(overlay.id)
              return (
                <button
                  key={overlay.id}
                  type="button"
                  data-testid="overlay"
                  data-kind={overlay.kind}
                  data-hit={overlay.id}
                  title={overlay.text}
                  className={`pointer-events-auto absolute border ${KIND_CLASS[overlay.kind]} ${on ? "z-10 border-2 border-foreground bg-primary/25" : ""}`}
                  style={{
                    left: `${box.left}%`,
                    top: `${box.top}%`,
                    width: `${box.width}%`,
                    height: `${box.height}%`,
                    zIndex: on ? 10 : stack(overlay.kind),
                  }}
                  onMouseEnter={() => onHit(overlay.id)}
                  onMouseLeave={() => onHit(null)}
                  onClick={() => onHit(overlay.id)}
                />
              )
            })
              : null}
          </div>
        </div>
      </div>
      {renderError ? <p className="text-sm text-destructive">{renderError}</p> : null}
    </div>
  )
}
