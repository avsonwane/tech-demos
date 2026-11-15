"""Build a review report from a run's equity, trades, and fills.

Every figure is computed from those files or copied from the run's own
metrics when the equity file is too coarse to recompute it. Missing
figures stay ``None`` and render as an em dash. Nothing here is estimated.
"""

from __future__ import annotations

import csv
import io
import math
import statistics
from datetime import date
from typing import Any

_MISSING = "—"


def _day(value: Any) -> date | None:
    text = str(value or "")[:10]
    if len(text) < 10:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _sorted_equity(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    usable = []
    for point in points:
        day = _day(point.get("time"))
        equity = point.get("equity")
        if day is None or not isinstance(equity, (int, float)) or not math.isfinite(equity):
            continue
        usable.append(point)
    return sorted(usable, key=lambda point: str(point.get("time")))


def _endpoint_return(points: list[dict[str, Any]]) -> float | None:
    if len(points) < 2:
        return None
    start = float(points[0]["equity"])
    end = float(points[-1]["equity"])
    if start == 0:
        return None
    return end / start - 1


def _cagr(points: list[dict[str, Any]]) -> float | None:
    if len(points) < 2:
        return None
    start_day = _day(points[0].get("time"))
    end_day = _day(points[-1].get("time"))
    start = float(points[0]["equity"])
    end = float(points[-1]["equity"])
    if start_day is None or end_day is None or end_day <= start_day:
        return None
    if start <= 0 or end <= 0:
        return None
    years = (end_day - start_day).days / 365.25
    if years <= 0:
        return None
    return (end / start) ** (1 / years) - 1


def _min_drawdown(points: list[dict[str, Any]]) -> float | None:
    values = [
        float(point["drawdown"])
        for point in points
        if isinstance(point.get("drawdown"), (int, float)) and math.isfinite(point["drawdown"])
    ]
    if not values:
        return None
    return min(values)


def _gaps(points: list[dict[str, Any]]) -> list[int]:
    gaps: list[int] = []
    previous: date | None = None
    for point in points:
        day = _day(point.get("time"))
        if day is None:
            continue
        if previous is not None:
            gaps.append((day - previous).days)
        previous = day
    return gaps


def _regular_daily(points: list[dict[str, Any]]) -> bool:
    """True when the curve is dense enough to treat steps as daily returns."""
    gaps = _gaps(points)
    if len(points) < 20 or len(gaps) < 19:
        return False
    if any(gap <= 0 for gap in gaps):
        return False
    ordered = sorted(gaps)
    median = ordered[len(ordered) // 2]
    return median <= 5


def _simple_returns(points: list[dict[str, Any]]) -> list[float]:
    returns: list[float] = []
    for previous, point in zip(points, points[1:]):
        start = float(previous["equity"])
        end = float(point["equity"])
        if start == 0:
            continue
        returns.append(end / start - 1)
    return returns


def _sample_std(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    spread = statistics.stdev(values)
    if not math.isfinite(spread):
        return None
    return spread


def _sortino(returns: list[float], periods_per_year: float | None) -> float | None:
    if len(returns) < 2:
        return None
    downside = [min(0.0, value) ** 2 for value in returns]
    divisor = len(returns) - 1
    variance = sum(downside) / divisor
    if variance <= 0:
        return None
    deviation = math.sqrt(variance)
    mean = sum(returns) / len(returns)
    ratio = mean / deviation
    if periods_per_year and periods_per_year > 0:
        ratio *= math.sqrt(periods_per_year)
    return ratio if math.isfinite(ratio) else None


def _volatility(returns: list[float], periods_per_year: float | None) -> float | None:
    spread = _sample_std(returns)
    if spread is None:
        return None
    if periods_per_year and periods_per_year > 0:
        spread *= math.sqrt(periods_per_year)
    return spread if math.isfinite(spread) else None


def _month_end(points: list[dict[str, Any]]) -> dict[tuple[int, int], float]:
    ends: dict[tuple[int, int], float] = {}
    for point in points:
        day = _day(point.get("time"))
        if day is None:
            continue
        ends[(day.year, day.month)] = float(point["equity"])
    return ends


def monthly_returns(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per year. A month is filled only when it and the previous month both have a bar."""
    ends = _month_end(_sorted_equity(points))
    if not ends:
        return []
    rows = []
    for year in sorted({key[0] for key in ends}):
        months: list[float | None] = []
        for month in range(1, 13):
            if (year, month) not in ends:
                months.append(None)
                continue
            previous_year, previous_month = (year, month - 1) if month > 1 else (year - 1, 12)
            if (previous_year, previous_month) not in ends:
                months.append(None)
                continue
            base = ends[(previous_year, previous_month)]
            if base == 0:
                months.append(None)
                continue
            months.append(ends[(year, month)] / base - 1)
        rows.append({"year": year, "months": months})
    return rows


def drawdown_periods(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Top three drawdowns from the equity file's drawdown column."""
    periods: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for point in _sorted_equity(points):
        depth = point.get("drawdown")
        day = _day(point.get("time"))
        if day is None or not isinstance(depth, (int, float)):
            continue
        stamp = day.isoformat()
        if depth < 0:
            if current is None:
                current = {"start": stamp, "trough": stamp, "recovery": None, "depth": float(depth)}
            elif float(depth) < float(current["depth"]):
                current["trough"] = stamp
                current["depth"] = float(depth)
        elif current is not None:
            current["recovery"] = stamp
            periods.append(current)
            current = None
    if current is not None:
        periods.append(current)
    periods.sort(key=lambda item: float(item["depth"]))
    return periods[:3]


def _is_entry(trade: dict[str, Any]) -> bool:
    event = str(trade.get("event") or "").lower()
    side = str(trade.get("side") or "").lower()
    if event == "exit":
        return False
    if event == "entry":
        return True
    return side in {"buy", "long"}


def _is_exit(trade: dict[str, Any]) -> bool:
    event = str(trade.get("event") or "").lower()
    side = str(trade.get("side") or "").lower()
    if event == "entry":
        return False
    if event == "exit":
        return True
    return side in {"sell", "short"}


def _fee_on(fills: list[dict[str, Any]], stamp: str | None, action: str) -> float | None:
    if not stamp:
        return None
    day = stamp[:10]
    total = 0.0
    seen = False
    for fill in fills:
        fill_day = str(fill.get("timestamp") or fill.get("time") or "")[:10]
        if fill_day != day:
            continue
        fill_action = str(fill.get("action") or "").lower()
        if fill_action and fill_action != action:
            continue
        fee = fill.get("fee", fill.get("commission"))
        if not isinstance(fee, (int, float)) or not math.isfinite(fee):
            continue
        total += float(fee)
        seen = True
    return total if seen else None


def pair_trades(
    trades: list[dict[str, Any]],
    fills: list[dict[str, Any]],
    last_bar: date | None,
) -> list[dict[str, Any]]:
    """Match entry and exit rows. An unmatched entry stays an open trade."""
    trips: list[dict[str, Any]] = []
    open_trip: dict[str, Any] | None = None
    ordered = sorted(trades, key=lambda trade: str(trade.get("time") or ""))
    for trade in ordered:
        stamp = str(trade.get("time") or "")[:10]
        if _is_entry(trade) and open_trip is None:
            entry_fee = _fee_on(fills, stamp, "open")
            open_trip = {
                "entry_time": stamp or None,
                "exit_time": None,
                "entry_price": trade.get("price") if isinstance(trade.get("price"), (int, float)) else None,
                "exit_price": None,
                "qty": trade.get("qty") if isinstance(trade.get("qty"), (int, float)) else None,
                "holding_days": None,
                "pnl": None,
                "return_pct": None,
                "fees": entry_fee,
                "open": True,
            }
            continue
        if _is_exit(trade) and open_trip is not None:
            exit_fee = _fee_on(fills, stamp, "close")
            entry_fee = open_trip["fees"] or 0.0
            fees = None
            if open_trip["fees"] is not None or exit_fee is not None:
                fees = float(entry_fee) + float(exit_fee or 0.0)
            entry_day = _day(open_trip["entry_time"])
            exit_day = _day(stamp)
            holding = (exit_day - entry_day).days if entry_day and exit_day else None
            pnl = trade.get("pnl") if isinstance(trade.get("pnl"), (int, float)) else None
            entry_price = open_trip["entry_price"]
            exit_price = trade.get("price") if isinstance(trade.get("price"), (int, float)) else None
            qty = open_trip["qty"]
            return_pct = None
            if isinstance(pnl, (int, float)) and isinstance(entry_price, (int, float)) and isinstance(qty, (int, float)):
                notional = entry_price * qty
                if notional:
                    return_pct = float(pnl) / notional
            elif isinstance(entry_price, (int, float)) and isinstance(exit_price, (int, float)) and entry_price:
                return_pct = (float(exit_price) - float(entry_price)) / float(entry_price)
            open_trip.update(
                {
                    "exit_time": stamp or None,
                    "exit_price": exit_price,
                    "holding_days": holding,
                    "pnl": float(pnl) if isinstance(pnl, (int, float)) else None,
                    "return_pct": return_pct,
                    "fees": fees,
                    "open": False,
                }
            )
            trips.append(open_trip)
            open_trip = None
    if open_trip is not None:
        entry_day = _day(open_trip["entry_time"])
        if entry_day and last_bar and last_bar >= entry_day:
            open_trip["holding_days"] = (last_bar - entry_day).days
        trips.append(open_trip)
    return trips


def _merge_days(intervals: list[tuple[date, date]]) -> int:
    if not intervals:
        return 0
    ordered = sorted(intervals)
    total = 0
    start, end = ordered[0]
    for next_start, next_end in ordered[1:]:
        if next_start <= end:
            if next_end > end:
                end = next_end
            continue
        total += (end - start).days
        start, end = next_start, next_end
    total += (end - start).days
    return total


def _exposure(trips: list[dict[str, Any]], first: date | None, last: date | None) -> float | None:
    if first is None or last is None or last <= first:
        return None
    window = (last - first).days
    if window <= 0:
        return None
    intervals: list[tuple[date, date]] = []
    for trip in trips:
        entry = _day(trip.get("entry_time"))
        exit_day = _day(trip.get("exit_time")) if not trip.get("open") else last
        if entry is None or exit_day is None or exit_day <= entry:
            continue
        start = max(entry, first)
        end = min(exit_day, last)
        if end > start:
            intervals.append((start, end))
    return _merge_days(intervals) / window


def _closed(trips: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [trip for trip in trips if not trip.get("open") and isinstance(trip.get("pnl"), (int, float))]


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _longest_flat(trips: list[dict[str, Any]]) -> tuple[str, str] | None:
    best: tuple[str, str] | None = None
    best_days = 0
    for previous, nxt in zip(trips, trips[1:]):
        exit_day = _day(previous.get("exit_time"))
        entry = _day(nxt.get("entry_time"))
        if exit_day is None or entry is None or entry <= exit_day:
            continue
        span = (entry - exit_day).days
        if span > best_days:
            best_days = span
            best = (exit_day.isoformat(), entry.isoformat())
    return best


def _side(result: dict[str, Any], fills: list[dict[str, Any]]) -> dict[str, Any]:
    points = _sorted_equity(result.get("equity") or [])
    metrics = result.get("metrics") if isinstance(result.get("metrics"), dict) else {}
    first = _day(points[0].get("time")) if points else None
    last = _day(points[-1].get("time")) if points else None
    trips = pair_trades(result.get("trades") or [], fills, last)
    closed = _closed(trips)
    pnls = [float(trip["pnl"]) for trip in closed]
    wins = [value for value in pnls if value > 0]
    losses = [value for value in pnls if value < 0]
    returns = _simple_returns(points)
    daily = _regular_daily(points)
    periods = 252.0 if daily else None
    total_return = _endpoint_return(points)
    if total_return is None and isinstance(metrics.get("total_return"), (int, float)):
        total_return = float(metrics["total_return"])
    sharpe = None
    sharpe_from_metrics = False
    if isinstance(metrics.get("sharpe"), (int, float)) and math.isfinite(metrics["sharpe"]):
        sharpe = float(metrics["sharpe"])
        sharpe_from_metrics = True
    drawdown = _min_drawdown(points)
    if drawdown is None and isinstance(metrics.get("max_drawdown"), (int, float)):
        drawdown = float(metrics["max_drawdown"])
    win_rate = (len(wins) / len(closed)) if closed else None
    profit_factor = None
    if wins and losses:
        profit_factor = sum(wins) / abs(sum(losses))
    realized = sum(pnls) if pnls else None
    fees = metrics.get("fees") if metrics.get("fees_reported") else None
    if not isinstance(fees, (int, float)):
        fees = None
        total_fees = 0.0
        seen_fee = False
        for fill in fills:
            fee = fill.get("fee", fill.get("commission"))
            if isinstance(fee, (int, float)) and math.isfinite(fee):
                total_fees += float(fee)
                seen_fee = True
        if seen_fee:
            fees = total_fees
    fees_pct = None
    if isinstance(fees, (int, float)) and isinstance(realized, (int, float)) and realized > 0:
        fees_pct = float(fees) / realized
    return {
        "total_return": total_return,
        "cagr": _cagr(points),
        "sharpe": sharpe,
        "sharpe_from_metrics": sharpe_from_metrics,
        "sortino": _sortino(returns, periods) if daily else None,
        "max_drawdown": drawdown,
        "volatility": _volatility(returns, periods) if daily else None,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "avg_win": _mean(wins),
        "avg_loss": _mean(losses),
        "best": max(pnls) if pnls else None,
        "worst": min(pnls) if pnls else None,
        "exposure": _exposure(trips, first, last),
        "trades": len(closed),
        "open_trades": sum(1 for trip in trips if trip.get("open")),
        "fees": float(fees) if isinstance(fees, (int, float)) else None,
        "fees_pct": fees_pct,
        "trips": trips,
        "drawdowns": drawdown_periods(points),
        "monthly": monthly_returns(points),
        "starting_capital": float(points[0]["equity"]) if points else None,
        "first_bar": first.isoformat() if first else None,
        "last_bar": last.isoformat() if last else None,
        "bars": len(points),
        "realized_pnl": realized,
    }


_ROWS: tuple[tuple[str, str, str, str, bool], ...] = (
    ("return", "Return", "percent", "sign", True),
    ("cagr", "CAGR", "percent", "sign", True),
    ("sharpe", "Sharpe", "number", "sharpe", True),
    ("sortino", "Sortino", "number", "sharpe", True),
    ("max_drawdown", "Max drawdown", "percent", "drawdown", True),
    ("volatility", "Volatility", "percent", "plain", False),
    ("win_rate", "Win rate", "percent", "winrate", False),
    ("profit_factor", "Profit factor", "number", "ratio", True),
    ("avg_win", "Average win", "money", "sign", True),
    ("avg_loss", "Average loss", "money", "sign", True),
    ("best", "Best trade", "money", "sign", True),
    ("worst", "Worst trade", "money", "sign", True),
    ("exposure", "Time in market", "percent", "plain", False),
    ("trades", "Closed trades", "count", "plain", False),
    ("fees_pct", "Fees / PnL", "percent", "cost", True),
)


def _pct(value: float | None) -> str:
    if value is None:
        return _MISSING
    number = value * 100
    if number > 0:
        return f"+{number:.2f}%"
    return f"{number:.2f}%"


def _num(value: float | None, signed: bool) -> str:
    if value is None:
        return _MISSING
    if signed and value > 0:
        return f"+{value:.2f}"
    return f"{value:.2f}"


def _money(value: float | None, signed: bool) -> str:
    if value is None:
        return _MISSING
    sign = "+" if signed and value > 0 else ""
    return f"{sign}{value:,.2f}"


def _count(value: float | None) -> str:
    if value is None:
        return _MISSING
    return str(int(value))


def _format(value: float | None, unit: str, signed: bool) -> str:
    if unit == "percent":
        return _pct(value)
    if unit == "money":
        return _money(value, signed)
    if unit == "count":
        return _count(value)
    return _num(value, signed)


def _summary(result: dict[str, Any], strategy: dict[str, Any], benchmark: dict[str, Any] | None) -> str:
    name = result.get("strategy_label") or "The strategy"
    parts: list[str] = []
    strategy_return = strategy["total_return"]
    benchmark_return = benchmark["total_return"] if benchmark else None
    if strategy_return is not None and benchmark_return is not None:
        gap = (strategy_return - benchmark_return) * 100
        if gap > 0:
            lead = f"{name} beat buy-and-hold by {gap:.2f} percentage points"
        elif gap < 0:
            lead = f"{name} trailed buy-and-hold by {abs(gap):.2f} percentage points"
        else:
            lead = f"{name} matched buy-and-hold"
        parts.append(f"{lead} ({_pct(strategy_return)} versus {_pct(benchmark_return)}).")
    elif strategy_return is not None:
        parts.append(f"{name} returned {_pct(strategy_return)}. Buy-and-hold was not recorded.")
    else:
        parts.append(f"{name} has no start and end equity, so the return is not computed.")
    closed = _closed(strategy["trips"])
    if len(closed) == 1:
        trip = closed[0]
        verb = "gained" if float(trip["pnl"]) > 0 else "lost" if float(trip["pnl"]) < 0 else "was flat at"
        amount = abs(float(trip["pnl"]))
        parts.append(
            f"One closed trade, from {trip['entry_time']} to {trip['exit_time']}, {verb} {amount:,.2f}."
        )
    elif closed:
        wins = sum(1 for trip in closed if float(trip["pnl"]) > 0)
        parts.append(f"{wins} of {len(closed)} closed trades made money.")
    flat = _longest_flat(strategy["trips"])
    if flat:
        parts.append(f"The book was flat from {flat[0]} until the next entry on {flat[1]}.")
    if strategy["open_trades"]:
        noun = "trade is" if strategy["open_trades"] == 1 else "trades are"
        parts.append(f"{strategy['open_trades']} {noun} still open at the last bar, so the realized return excludes them.")
    return " ".join(parts)


def _notes(result: dict[str, Any], strategy: dict[str, Any]) -> dict[str, Any]:
    sharpe_note = None
    if strategy["sharpe_from_metrics"]:
        sharpe_note = "Sharpe is the run's recorded metric. The equity file is not a regular daily series, so it was not recomputed."
    return {
        "sources": list(result.get("sources") or []),
        "start_date": result.get("start_date"),
        "end_date": result.get("end_date"),
        "first_bar": strategy["first_bar"],
        "last_bar": strategy["last_bar"],
        "bars": strategy["bars"],
        "warmup": None,
        "starting_capital": strategy["starting_capital"],
        "fee_model": None,
        "fees": strategy["fees"],
        "sharpe_note": sharpe_note,
    }


_FIELDS = {
    "return": "total_return",
    "cagr": "cagr",
    "sharpe": "sharpe",
    "sortino": "sortino",
    "max_drawdown": "max_drawdown",
    "volatility": "volatility",
    "win_rate": "win_rate",
    "profit_factor": "profit_factor",
    "avg_win": "avg_win",
    "avg_loss": "avg_loss",
    "best": "best",
    "worst": "worst",
    "exposure": "exposure",
    "trades": "trades",
    "fees_pct": "fees_pct",
}


def _comparison(strategy: dict[str, Any], benchmark: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows = []
    for key, label, unit, tone, signed in _ROWS:
        field = _FIELDS[key]
        rows.append(
            {
                "id": key,
                "label": label,
                "unit": unit,
                "tone": tone,
                "signed": signed,
                "strategy": strategy.get(field),
                "benchmark": None if benchmark is None else benchmark.get(field),
            }
        )
    return rows


def _markdown(result: dict[str, Any], report: dict[str, Any]) -> str:
    strategy_name = result.get("strategy_label") or "Strategy"
    benchmark_name = result.get("benchmark_label") or "Buy and hold"
    lines = [f"# {strategy_name}", "", report["summary"], "", "## Strategy vs benchmark", "", f"| Metric | {strategy_name} | {benchmark_name} |", "| --- | --- | --- |"]
    for row in report["comparison"]:
        lines.append(
            f"| {row['label']} | {_format(row['strategy'], row['unit'], row['signed'])} | {_format(row['benchmark'], row['unit'], row['signed'])} |"
        )
    lines.extend(["", "## Monthly returns", ""])
    if not report["monthly"]:
        lines.append("No equity bars.")
    else:
        header = "| Year | " + " | ".join(
            ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        ) + " |"
        lines.append(header)
        lines.append("| --- | " + " | ".join(["---"] * 12) + " |")
        for year in report["monthly"]:
            cells = [_pct(value) for value in year["months"]]
            lines.append(f"| {year['year']} | " + " | ".join(cells) + " |")
        lines.append("")
        lines.append("A month is filled only when that month and the previous month both have an equity bar.")
    lines.extend(["", "## Trades", "", "| Entry | Exit | Entry price | Exit price | Qty | Days | PnL | Return | Fees | Status |", "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"])
    if not report["round_trips"]:
        lines.append("| — | — | — | — | — | — | — | — | — | — |")
    for trip in report["round_trips"]:
        lines.append(
            "| {entry} | {exit} | {entry_price} | {exit_price} | {qty} | {days} | {pnl} | {ret} | {fees} | {status} |".format(
                entry=trip["entry_time"] or _MISSING,
                exit=trip["exit_time"] or _MISSING,
                entry_price=_num(trip["entry_price"], False),
                exit_price=_num(trip["exit_price"], False),
                qty=_num(trip["qty"], False),
                days=_count(trip["holding_days"]),
                pnl=_money(trip["pnl"], True),
                ret=_pct(trip["return_pct"]),
                fees=_money(trip["fees"], False),
                status="Open" if trip["open"] else "Closed",
            )
        )
    lines.extend(["", "## Drawdown periods", "", "| Start | Trough | Recovery | Depth |", "| --- | --- | --- | --- |"])
    if not report["drawdowns"]:
        lines.append("| — | — | — | — |")
    for period in report["drawdowns"]:
        lines.append(
            f"| {period['start']} | {period['trough']} | {period['recovery'] or _MISSING} | {_pct(period['depth'])} |"
        )
    notes = report["notes"]
    lines.extend(
        [
            "",
            "## Data notes",
            "",
            f"- Source: {', '.join(notes['sources']) if notes['sources'] else _MISSING}",
            f"- Requested range: {notes['start_date'] or _MISSING} to {notes['end_date'] or _MISSING}",
            f"- Equity bars: {notes['first_bar'] or _MISSING} to {notes['last_bar'] or _MISSING} ({notes['bars']})",
            f"- Warmup: {_MISSING if notes['warmup'] is None else notes['warmup']}",
            f"- Starting capital: {_money(notes['starting_capital'], False)}",
            f"- Fee model: {_MISSING if notes['fee_model'] is None else notes['fee_model']}",
            f"- Fees: {_money(notes['fees'], False)}",
            "- Fees / PnL divides fill fees by closed-trade PnL. Those columns are not rescaled.",
            "- A month is colored only when that month and the previous month both have an equity bar.",
            "- Drawdown periods follow the drawdown column. They are not recomputed from the equity level.",
        ]
    )
    if notes["sharpe_note"]:
        lines.append(f"- {notes['sharpe_note']}")
    lines.append("")
    return "\n".join(lines)


def _csv_cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _csv(trips: list[dict[str, Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(
        ["entry_time", "exit_time", "entry_price", "exit_price", "qty", "holding_days", "pnl", "return", "fees", "status"]
    )
    for trip in trips:
        writer.writerow(
            [
                trip["entry_time"] or "",
                trip["exit_time"] or "",
                _csv_cell(trip["entry_price"]),
                _csv_cell(trip["exit_price"]),
                _csv_cell(trip["qty"]),
                _csv_cell(trip["holding_days"]),
                _csv_cell(trip["pnl"]),
                _csv_cell(trip["return_pct"]),
                _csv_cell(trip["fees"]),
                "open" if trip["open"] else "closed",
            ]
        )
    return buffer.getvalue()


def build_report(
    result: dict[str, Any],
    fills: list[dict[str, Any]] | None = None,
    benchmark: dict[str, Any] | None = None,
    benchmark_fills: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return the review payload, including the Markdown download and the trades CSV."""
    strategy = _side(result, [row for row in (fills or []) if isinstance(row, dict)])
    other = None
    if benchmark is not None:
        other = _side(benchmark, [row for row in (benchmark_fills or []) if isinstance(row, dict)])
    report = {
        "summary": _summary(result, strategy, other),
        "comparison": _comparison(strategy, other),
        "monthly": strategy["monthly"],
        "round_trips": strategy["trips"],
        "drawdowns": strategy["drawdowns"],
        "notes": _notes(result, strategy),
    }
    report["markdown"] = _markdown(result, report)
    report["trades_csv"] = _csv(strategy["trips"])
    return report
