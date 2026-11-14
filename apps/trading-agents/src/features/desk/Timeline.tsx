import type { ReactNode } from "react"
import { Badge } from "@/components/ui/badge"
import type { Stage } from "./types"

const ANALYSTS = [
  { id: "market", title: "Market / technical" },
  { id: "social", title: "Sentiment" },
  { id: "news", title: "News" },
  { id: "fundamentals", title: "Fundamentals" },
] as const

type TimelineProps = {
  stages: Record<string, Stage>
  running: boolean
}

function byPhase(stages: Record<string, Stage>, phase: Stage["phase"]): Stage[] {
  return Object.values(stages)
    .filter((stage) => stage.phase === phase)
    .sort((a, b) => a.id.localeCompare(b.id, undefined, { numeric: true }))
}

function analystsReady(stages: Record<string, Stage>): boolean {
  return ANALYSTS.every((analyst) => stages[analyst.id]?.body)
}

function currentSection(stages: Record<string, Stage>, running: boolean): string | null {
  if (!running) return null
  if (!analystsReady(stages)) return "analysts"
  if (!stages["investment-plan"]) return "debate"
  if (!stages.trader) return "trader"
  if (!stages.decision) return "risk"
  return null
}

function Marker({ active }: { active: boolean }) {
  return (
    <span
      className={
        active
          ? "absolute top-1.5 left-0 size-2 -translate-x-1/2 animate-pulse bg-foreground"
          : "absolute top-1.5 left-0 size-2 -translate-x-1/2 bg-foreground/30"
      }
    />
  )
}

function Waiting({ active }: { active: boolean }) {
  return <p className="text-sm text-muted-foreground">{active ? "Working" : "Waiting"}</p>
}

function Prose({ body }: { body: string }) {
  return <p className="text-sm leading-relaxed whitespace-pre-wrap">{body}</p>
}

function Step({
  index,
  title,
  active,
  children,
}: {
  index: string
  title: string
  active: boolean
  children: ReactNode
}) {
  return (
    <li className="relative border-l border-foreground/15 pb-10 pl-6">
      <Marker active={active} />
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <h3 className="font-heading text-lg tracking-wide uppercase">
          <span className="mr-2 text-muted-foreground">{index}</span>
          {title}
        </h3>
        {active ? <Badge variant="secondary">Working</Badge> : null}
      </div>
      {children}
    </li>
  )
}

export function Timeline({ stages, running }: TimelineProps) {
  const current = currentSection(stages, running)
  const debate = byPhase(stages, "debate")
  const risk = byPhase(stages, "risk")
  const plan = stages["investment-plan"]
  const trader = stages.trader
  const decision = stages.decision

  return (
    <ol className="mt-10">
      <Step index="01" title="Analysts" active={current === "analysts"}>
        <div className="grid gap-6">
          {ANALYSTS.map((analyst) => {
            const stage = stages[analyst.id]
            return (
              <article key={analyst.id}>
                <h4 className="mb-1 text-xs font-semibold tracking-widest uppercase">{analyst.title}</h4>
                {stage?.body ? <Prose body={stage.body} /> : <Waiting active={current === "analysts"} />}
              </article>
            )
          })}
        </div>
      </Step>

      <Step index="02" title="Bull vs bear" active={current === "debate"}>
        {debate.length === 0 ? (
          <Waiting active={current === "debate"} />
        ) : (
          <div className="grid gap-5">
            {debate.map((turn) => (
              <article
                key={turn.id}
                className={turn.role === "bear" ? "ml-6 border-l border-foreground/25 pl-4 sm:ml-10" : "border-l border-foreground pl-4"}
              >
                <h4 className="mb-1 text-xs font-semibold tracking-widest uppercase">{turn.title}</h4>
                <Prose body={turn.body} />
              </article>
            ))}
          </div>
        )}
      </Step>

      <Step index="03" title="Research manager" active={Boolean(plan) && current === "trader"}>
        {plan ? <Prose body={plan.body} /> : <Waiting active={current === "debate" && debate.length > 0} />}
      </Step>

      <Step index="04" title="Trader" active={current === "trader"}>
        {trader ? <Prose body={trader.body} /> : <Waiting active={current === "trader"} />}
      </Step>

      <Step index="05" title="Risk team" active={current === "risk"}>
        {risk.length === 0 ? (
          <Waiting active={current === "risk"} />
        ) : (
          <div className="grid gap-5">
            {risk.map((turn) => (
              <article key={turn.id} className="border-l border-foreground/20 pl-4">
                <h4 className="mb-1 text-xs font-semibold tracking-widest uppercase">{turn.title}</h4>
                <Prose body={turn.body} />
              </article>
            ))}
          </div>
        )}
      </Step>

      <Step index="06" title="Decision" active={false}>
        {decision ? (
          <div>
            <p className="text-xs font-semibold tracking-widest text-muted-foreground uppercase">Paper decision</p>
            <p className="font-heading text-5xl tracking-wide">{decision.action ?? "REVIEW"}</p>
            {decision.rating ? (
              <p className="mt-2 text-sm text-muted-foreground">Framework rating: {decision.rating}</p>
            ) : null}
            <div className="mt-4">
              <Prose body={decision.body} />
            </div>
            <p className="mt-4 text-sm text-muted-foreground">Research/simulation only, not financial advice.</p>
          </div>
        ) : (
          <Waiting active={current === "risk" && risk.length > 0} />
        )}
      </Step>
    </ol>
  )
}
