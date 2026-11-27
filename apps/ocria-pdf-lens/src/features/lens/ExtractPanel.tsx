import { useEffect, useRef } from "react"
import { ScrollArea } from "@/components/ui/scroll-area"
import { relatedOverlayIds } from "./geometry"
import type { ShapedPage } from "./types"

export function ExtractPanel({
  page,
  hitId,
  onHit,
}: {
  page: ShapedPage
  hitId: string | null
  onHit: (id: string | null) => void
}) {
  const rootRef = useRef<HTMLDivElement>(null)
  const active = new Set(relatedOverlayIds(page.overlays, hitId))
  const selected = page.overlays.find((overlay) => overlay.id === hitId)

  useEffect(() => {
    if (!hitId || !rootRef.current) return
    const node = rootRef.current.querySelector(`[data-hit="${CSS.escape(hitId)}"]`)
    node?.scrollIntoView({ block: "nearest" })
  }, [hitId])

  return (
    <div ref={rootRef} className="flex min-h-0 flex-col gap-4">
      {selected?.text ? (
        <p className="text-sm" data-testid="selected-text">
          <span className="font-semibold tracking-widest uppercase text-muted-foreground">Selected </span>
          {selected.text}
        </p>
      ) : (
        <p className="text-sm text-muted-foreground">Hover a box or a line to link the page and the text.</p>
      )}
      <section className="min-h-0">
        <h3 className="font-heading text-sm font-semibold tracking-wider uppercase">Markdown</h3>
        <ScrollArea className="mt-2 h-52 ring-1 ring-foreground/10">
          <pre
            data-testid="markdown"
            className="p-3 font-mono text-xs leading-5 whitespace-pre-wrap"
          >
            {page.markdown || "No markdown on this page."}
          </pre>
        </ScrollArea>
      </section>
      <section>
        <h3 className="font-heading text-sm font-semibold tracking-wider uppercase">Tables</h3>
        {page.tables.length === 0 ? (
          <p className="mt-2 text-sm text-muted-foreground">No table on this page.</p>
        ) : (
          <div className="mt-2 flex flex-col gap-3">
            {page.tables.map((table) => (
              <div key={table.id} className="overflow-x-auto ring-1 ring-foreground/10" data-testid="table">
                <table className="w-full border-collapse text-sm">
                  {table.header.length > 0 ? (
                    <thead>
                      <tr className="bg-muted">
                        {table.header.map((cell, index) => (
                          <th key={index} className="px-2 py-1 text-left font-semibold">
                            {cell.text}
                          </th>
                        ))}
                      </tr>
                    </thead>
                  ) : null}
                  <tbody>
                    {table.rows.map((row, rowIndex) => (
                      <tr key={rowIndex}>
                        {row.map((cell, cellIndex) => {
                          const hit = cell.textItemIndices[0]
                          const id = hit === undefined ? table.id : `p${page.pageNum}-t${hit}`
                          const on = active.has(id) || active.has(table.id)
                          return (
                            <td key={cellIndex} className="p-0">
                              <button
                                type="button"
                                data-hit={id}
                                className={`block w-full px-2 py-1 text-left ${on ? "bg-primary/20" : "hover:bg-muted"}`}
                                onMouseEnter={() => onHit(id)}
                                onMouseLeave={() => onHit(null)}
                                onClick={() => onHit(id)}
                              >
                                {cell.text || " "}
                              </button>
                            </td>
                          )
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
