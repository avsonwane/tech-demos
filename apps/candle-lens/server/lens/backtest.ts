// Fee-aware backtest of the official score-70 setups, compared with buy-and-hold.
// The Pine tracker itself has no fees. This desk adds them and flattens at the window end.

import type { Action, Bar } from "./packet.ts"

export type Currency = "INR" | "USD"

export type CostModel = {
  slippage: number
  buyRate: number
  sellRate: number
  capital: number
  currency: Currency
  note: string
}

export type Metrics = {
  returnPct: number
  cagrPct: number | null
  sharpe: number | null
  maxDrawdownPct: number
  winRatePct: number | null
  tradeCount: number
  fees: number
  endingEquity: number
}

export type Reality = {
  capital: number
  currency: Currency
  feeNote: string
  strategy: Metrics
  buyHold: Metrics
}

const FLATTEN =
  "Open positions are closed at the last close in the window so the strip is a full round trip. Chart levels are the indicator's, before fees and slippage."

export function indiaRates(): { buyRate: number; sellRate: number } {
  const brokerage = 0
  const exchange = 0.0000297
  const sebi = 0.000001
  const gst = (brokerage + exchange + sebi) * 0.18
  const variable = brokerage + exchange + sebi + gst + 0.001
  return { buyRate: variable + 0.00015, sellRate: variable }
}

export function isIndiaName(symbol: string): boolean {
  const upper = symbol.toUpperCase()
  return upper.endsWith(".NS") || upper.endsWith(".BO")
}

export function costModel(symbol: string): CostModel {
  if (isIndiaName(symbol)) {
    const { buyRate, sellRate } = indiaRates()
    return {
      slippage: 0.001,
      buyRate,
      sellRate,
      capital: 100_000,
      currency: "INR",
      note: `India delivery: slippage 10 bps, STT 10 bps, exchange 0.297 bps, SEBI 0.01 bps, stamp duty 1.5 bps on buys, GST 18% on brokerage, exchange, and SEBI. The Pine trade tracker itself has no fees. ${FLATTEN}`,
    }
  }
  return {
    slippage: 0.001,
    buyRate: 0.001,
    sellRate: 0.001,
    capital: 10_000,
    currency: "USD",
    note: `Slippage 10 bps and a 10 bps fee each way. The Pine trade tracker itself has no fees. ${FLATTEN}`,
  }
}

type Side = "LONG" | "SHORT"
type Position = {
  side: Side
  shares: number
  entryFill: number
  entryFee: number
  entryDate: string
}
type Closed = { pnl: number; fees: number }

function inWindow(date: string, start: string, end: string): boolean {
  return date >= start && date <= end
}

function slipped(price: number, worse: boolean, slippage: number): number {
  return price * (1 + (worse ? slippage : -slippage))
}

function entryFill(side: Side, price: number, slippage: number): number {
  return slipped(price, side === "LONG", slippage)
}

function exitFill(side: Side, price: number, slippage: number): number {
  return slipped(price, side === "SHORT", slippage)
}

function rate(side: Side, kind: "entry" | "exit", costs: CostModel): number {
  const buying = kind === "entry" ? side === "LONG" : side === "SHORT"
  return buying ? costs.buyRate : costs.sellRate
}

export function summarize(equity: number[], closed: Closed[], startDate: string, endDate: string, capital: number): Metrics {
  const ending = equity[equity.length - 1] ?? capital
  const returns: number[] = []
  for (let index = 1; index < equity.length; index++) {
    const previous = equity[index - 1]!
    if (previous > 0) returns.push(equity[index]! / previous - 1)
  }
  let sharpe: number | null = null
  if (returns.length >= 2) {
    const mean = returns.reduce((sum, value) => sum + value, 0) / returns.length
    const variance = returns.reduce((sum, value) => sum + (value - mean) ** 2, 0) / (returns.length - 1)
    const deviation = Math.sqrt(variance)
    sharpe = deviation === 0 ? null : (mean / deviation) * Math.sqrt(252)
  }
  let peak = equity[0] ?? capital
  let maxDrawdown = 0
  for (const value of equity) {
    if (value > peak) peak = value
    if (peak > 0) maxDrawdown = Math.min(maxDrawdown, value / peak - 1)
  }
  const start = Date.parse(`${startDate}T00:00:00Z`)
  const end = Date.parse(`${endDate}T00:00:00Z`)
  const days = (end - start) / 86_400_000
  let cagrPct: number | null = null
  if (days > 0 && capital > 0 && ending > 0) {
    cagrPct = ((ending / capital) ** (365.25 / days) - 1) * 100
  }
  const wins = closed.filter((trade) => trade.pnl > 0).length
  return {
    returnPct: capital > 0 ? (ending / capital - 1) * 100 : 0,
    cagrPct,
    sharpe,
    maxDrawdownPct: maxDrawdown * 100,
    winRatePct: closed.length > 0 ? (wins / closed.length) * 100 : null,
    tradeCount: closed.length,
    fees: closed.reduce((sum, trade) => sum + trade.fees, 0),
    endingEquity: ending,
  }
}

function openPosition(cash: number, side: Side, price: number, date: string, costs: CostModel): { cash: number; position: Position | null } {
  const fill = entryFill(side, price, costs.slippage)
  const feeRate = rate(side, "entry", costs)
  if (!(fill > 0) || !(cash > 0)) return { cash, position: null }
  const shares = cash / (fill * (1 + feeRate))
  if (!(shares > 0)) return { cash, position: null }
  const entryFee = shares * fill * feeRate
  const nextCash = side === "LONG" ? cash - shares * fill - entryFee : cash + shares * fill - entryFee
  return {
    cash: nextCash,
    position: { side, shares, entryFill: fill, entryFee, entryDate: date },
  }
}

function closePosition(cash: number, position: Position, price: number, costs: CostModel): { cash: number; closed: Closed } {
  const fill = exitFill(position.side, price, costs.slippage)
  const feeRate = rate(position.side, "exit", costs)
  const exitFee = position.shares * fill * feeRate
  const nextCash = position.side === "LONG" ? cash + position.shares * fill - exitFee : cash - position.shares * fill - exitFee
  const pnl =
    position.side === "LONG"
      ? position.shares * fill - exitFee - (position.shares * position.entryFill + position.entryFee)
      : position.shares * position.entryFill - position.entryFee - (position.shares * fill + exitFee)
  return {
    cash: nextCash,
    closed: { pnl, fees: position.entryFee + exitFee },
  }
}

function mark(cash: number, position: Position | null, close: number): number {
  if (!position) return cash
  if (position.side === "LONG") return cash + position.shares * close
  return cash - position.shares * close
}

export function runBacktest(bars: Bar[], actions: Action[][], symbol: string, start: string, end: string, costs: CostModel = costModel(symbol)): Reality {
  const window = bars.filter((bar) => inWindow(bar.date, start, end))
  const strategy = simulate(bars, actions, start, end, costs)
  const buyHold = simulateBuyHold(window, costs)
  const first = window[0]?.date ?? start
  const last = window[window.length - 1]?.date ?? end
  return {
    capital: costs.capital,
    currency: costs.currency,
    feeNote: costs.note,
    strategy: summarize(strategy.equity, strategy.closed, first, last, costs.capital),
    buyHold: summarize(buyHold.equity, buyHold.closed, first, last, costs.capital),
  }
}

function simulate(bars: Bar[], actions: Action[][], start: string, end: string, costs: CostModel): { equity: number[]; closed: Closed[] } {
  let cash = costs.capital
  let position: Position | null = null
  const closed: Closed[] = []
  const equity: number[] = [costs.capital]
  const lastDate = bars.filter((bar) => inWindow(bar.date, start, end)).at(-1)?.date
  for (let index = 0; index < bars.length; index++) {
    const bar = bars[index]!
    const inside = inWindow(bar.date, start, end)
    for (const action of actions[index] ?? []) {
      if (action.type === "exit" && position) {
        const result = closePosition(cash, position, action.price, costs)
        cash = result.cash
        closed.push(result.closed)
        position = null
      } else if (action.type === "open" && inside) {
        const result = openPosition(cash, action.side, action.entry, bar.date, costs)
        cash = result.cash
        position = result.position
      }
    }
    if (inside && bar.date === lastDate && position) {
      const result = closePosition(cash, position, bar.close, costs)
      cash = result.cash
      closed.push(result.closed)
      position = null
    }
    if (inside) equity.push(mark(cash, position, bar.close))
  }
  return { equity, closed }
}

function simulateBuyHold(window: Bar[], costs: CostModel): { equity: number[]; closed: Closed[] } {
  const equity: number[] = [costs.capital]
  if (window.length < 2) return { equity, closed: [] }
  const first = window[0]!
  const last = window[window.length - 1]!
  let cash = costs.capital
  const opened = openPosition(cash, "LONG", first.close, first.date, costs)
  cash = opened.cash
  const position = opened.position
  const closed: Closed[] = []
  if (!position) return { equity, closed }
  for (const bar of window) {
    if (bar.date === last.date) {
      const result = closePosition(cash, position, bar.close, costs)
      cash = result.cash
      closed.push(result.closed)
      equity.push(cash)
    } else {
      equity.push(mark(cash, position, bar.close))
    }
  }
  return { equity, closed }
}
