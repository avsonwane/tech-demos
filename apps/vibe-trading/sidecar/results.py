"""Turn a Vibe-Trading ``GET /runs/{id}`` payload into the desk result.

Equity prefers ``artifacts_equity_csv`` because the preview curve in 0.1.19
drops ``benchmark_equity``. Summary metrics include return, CAGR
(``annual_return``), Sharpe, max drawdown, and win rate. They do not include
a fee total; a fee or commission field is shown when one is present.
"""

from __future__ import annotations

import math
from typing import Any

_FEE_KEYS = (
    "fees",
    "total_fees",
    "total_fee",
    "commission",
    "total_commission",
    "trading_fees",
    "ar_total_fees",
)


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _metrics_dict(payload: dict[str, Any]) -> dict[str, Any]:
    metrics = payload.get("metrics") or {}
    if hasattr(metrics, "model_dump"):
        metrics = metrics.model_dump()
    if isinstance(metrics, dict) and metrics:
        return metrics
    rows = payload.get("artifacts_metrics_csv") or []
    if rows and isinstance(rows[0], dict):
        return rows[0]
    card = payload.get("run_card") or {}
    card_metrics = card.get("metrics") if isinstance(card, dict) else None
    return card_metrics if isinstance(card_metrics, dict) else {}


def _fees(metrics: dict[str, Any], trades: list[dict[str, Any]]) -> float | None:
    for key in _FEE_KEYS:
        if key in metrics:
            return _number(metrics.get(key))
    total = 0.0
    seen = False
    for row in trades:
        if "fee" in row:
            value = _number(row.get("fee"))
        elif "commission" in row:
            value = _number(row.get("commission"))
        else:
            continue
        if value is None:
            continue
        total += value
        seen = True
    return total if seen else None


def _equity(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("artifacts_equity_csv") or payload.get("equity_curve") or []
    points: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        stamp = row.get("timestamp") or row.get("time")
        equity = _number(row.get("equity"))
        if stamp is None or equity is None:
            continue
        drawdown = _number(row.get("drawdown"))
        points.append(
            {
                "time": str(stamp),
                "equity": equity,
                "benchmark": _number(row.get("benchmark_equity")),
                "drawdown": 0.0 if drawdown is None else drawdown,
            }
        )
    return points


def _trades(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("artifacts_trades_csv") or payload.get("trade_log") or []
    trades: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        trades.append(
            {
                "time": str(row.get("timestamp") or row.get("time") or ""),
                "code": str(row.get("code") or ""),
                "side": str(row.get("side") or ""),
                "price": _number(row.get("price")),
                "qty": _number(row.get("qty") if "qty" in row else row.get("quantity")),
                "pnl": _number(row.get("pnl")),
                "event": str(row.get("event") or ""),
            }
        )
    return trades


def _codes(backtest: dict[str, Any]) -> list[str]:
    raw = backtest.get("codes") or []
    if isinstance(raw, str):
        return [raw] if raw else []
    if isinstance(raw, list):
        return [str(code) for code in raw if str(code).strip()]
    return []


def _sources(card: dict[str, Any], backtest: dict[str, Any]) -> list[str]:
    raw = card.get("data_sources")
    if isinstance(raw, str) and raw.strip():
        sources = [raw.strip()]
    elif isinstance(raw, list):
        sources = [str(item).strip() for item in raw if str(item).strip()]
    else:
        sources = []
    if not sources and backtest.get("source"):
        sources = [str(backtest["source"])]
    return sources


def strategy_source(code: dict[str, Any] | str | None) -> str:
    if isinstance(code, str):
        return code
    if not isinstance(code, dict):
        return ""
    if isinstance(code.get("signal_engine.py"), str):
        return code["signal_engine.py"]
    for value in code.values():
        if isinstance(value, str) and value.strip():
            return value
    return ""


def parse_run(payload: dict[str, Any], code: dict[str, Any] | str | None = None) -> dict[str, Any]:
    """Normalize a run payload and the ``/code`` body into one desk result."""
    card = payload.get("run_card") if isinstance(payload.get("run_card"), dict) else {}
    backtest = card.get("backtest") if isinstance(card.get("backtest"), dict) else {}
    metrics = _metrics_dict(payload)
    trade_rows = payload.get("artifacts_trades_csv") or payload.get("trade_log") or []
    if not isinstance(trade_rows, list):
        trade_rows = []
    fees = _fees(metrics, [row for row in trade_rows if isinstance(row, dict)])
    return {
        "run_id": payload.get("run_id"),
        "status": payload.get("status"),
        "codes": _codes(backtest),
        "start_date": backtest.get("start_date"),
        "end_date": backtest.get("end_date"),
        "sources": _sources(card, backtest),
        "metrics": {
            "total_return": _number(metrics.get("total_return")),
            "cagr": _number(metrics.get("annual_return")),
            "sharpe": _number(metrics.get("sharpe")),
            "max_drawdown": _number(metrics.get("max_drawdown")),
            "win_rate": _number(metrics.get("win_rate")),
            "fees": fees,
            "fees_reported": fees is not None,
        },
        "equity": _equity(payload),
        "trades": _trades(payload),
        "code": strategy_source(code),
        "illustrative": False,
    }
