import type { ReportRow } from "./types"

export type Tone = "gain" | "loss" | "amber" | "plain"

export function band(kind: ReportRow["tone"], value: number | null): Tone {
  if (value == null || Number.isNaN(value)) return "plain"
  if (kind === "sharpe") {
    if (value < 0.5) return "loss"
    if (value <= 1) return "amber"
    return "gain"
  }
  if (kind === "drawdown") {
    if (value < -0.2) return "loss"
    if (value < -0.1) return "amber"
    return "gain"
  }
  if (kind === "winrate") {
    if (value < 0.4) return "loss"
    if (value <= 0.6) return "amber"
    return "gain"
  }
  if (kind === "ratio") {
    if (value > 1) return "gain"
    if (value < 1) return "loss"
    return "plain"
  }
  if (kind === "cost") {
    if (value > 0) return "loss"
    if (value < 0) return "gain"
    return "plain"
  }
  if (kind === "sign") {
    if (value > 0) return "gain"
    if (value < 0) return "loss"
    return "plain"
  }
  return "plain"
}

export function toneWord(kind: ReportRow["tone"], value: number | null): string | null {
  const painted = band(kind, value)
  if (kind === "sharpe" || kind === "winrate") {
    if (painted === "loss") return "Low"
    if (painted === "amber") return "Mid"
    if (painted === "gain") return "High"
  }
  if (kind === "drawdown") {
    if (painted === "loss") return "Deep"
    if (painted === "amber") return "Moderate"
    if (painted === "gain") return "Shallow"
  }
  return null
}

export function toneClass(tone: Tone): string {
  if (tone === "gain") return "bg-[var(--gain-bg)] text-[var(--gain)]"
  if (tone === "loss") return "bg-[var(--loss-bg)] text-[var(--loss)]"
  if (tone === "amber") return "bg-[var(--amber-bg)] text-[var(--amber)]"
  return ""
}

export function formatStat(value: number | null, unit: ReportRow["unit"], signed: boolean): string {
  if (value == null || Number.isNaN(value)) return "—"
  if (unit === "percent") {
    const number = value * 100
    const body = `${Math.abs(number).toFixed(2)}%`
    if (number > 0 && signed) return `+${body}`
    if (number < 0) return `−${body}`
    return body
  }
  if (unit === "money") {
    const body = Math.abs(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    if (value > 0 && signed) return `+${body}`
    if (value < 0) return `−${body}`
    return body
  }
  if (unit === "count") return String(Math.round(value))
  const body = Math.abs(value).toFixed(2)
  if (value > 0 && signed) return `+${body}`
  if (value < 0) return `−${body}`
  return body
}
