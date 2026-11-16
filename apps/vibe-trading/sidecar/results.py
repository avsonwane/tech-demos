"""Turn a Vibe-Trading ``GET /runs/{id}`` payload into the desk result.

Equity prefers ``artifacts_equity_csv`` because the preview curve in 0.1.19
drops ``benchmark_equity``. Summary metrics include return, CAGR
(``annual_return``), Sharpe, max drawdown, and win rate. They do not include
a fee total. Fees are the sum of ``fee`` or ``commission`` on trades, or on
``fills.jsonl`` when the summary omits them.

A session often writes the requested strategy under a subdirectory (``sma/``)
and leaves buy-and-hold at the run root. The headline is that strategy. The
root curve is the benchmark line.
"""

from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path
from typing import Any

from report import build_report

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


def _sum_fee_rows(rows: list[dict[str, Any]]) -> float | None:
    total = 0.0
    seen = False
    for row in rows:
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


def _fees(
    metrics: dict[str, Any],
    trades: list[dict[str, Any]],
    fills: list[dict[str, Any]] | None = None,
) -> float | None:
    for key in _FEE_KEYS:
        if key in metrics:
            reported = _number(metrics.get(key))
            if reported is not None:
                return reported
    from_fills = _sum_fee_rows(fills or [])
    if from_fills is not None:
        return from_fills
    return _sum_fee_rows(trades)


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


def _cash_from_mapping(mapping: Any) -> float | None:
    if not isinstance(mapping, dict):
        return None
    for key in ("initial_cash", "initial_capital", "starting_capital"):
        value = _number(mapping.get(key))
        if value is not None and value > 0:
            return value
    return None


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


def parse_run(
    payload: dict[str, Any],
    code: dict[str, Any] | str | None = None,
    fills: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Normalize a run payload and the ``/code`` body into one desk result."""
    card = payload.get("run_card") if isinstance(payload.get("run_card"), dict) else {}
    backtest = card.get("backtest") if isinstance(card.get("backtest"), dict) else {}
    metrics = _metrics_dict(payload)
    trade_rows = payload.get("artifacts_trades_csv") or payload.get("trade_log") or []
    if not isinstance(trade_rows, list):
        trade_rows = []
    fill_rows = [row for row in (fills or []) if isinstance(row, dict)]
    fees = _fees(metrics, [row for row in trade_rows if isinstance(row, dict)], fill_rows)
    annualisation = card.get("annualisation") if isinstance(card.get("annualisation"), dict) else {}
    config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
    cash = _cash_from_mapping(backtest)
    if cash is None:
        cash = _cash_from_mapping(config)
    price_bars = payload.get("price_bars") if isinstance(payload.get("price_bars"), list) else []
    return {
        "run_id": payload.get("run_id"),
        "status": payload.get("status"),
        "strategy_label": None,
        "benchmark_label": None,
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
            "benchmark_return": None,
            "fees": fees,
            "fees_reported": fees is not None,
        },
        "equity": _equity(payload),
        "trades": _trades(payload),
        "code": strategy_source(code),
        "illustrative": False,
        "initial_cash": cash,
        "bars_per_year": _number(annualisation.get("bars_per_year")),
        "config": config,
        "backtest": backtest,
        "price_bars": price_bars,
    }


def _with_report(
    result: dict[str, Any],
    fills: list[dict[str, Any]] | None = None,
    benchmark: dict[str, Any] | None = None,
    benchmark_fills: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    result["report"] = build_report(result, fills, benchmark, benchmark_fills)
    row = next((item for item in result["report"]["comparison"] if item["id"] == "return"), None)
    if row is not None and row.get("benchmark") is not None:
        if not result.get("benchmark_label"):
            result["benchmark_label"] = "Buy and hold"
        if result["metrics"].get("benchmark_return") is None:
            result["metrics"]["benchmark_return"] = row["benchmark"]
    return result


_BH_NAMES = {"bh", "bnh", "buyhold", "buy_and_hold", "buy-and-hold", "benchmark", "hold"}
_SKIP_DIRS = {"artifacts", "code", "logs", "log", "__pycache__"}
_INDICATOR_RE = re.compile(r"rolling|ewm|crossover|\bsma\b|\bema\b|macd|\brsi\b|\.shift\s*\(", re.IGNORECASE)
_ROLLING_RE = re.compile(r"rolling\s*\(\s*(\d+)\s*\)")


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _read_fills(path: Path) -> list[dict[str, Any]]:
    file = path / "artifacts" / "fills.jsonl"
    if not file.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in file.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            item = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _read_code(path: Path) -> str:
    file = path / "code" / "signal_engine.py"
    if not file.is_file():
        return ""
    return file.read_text(encoding="utf-8")


def _is_backtest_dir(path: Path) -> bool:
    artifacts = path / "artifacts"
    return (artifacts / "equity.csv").is_file() or (artifacts / "metrics.csv").is_file()


def looks_like_buy_and_hold(path: Path) -> bool:
    """A comparison run is buy-and-hold when its folder or its signal says so."""
    if path.name.lower() in _BH_NAMES:
        return True
    source = _read_code(path)
    if not source or _INDICATOR_RE.search(source):
        return False
    lowered = source.lower()
    if "buy" in lowered and "hold" in lowered:
        return True
    return bool(re.search(r"\bones\s*\(|np\.ones|=\s*1(?:\.0)?\b", source))


def _strategy_rank(path: Path) -> tuple[int, str]:
    name = path.name.lower()
    preferred = 0 if any(token in name for token in ("sma", "cross", "signal", "strategy")) else 1
    return (preferred, name)


def choose_strategy(root: Path) -> tuple[Path, Path | None]:
    """Pick the requested strategy directory and the buy-and-hold comparison.

    Nested backtests win over the run root. The root is the usual place the
    agent leaves the buy-and-hold comparison.
    """
    if not root.is_dir():
        return root, None
    children: list[Path] = []
    for child in sorted(root.iterdir(), key=lambda item: item.name):
        if not child.is_dir() or child.name.startswith(".") or child.name in _SKIP_DIRS:
            continue
        if _is_backtest_dir(child):
            children.append(child)
    if not children:
        return root, None
    parent_is = _is_backtest_dir(root)
    candidates = ([root] if parent_is else []) + children
    strategies = [item for item in candidates if not looks_like_buy_and_hold(item)]
    baselines = [item for item in candidates if looks_like_buy_and_hold(item)]
    nested = [item for item in strategies if item != root]
    pool = nested or strategies
    if not pool:
        return (root if parent_is else children[0]), None
    primary = sorted(pool, key=_strategy_rank)[0]
    benchmark = next((item for item in baselines if item != primary), None)
    return primary, benchmark


_SMA_PAIR = re.compile(r"(\d+)\s*/\s*(\d+)\s*(?:SMA|moving[- ]average)", re.IGNORECASE)
_RUN_ID = re.compile(r"^\d{8}_\d+")


def strategy_label(path: Path, code: str, prompt: str = "", *, at_root: bool = False) -> str | None:
    """Name the strategy from its code or, when the code does not say, from the prompt."""
    windows = [int(match) for match in _ROLLING_RE.findall(code or "")]
    if len(windows) >= 2:
        fast, slow = sorted(windows[:2])
        return f"{fast}/{slow} SMA"
    pair = _SMA_PAIR.search(prompt or "")
    if pair:
        fast, slow = sorted((int(pair.group(1)), int(pair.group(2))))
        return f"{fast}/{slow} SMA"
    if path.name.lower() == "sma" or re.search(r"\bsma\b", code or "", re.IGNORECASE):
        return "SMA"
    if at_root or _RUN_ID.match(path.name):
        return None
    return path.name


def _payload_from_dir(path: Path) -> dict[str, Any]:
    card = path / "run_card.json"
    try:
        loaded = json.loads(card.read_text(encoding="utf-8")) if card.is_file() else {}
    except json.JSONDecodeError:
        loaded = {}
    metrics_rows = _read_csv(path / "artifacts" / "metrics.csv")
    return {
        "run_id": path.name,
        "status": "success",
        "metrics": metrics_rows[0] if metrics_rows else {},
        "run_card": loaded if isinstance(loaded, dict) else {},
        "artifacts_equity_csv": _read_csv(path / "artifacts" / "equity.csv"),
        "artifacts_trades_csv": _read_csv(path / "artifacts" / "trades.csv"),
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _apply_files(parsed: dict[str, Any], directory: Path) -> None:
    """Pull starting capital, the fee schedule, and price bars off the run directory."""
    config = _read_json(directory / "config.json") or _read_json(directory / "code" / "config.json")
    if config:
        merged = dict(parsed.get("config") or {})
        merged.update(config)
        parsed["config"] = merged
        cash = _cash_from_mapping(config)
        if cash is not None:
            parsed["initial_cash"] = cash
    if not parsed.get("price_bars"):
        bars = _read_csv(directory / "artifacts" / "bars.csv")
        if bars:
            parsed["price_bars"] = bars


def _merge_run_payload(disk: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    merged = dict(disk)
    for key in ("metrics", "run_card", "artifacts_equity_csv", "artifacts_trades_csv"):
        value = payload.get(key)
        if value:
            merged[key] = value
    for key, value in payload.items():
        if key in {"metrics", "run_card", "artifacts_equity_csv", "artifacts_trades_csv"}:
            continue
        if value not in (None, ""):
            merged[key] = value
    return merged


def _overlay_benchmark(result: dict[str, Any], benchmark_equity: list[dict[str, Any]]) -> None:
    by_day: dict[str, float] = {}
    for point in benchmark_equity:
        stamp = str(point.get("time") or "")
        equity = point.get("equity")
        if stamp and isinstance(equity, (int, float)):
            by_day[stamp[:10]] = float(equity)
    for point in result["equity"]:
        match = by_day.get(str(point["time"])[:10])
        if match is not None:
            point["benchmark"] = match


def resolve_result(payload: dict[str, Any], code: dict[str, Any] | str | None = None) -> dict[str, Any]:
    """Use a nested strategy directory when the run root is the comparison."""
    prompt = payload.get("prompt") if isinstance(payload.get("prompt"), str) else ""
    directory = payload.get("run_directory") or payload.get("run_dir")
    root = Path(directory) if isinstance(directory, str) and directory else None
    if root is None or not root.is_dir():
        parsed = parse_run(payload, code)
        parsed["strategy_label"] = strategy_label(Path("run"), parsed["code"], prompt, at_root=True)
        return _with_report(parsed)
    primary, benchmark = choose_strategy(root)
    if primary == root and benchmark is None:
        fills = _read_fills(root)
        source = _read_code(root) or strategy_source(code)
        parsed = parse_run(_merge_run_payload(_payload_from_dir(root), payload), source or code, fills=fills)
        _apply_files(parsed, root)
        if payload.get("run_id"):
            parsed["run_id"] = payload["run_id"]
        if payload.get("status"):
            parsed["status"] = payload["status"]
        parsed["strategy_label"] = strategy_label(root, parsed["code"], prompt, at_root=True)
        return _with_report(parsed, fills)
    primary_code = _read_code(primary)
    if not primary_code and primary == root:
        primary_code_value: dict[str, Any] | str | None = code
    else:
        primary_code_value = primary_code
    primary_fills = _read_fills(primary)
    parsed = parse_run(_payload_from_dir(primary), primary_code_value, fills=primary_fills)
    if primary != root:
        _apply_files(parsed, root)
    _apply_files(parsed, primary)
    if payload.get("run_id"):
        parsed["run_id"] = payload["run_id"]
    parsed["strategy_label"] = strategy_label(primary, parsed["code"], prompt, at_root=primary == root)
    baseline = None
    benchmark_fills: list[dict[str, Any]] | None = None
    if benchmark is not None:
        benchmark_fills = _read_fills(benchmark)
        baseline = parse_run(_payload_from_dir(benchmark), _read_code(benchmark), fills=benchmark_fills)
        _apply_files(baseline, benchmark)
        _overlay_benchmark(parsed, baseline["equity"])
        parsed["benchmark_label"] = "Buy and hold"
        parsed["benchmark_source"] = "buy-and-hold run"
        parsed["metrics"]["benchmark_return"] = baseline["metrics"]["total_return"]
    parent = parse_run(payload, code)
    if not parsed["sources"]:
        parsed["sources"] = parent["sources"]
    if not parsed["codes"]:
        parsed["codes"] = parent["codes"]
    if parsed.get("initial_cash") is None and parent.get("initial_cash") is not None:
        parsed["initial_cash"] = parent["initial_cash"]
    if not parsed.get("config") and parent.get("config"):
        parsed["config"] = parent["config"]
    if parsed.get("start_date") is None and parent.get("start_date"):
        parsed["start_date"] = parent["start_date"]
        parsed["end_date"] = parsed.get("end_date") or parent.get("end_date")
    if baseline is not None and baseline.get("initial_cash") is None and parsed.get("initial_cash") is not None:
        baseline["initial_cash"] = parsed["initial_cash"]
        baseline["bars_per_year"] = baseline.get("bars_per_year") or parsed.get("bars_per_year")
    return _with_report(parsed, primary_fills, baseline, benchmark_fills)
