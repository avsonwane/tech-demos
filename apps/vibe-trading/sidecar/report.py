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
    text = str(value or "").strip()
    if len(text) >= 8 and text[:8].isdigit():
        try:
            return date(int(text[:4]), int(text[4:6]), int(text[6:8]))
        except ValueError:
            return None
    text = text.replace("/", "-")[:10]
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


def _positive(value: Any) -> float | None:
    if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        return None
    return float(value)


def _capital_base(points: list[dict[str, Any]], result: dict[str, Any]) -> float | None:
    """Starting capital from the run, or the first equity bar when the run omitted it."""
    capital = _positive(result.get("initial_cash"))
    if capital is not None:
        return capital
    if not points:
        return None
    return _positive(points[0].get("equity"))


def _total_return(points: list[dict[str, Any]], base: float | None) -> float | None:
    if len(points) < 2 or base is None or base == 0:
        return None
    end = float(points[-1]["equity"])
    if not math.isfinite(end):
        return None
    return end / base - 1


def _cagr(
    points: list[dict[str, Any]],
    base: float | None,
    daily: bool,
    bars_per_year: float | None,
) -> float | None:
    if len(points) < 2 or base is None or base <= 0:
        return None
    end = float(points[-1]["equity"])
    if end <= 0 or not math.isfinite(end):
        return None
    growth = end / base
    if daily and bars_per_year and bars_per_year > 0:
        try:
            annual = growth ** (float(bars_per_year) / len(points)) - 1
        except OverflowError:
            return None
        return annual if math.isfinite(annual) else None
    start_day = _day(points[0].get("time"))
    end_day = _day(points[-1].get("time"))
    if start_day is None or end_day is None or end_day <= start_day:
        return None
    years = (end_day - start_day).days / 365.25
    if years <= 0:
        return None
    annual = growth ** (1 / years) - 1
    return annual if math.isfinite(annual) else None


def _path_drawdown(points: list[dict[str, Any]], base: float | None) -> float | None:
    """Max drawdown with the starting capital as the first peak."""
    if not points or base is None or base <= 0:
        return None
    peak = base
    worst = 0.0
    for point in points:
        equity = float(point["equity"])
        if not math.isfinite(equity):
            continue
        peak = max(peak, equity)
        if peak == 0:
            continue
        worst = min(worst, equity / peak - 1)
    return worst


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


def _next_month(year: int, month: int) -> date:
    if month == 12:
        return date(year + 1, 1, 1)
    return date(year, month + 1, 1)


def monthly_returns(
    points: list[dict[str, Any]],
    capital: float | None = None,
    start: date | None = None,
    daily: bool = False,
) -> list[dict[str, Any]]:
    """One row per year.

    A month with a bar and a previous month is the change between those
    month-end equities. On a daily series, the first month is measured from
    starting capital, and a month that ends before the first equity bar is
    warmup at 0.00%.
    """
    ordered = _sorted_equity(points)
    ends = _month_end(ordered)
    if not ends:
        return []
    first = _day(ordered[0].get("time"))
    rows = []
    for year in sorted({key[0] for key in ends}):
        months: list[float | None] = []
        marks: list[str | None] = []
        for month in range(1, 13):
            month_ends = _next_month(year, month)
            before_first = daily and first is not None and month_ends <= first
            if before_first:
                if start is not None and month_ends <= start:
                    months.append(None)
                    marks.append(None)
                    continue
                months.append(0.0)
                marks.append("warmup")
                continue
            if (year, month) not in ends:
                months.append(None)
                marks.append(None)
                continue
            previous_year, previous_month = (year, month - 1) if month > 1 else (year - 1, 12)
            if (previous_year, previous_month) not in ends:
                if daily and capital is not None and capital > 0:
                    months.append(ends[(year, month)] / capital - 1)
                    marks.append("capital")
                else:
                    months.append(None)
                    marks.append(None)
                continue
            base = ends[(previous_year, previous_month)]
            if base == 0:
                months.append(None)
                marks.append(None)
                continue
            months.append(ends[(year, month)] / base - 1)
            marks.append(None)
        rows.append({"year": year, "months": months, "marks": marks})
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


def _longest_flat(
    trips: list[dict[str, Any]],
    first: date | None,
    last: date | None,
) -> dict[str, str] | None:
    """The longest stretch with no position, including after the last exit."""
    spans: list[tuple[date, date, str]] = []
    if trips and first is not None:
        entry = _day(trips[0].get("entry_time"))
        if entry is not None and entry > first:
            spans.append((first, entry, "entry"))
    elif not trips and first is not None and last is not None and last > first:
        spans.append((first, last, "bar"))
    for previous, nxt in zip(trips, trips[1:]):
        if previous.get("open"):
            continue
        exit_day = _day(previous.get("exit_time"))
        entry = _day(nxt.get("entry_time"))
        if exit_day is None or entry is None or entry <= exit_day:
            continue
        spans.append((exit_day, entry, "entry"))
    if trips and last is not None and not trips[-1].get("open"):
        exit_day = _day(trips[-1].get("exit_time"))
        if exit_day is not None and last > exit_day:
            spans.append((exit_day, last, "bar"))
    if not spans:
        return None
    start, end, kind = max(spans, key=lambda item: (item[1] - item[0]).days)
    return {"start": start.isoformat(), "end": end.isoformat(), "kind": kind}


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
    periods = _positive(result.get("bars_per_year")) if daily else None
    if daily and periods is None:
        periods = 252.0
    base = _capital_base(points, result)
    total_return = _total_return(points, base)
    if total_return is None and isinstance(metrics.get("total_return"), (int, float)):
        total_return = float(metrics["total_return"])
    sharpe = None
    sharpe_from_metrics = False
    if isinstance(metrics.get("sharpe"), (int, float)) and math.isfinite(metrics["sharpe"]):
        sharpe = float(metrics["sharpe"])
        sharpe_from_metrics = True
    elif daily and periods and returns:
        spread = _sample_std(returns)
        if spread:
            sharpe = (sum(returns) / len(returns)) / spread * math.sqrt(periods)
            if not math.isfinite(sharpe):
                sharpe = None
    drawdown = _path_drawdown(points, base) if daily else None
    if drawdown is None:
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
        "cagr": _cagr(points, base, daily, periods),
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
        "monthly": monthly_returns(points, base, _day(result.get("start_date")), daily),
        "starting_capital": base,
        "first_bar": first.isoformat() if first else None,
        "last_bar": last.isoformat() if last else None,
        "bars": len(points),
        "frequency": "daily" if daily else ("irregular" if points else None),
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
    flat = _longest_flat(strategy["trips"], _day(strategy.get("first_bar")), _day(strategy.get("last_bar")))
    if flat and flat["kind"] == "bar":
        parts.append(f"The book was flat from {flat['start']} through {flat['end']}.")
    elif flat:
        parts.append(f"The book was flat from {flat['start']} until the next entry on {flat['end']}.")
    if strategy["open_trades"]:
        noun = "trade is" if strategy["open_trades"] == 1 else "trades are"
        parts.append(f"{strategy['open_trades']} {noun} still open at the last bar, so the realized return excludes them.")
    return " ".join(parts)


_RATE_FIELDS = (
    ("commission_rate", "commission", False),
    ("commission", "commission", False),
    ("slippage_bps", "slippage", True),
    ("slippage", "slippage", False),
    ("taker_rate", "taker", False),
    ("maker_rate", "maker", False),
    ("fee_bps", "fee", True),
    ("fee_rate", "fee", False),
    ("in_brokerage", "brokerage", False),
    ("in_stt", "STT", False),
    ("in_exchange_txn", "exchange", False),
    ("in_sebi_fee", "SEBI", False),
    ("in_stamp_duty", "stamp duty", False),
    ("in_gst", "GST", False),
    ("in_dp_charge", "DP charge", False),
    ("hk_commission", "HK commission", False),
    ("ca_commission", "CA commission", False),
)


def _rate_phrase(label: str, value: Any, already_bps: bool) -> str | None:
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    if already_bps:
        return f"{label} {value:g} bps"
    magnitude = abs(float(value))
    if magnitude < 0.05:
        return f"{label} {float(value) * 10000:.4g} bps"
    if magnitude < 1:
        return f"{label} {float(value) * 100:.4g}%"
    return f"{label} {float(value):g}"


def _rates_from(mapping: Any) -> list[str]:
    if not isinstance(mapping, dict):
        return []
    phrases: list[str] = []
    for key, label, already_bps in _RATE_FIELDS:
        if key not in mapping:
            continue
        phrase = _rate_phrase(label, mapping.get(key), already_bps)
        if phrase and phrase not in phrases:
            phrases.append(phrase)
    return phrases


def _fee_model(result: dict[str, Any], fills: list[dict[str, Any]]) -> str | None:
    phrases = _rates_from(result.get("config")) or _rates_from(result.get("backtest"))
    if not phrases:
        for fill in fills:
            phrases = _rates_from(fill)
            if phrases:
                break
    if phrases:
        return ", ".join(phrases)
    rates: list[float] = []
    for fill in fills:
        fee = fill.get("fee", fill.get("commission"))
        notional = fill.get("notional")
        if (
            isinstance(fee, (int, float))
            and isinstance(notional, (int, float))
            and math.isfinite(fee)
            and math.isfinite(notional)
            and notional > 0
        ):
            rates.append(float(fee) / float(notional))
    if not rates or max(rates) - min(rates) > 0.0001:
        return None
    return f"effective {rates[0] * 10000:.4g} bps from fills"


def _warmup(result: dict[str, Any], strategy: dict[str, Any]) -> str | None:
    start = _day(result.get("start_date"))
    first = _day(strategy.get("first_bar"))
    if start is None or first is None or first <= start:
        return None
    return f"{start.isoformat()} to {first.isoformat()}"


def _notes(result: dict[str, Any], strategy: dict[str, Any], fills: list[dict[str, Any]]) -> dict[str, Any]:
    frequency = strategy.get("frequency")
    sharpe_note = None
    if strategy["sharpe_from_metrics"] and frequency != "daily":
        sharpe_note = (
            "Sharpe is the run's recorded metric. The equity file is not a regular daily series, so it was not recomputed."
        )
    elif strategy["sharpe_from_metrics"]:
        sharpe_note = "Sharpe is the run's recorded metric."
    return {
        "sources": list(result.get("sources") or []),
        "start_date": result.get("start_date"),
        "end_date": result.get("end_date"),
        "first_bar": strategy["first_bar"],
        "last_bar": strategy["last_bar"],
        "bars": strategy["bars"],
        "frequency": frequency,
        "warmup": _warmup(result, strategy),
        "starting_capital": strategy["starting_capital"],
        "fee_model": _fee_model(result, fills),
        "fees": strategy["fees"],
        "sharpe_note": sharpe_note,
        "benchmark_source": result.get("benchmark_source"),
        "benchmark_detail": result.get("benchmark_detail"),
        "recorded_benchmark": result.get("recorded_benchmark"),
        "strategy_warning": result.get("strategy_warning"),
        "hold_window": result.get("hold_window"),
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
    lines = [f"# {strategy_name}", ""]
    warning = result.get("strategy_warning")
    if isinstance(warning, str) and warning.strip():
        lines.extend([warning.strip(), ""])
    lines.extend([report["summary"], "", "## Strategy vs benchmark", "", f"| Metric | {strategy_name} | {benchmark_name} |", "| --- | --- | --- |"])
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
        lines.append(
            "On a daily series, a month before the first equity bar is warmup and shows 0.00%. "
            "The first month with bars is measured from starting capital when the previous month has none."
        )
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
            f"- Frequency: {notes['frequency'] or _MISSING}",
            f"- Warmup: {_MISSING if notes['warmup'] is None else notes['warmup']}",
            f"- Starting capital: {_money(notes['starting_capital'], False)}",
            f"- Fee model: {_MISSING if notes['fee_model'] is None else notes['fee_model']}",
            f"- Buy-and-hold window: {notes.get('hold_window') or _MISSING}",
            f"- Benchmark: {notes.get('benchmark_detail') or notes['benchmark_source'] or _MISSING}",
            f"- Recorded benchmark: {notes.get('recorded_benchmark') or _MISSING}",
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


_BH_LABEL = "Buy & hold, fees included: one entry + one exit"

# India delivery defaults from vibe-trading-ai 0.1.19 IndiaEquityEngine.
# A run's config overrides a key when that key is present. Two RELIANCE runs
# then share one schedule even when one of them left the keys out of config.json.
_INDIA_FEES = {
    "slippage": 0.001,
    "in_brokerage": 0.0,
    "in_stt": 0.001,
    "in_exchange_txn": 0.0000297,
    "in_sebi_fee": 0.000001,
    "in_stamp_duty": 0.00015,
    "in_gst": 0.18,
    "in_dp_charge": 0.0,
}


def _configured(config: Any, key: str, default: float) -> float:
    if isinstance(config, dict) and key in config:
        value = config.get(key)
        if isinstance(value, (int, float)) and math.isfinite(value):
            return float(value)
    return default


def _india_market(result: dict[str, Any]) -> bool:
    backtest = result.get("backtest") if isinstance(result.get("backtest"), dict) else {}
    engine = str(backtest.get("engine") or "").lower()
    if engine in {"india_equity", "india"}:
        return True
    codes = result.get("codes") or []
    return any(str(code).upper().endswith((".NS", ".BO")) for code in codes)


def _india_schedule(config: Any) -> dict[str, float]:
    return {key: _configured(config, key, default) for key, default in _INDIA_FEES.items()}


def _variable_rate(schedule: dict[str, float], buy: bool) -> tuple[float, float]:
    """Return (rate on notional, flat cash fee) for one India side."""
    brokerage = schedule["in_brokerage"]
    exchange = schedule["in_exchange_txn"]
    sebi = schedule["in_sebi_fee"]
    gst = (brokerage + exchange + sebi) * schedule["in_gst"]
    variable = brokerage + exchange + sebi + gst + schedule["in_stt"]
    if buy:
        return variable + schedule["in_stamp_duty"], 0.0
    return variable, schedule["in_dp_charge"]


def _generic_costs(config: Any) -> tuple[float, float]:
    slippage = _configured(config, "slippage", 0.0)
    if not (isinstance(config, dict) and "slippage" in config) and isinstance(config, dict) and "slippage_bps" in config:
        slippage = _configured(config, "slippage_bps", 0.0) / 10_000
    fee = 0.0
    if isinstance(config, dict):
        for key in ("commission_rate", "commission", "fee_rate", "taker_rate"):
            if key in config:
                fee = _configured(config, key, 0.0)
                break
    return slippage, fee


def _close_series(rows: list[dict[str, Any]]) -> list[tuple[date, float]]:
    series: list[tuple[date, float]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        day = _day(row.get("time") or row.get("timestamp") or row.get("date"))
        value = row.get("close")
        if value is None:
            value = row.get("price")
        if isinstance(value, str):
            try:
                value = float(value)
            except ValueError:
                value = None
        if day is None or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            continue
        series.append((day, float(value)))
    series.sort(key=lambda item: item[0])
    return series


def _schedule_phrase(schedule: dict[str, float]) -> str:
    parts = [
        f"slippage {schedule['slippage'] * 10000:.4g} bps",
        f"STT {schedule['in_stt'] * 10000:.4g} bps",
        f"exchange {schedule['in_exchange_txn'] * 10000:.4g} bps",
        f"SEBI {schedule['in_sebi_fee'] * 10000:.4g} bps",
        f"stamp duty {schedule['in_stamp_duty'] * 10000:.4g} bps",
        f"GST {schedule['in_gst'] * 100:.4g}% on brokerage, exchange, and SEBI",
    ]
    if schedule["in_brokerage"]:
        parts.insert(1, f"brokerage {schedule['in_brokerage'] * 10000:.4g} bps")
    if schedule["in_dp_charge"]:
        parts.append(f"DP charge {schedule['in_dp_charge']:.4g}")
    return ", ".join(parts)


def _named_day(mapping: Any, key: str) -> date | None:
    if not isinstance(mapping, dict):
        return None
    return _day(mapping.get(key))


def _hold_bounds(result: dict[str, Any]) -> tuple[date | None, date | None]:
    """Evaluation window for buy-and-hold, never the warmup fetch start.

    Start is ``evaluation_start_date`` when the run recorded one, otherwise
    the first equity bar, otherwise the requested backtest start. End is the
    last equity bar, otherwise the requested end. ``start_date`` is the date
    the model fetched, which includes warmup and differs across models.
    """
    config = result.get("config") if isinstance(result.get("config"), dict) else {}
    backtest = result.get("backtest") if isinstance(result.get("backtest"), dict) else {}
    evaluation = _named_day(config, "evaluation_start_date") or _named_day(backtest, "evaluation_start_date")
    equity = _sorted_equity(result.get("equity") or [])
    first_equity = _day(equity[0].get("time")) if equity else None
    last_equity = _day(equity[-1].get("time")) if equity else None
    if evaluation is not None:
        start = evaluation
    elif first_equity is not None:
        start = first_equity
    else:
        start = _day(result.get("start_date"))
    end = last_equity or _day(result.get("end_date"))
    return start, end


def compute_buy_hold(result: dict[str, Any]) -> dict[str, Any] | None:
    """One buy-and-hold from the run's closes, initial capital, and fee schedule.

    Entry is the first close on or after the strategy evaluation start.
    Exit is the last close on or before the last equity bar. Slippage and
    fees are charged once on the way in and once on the way out.
    """
    closes = _close_series(result.get("price_bars") or [])
    if len(closes) < 2:
        return None
    start, end = _hold_bounds(result)
    window = [
        item
        for item in closes
        if (start is None or item[0] >= start) and (end is None or item[0] <= end)
    ]
    if len(window) < 2:
        return None
    capital = _positive(result.get("initial_cash"))
    if capital is None:
        equity = _sorted_equity(result.get("equity") or [])
        capital = _capital_base(equity, result)
    if capital is None:
        return None
    config = result.get("config") if isinstance(result.get("config"), dict) else {}
    schedule = None
    if _india_market(result):
        schedule = _india_schedule(config)
        slippage = schedule["slippage"]
        buy_rate, buy_flat = _variable_rate(schedule, True)
        sell_rate, sell_flat = _variable_rate(schedule, False)
        costs = _schedule_phrase(schedule)
    else:
        slippage, fee = _generic_costs(config)
        buy_rate = sell_rate = fee
        buy_flat = sell_flat = 0.0
        costs = f"slippage {slippage * 10000:.4g} bps, fee {fee * 10000:.4g} bps"
    entry_day, entry_close = window[0]
    exit_day, exit_close = window[-1]
    entry_px = entry_close * (1 + slippage)
    exit_px = exit_close * (1 - slippage)
    unit = entry_px * (1 + buy_rate)
    if unit <= 0 or capital <= buy_flat:
        return None
    shares = (capital - buy_flat) / unit
    if shares <= 0:
        return None
    entry_fee = shares * entry_px * buy_rate + buy_flat
    cash = capital - shares * entry_px - entry_fee
    exit_fee = shares * exit_px * sell_rate + sell_flat
    points: list[dict[str, Any]] = []
    for day, close in window:
        if day == exit_day:
            equity = cash + shares * exit_px - exit_fee
        else:
            equity = cash + shares * close
        points.append({"time": day.isoformat(), "equity": equity, "drawdown": None})
    pnl = (shares * exit_px - exit_fee) - (shares * entry_px + entry_fee)
    hold_window = f"{entry_day.isoformat()} through {exit_day.isoformat()}"
    note = (
        f"{_BH_LABEL}. Buy-and-hold window: {hold_window}. "
        "That is the strategy evaluation window, from the first close on or after "
        "evaluation_start_date (or the first equity bar when that date is absent) "
        "through the last equity bar. The warmup fetch start is not used. "
        "Time in market is 100% of that window. "
        f"Costs: {costs}."
    )
    origin = result.get("price_bar_source")
    if isinstance(origin, str) and origin.strip():
        note += f" Closes from {origin.strip()}."
    return {
        "equity": points,
        "trades": [
            {
                "time": entry_day.isoformat(),
                "code": "",
                "side": "buy",
                "price": entry_px,
                "qty": shares,
                "pnl": 0.0,
                "event": "entry",
            },
            {
                "time": exit_day.isoformat(),
                "code": "",
                "side": "sell",
                "price": exit_px,
                "qty": shares,
                "pnl": pnl,
                "event": "exit",
            },
        ],
        "fills": [
            {"timestamp": entry_day.isoformat(), "action": "open", "fee": entry_fee},
            {"timestamp": exit_day.isoformat(), "action": "close", "fee": exit_fee},
        ],
        "metrics": {},
        "initial_cash": capital,
        "bars_per_year": result.get("bars_per_year"),
        "note": note,
        "hold_window": hold_window,
    }


def _benchmark_points(rows: list[dict[str, Any]], value_key: str) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        stamp = row.get("time") or row.get("timestamp")
        value = row.get(value_key)
        if value_key == "close" and value is None:
            value = row.get("price")
        if isinstance(value, str):
            try:
                value = float(value)
            except ValueError:
                value = None
        if stamp is None or not isinstance(value, (int, float)) or not math.isfinite(value):
            continue
        points.append({"time": str(stamp), "equity": float(value), "drawdown": None})
    return _sorted_equity(points)


def _recorded_benchmark(
    benchmark: dict[str, Any] | None,
    column: list[dict[str, Any]],
) -> str | None:
    """A Vibe-Trading benchmark stays a note. The table uses the computed one."""
    if benchmark is not None:
        side = _side(benchmark, [])
        if side["total_return"] is not None:
            return (
                f"Vibe-Trading also recorded a buy-and-hold run at {_pct(side['total_return'])}. "
                "The comparison table uses the computed buy-and-hold."
            )
    if len(column) >= 2:
        end = float(column[-1]["equity"])
        start = float(column[0]["equity"])
        if start:
            recorded = end / start - 1
            return (
                f"The equity file's benchmark column changes by {_pct(recorded)} and is price-only. "
                "The comparison table uses the computed buy-and-hold."
            )
    return None


def _overlay_curve(result: dict[str, Any], points: list[dict[str, Any]]) -> None:
    by_day = {str(point.get("time"))[:10]: float(point["equity"]) for point in points}
    for point in result.get("equity") or []:
        match = by_day.get(str(point.get("time"))[:10])
        if match is not None:
            point["benchmark"] = match


def build_report(
    result: dict[str, Any],
    fills: list[dict[str, Any]] | None = None,
    benchmark: dict[str, Any] | None = None,
    benchmark_fills: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return the review payload, including the Markdown download and the trades CSV."""
    strategy_fills = [row for row in (fills or []) if isinstance(row, dict)]
    strategy = _side(result, strategy_fills)
    other = None
    source = None
    recorded = None
    computed = compute_buy_hold(result)
    column = _benchmark_points(result.get("equity") or [], "benchmark")
    detail = None
    noted_hold = None
    if computed is not None:
        other = _side(computed, computed["fills"])
        source = _BH_LABEL
        detail = computed["note"]
        _overlay_curve(result, computed["equity"])
        recorded = _recorded_benchmark(benchmark, column)
        noted_hold = computed.get("hold_window")
    elif benchmark is not None:
        other = _side(benchmark, [row for row in (benchmark_fills or []) if isinstance(row, dict)])
        source = "Vibe-Trading buy-and-hold run. Price bars were not available, so this column is that run."
    elif len(column) >= 2:
        other = _side(
            {
                "equity": column,
                "trades": [],
                "metrics": {},
                "initial_cash": result.get("initial_cash"),
                "bars_per_year": result.get("bars_per_year"),
            },
            [],
        )
        source = "Equity benchmark column. Price bars were not available, so this column is price-only."
    noted = dict(result)
    noted["benchmark_source"] = source
    noted["benchmark_detail"] = detail
    noted["recorded_benchmark"] = recorded
    noted["hold_window"] = noted_hold if computed is not None else None
    report = {
        "summary": _summary(result, strategy, other),
        "comparison": _comparison(strategy, other),
        "monthly": strategy["monthly"],
        "round_trips": strategy["trips"],
        "drawdowns": strategy["drawdowns"],
        "notes": _notes(noted, strategy, strategy_fills),
    }
    report["markdown"] = _markdown(result, report)
    report["trades_csv"] = _csv(strategy["trips"])
    return report
