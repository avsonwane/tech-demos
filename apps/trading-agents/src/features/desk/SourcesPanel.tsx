import { Badge } from "@/components/ui/badge"
import type { SourceRow } from "./types"

const VARIANT = {
  ok: "default",
  failed: "destructive",
  skipped: "secondary",
  blocked: "destructive",
} as const

export function SourcesPanel({ sources }: { sources: SourceRow[] }) {
  if (sources.length === 0) return null
  return (
    <section id="data-sources" className="mt-8 border border-foreground/15 px-4 py-4" aria-label="Data sources">
      <h2 className="text-xs font-semibold tracking-widest uppercase">Data sources</h2>
      <ul className="mt-3 grid gap-2">
        {sources.map((source) => (
          <li key={source.id} className="grid grid-cols-[5.5rem_minmax(0,1fr)] gap-x-3 gap-y-0.5 text-sm sm:grid-cols-[5.5rem_11rem_minmax(0,1fr)]">
            <Badge variant={VARIANT[source.status]}>{source.status}</Badge>
            <span className="font-medium">{source.label}</span>
            <span className="col-span-2 text-muted-foreground sm:col-span-1">{source.detail}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}
