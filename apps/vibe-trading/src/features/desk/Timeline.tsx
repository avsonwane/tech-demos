import { Badge } from "@/components/ui/badge"
import type { Phase } from "./types"

const ORDER = [
  { id: "plan", title: "Plan", index: "01" },
  { id: "ground", title: "Ground", index: "02" },
  { id: "code", title: "Code", index: "03" },
  { id: "execution", title: "Execution", index: "04" },
] as const

type TimelineProps = {
  phases: Record<string, Phase>
  running: boolean
}

export function Timeline({ phases, running }: TimelineProps) {
  return (
    <ol className="mt-10">
      {ORDER.map((step) => {
        const phase = phases[step.id]
        const status = phase?.status ?? "waiting"
        const active = running && status === "working"
        return (
          <li key={step.id} className="relative border-l border-foreground/15 pb-10 pl-6">
            <span
              className={
                active
                  ? "absolute top-1.5 left-0 size-2 -translate-x-1/2 animate-pulse bg-foreground"
                  : "absolute top-1.5 left-0 size-2 -translate-x-1/2 bg-foreground/30"
              }
            />
            <div className="mb-3 flex items-baseline justify-between gap-3">
              <h3 className="font-heading text-lg tracking-wide uppercase">
                <span className="mr-2 text-muted-foreground">{step.index}</span>
                {phase?.title ?? step.title}
              </h3>
              {active ? <Badge variant="secondary">Working</Badge> : null}
              {status === "done" ? <Badge variant="outline">Done</Badge> : null}
            </div>
            {phase?.body ? (
              <p className="text-sm leading-relaxed whitespace-pre-wrap">{phase.body}</p>
            ) : (
              <p className="text-sm text-muted-foreground">{active ? "Working" : "Waiting"}</p>
            )}
          </li>
        )
      })}
    </ol>
  )
}
