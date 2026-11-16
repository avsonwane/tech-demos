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
import logging
import math
import re
from datetime import date, timedelta
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


def _normalize_source(value: str) -> str:
    key = " ".join(value.strip().lower().replace("_", " ").split())
    if key in {"yfinance", "yahoo", "yahoo finance", "yahoo! finance"}:
        return "Yahoo Finance (yfinance)"
    return value.strip()


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
    return [_normalize_source(item) for item in sources]


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
        "price_bar_source": None,
        "strategy_warning": None,
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
        result["benchmark_label"] = "Buy & hold"
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


_RULE_RE = re.compile(
    r"\b(?:sma|ema|rsi|macd|crossover|cross-over|moving[- ]average|bollinger|breakout|"
    r"momentum|mean[- ]reversion|donchian|stochastic|vwap)\b|\d+\s*/\s*\d+",
    re.IGNORECASE,
)
_LONG_RE = re.compile(
    r"pd\.Series\(\s*1(?:\.0+)?\s*(?:,|\))"
    r"|np\.ones\s*\("
    r"|np\.full\s*\([^)]*,\s*1(?:\.0+)?\s*\)"
    r"|\*\s*0(?:\.0+)?\s*\+\s*1(?:\.0+)?\b"
    r"|(?:^|\n)\s*return\s+1(?:\.0+)?\s*(?:\n|$)"
    r"|\bsignal\s*=\s*1(?:\.0+)?\b"
    r"|\bposition\s*=\s*1(?:\.0+)?\b",
    re.IGNORECASE,
)
_FLAT_RE = re.compile(
    r"pd\.Series\(\s*0(?:\.0+)?\s*(?:,|\))"
    r"|np\.zeros\s*\("
    r"|(?:^|\n)\s*return\s+0(?:\.0+)?\s*(?:\n|$)"
    r"|\bsignal\s*=\s*0(?:\.0+)?\b"
    r"|\bposition\s*=\s*0(?:\.0+)?\b",
    re.IGNORECASE,
)
_DOCSTRING_RE = re.compile(r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'')
_COMMENT_RE = re.compile(r"#.*")
_LOGIC_RE = re.compile(r"rolling|ewm|\.shift\s*\(|\.diff\s*\(|\btalib\b|\bta\.", re.IGNORECASE)


def _code_body(code: str) -> str:
    """Drop docstrings and comments so a label is not taken from prose."""
    return _COMMENT_RE.sub("", _DOCSTRING_RE.sub("", code or ""))


def signal_stance(code: str) -> str | None:
    """``long`` or ``flat`` when the signal is a constant, else None.

    Indicator calls win. A file that only mentions a rule in a comment is
    still constant when the signal itself is ``pd.Series(1.0)`` or ``0``.
    """
    body = _code_body(code)
    if not body.strip() or _LOGIC_RE.search(body):
        return None
    if _LONG_RE.search(body):
        return "long"
    if _FLAT_RE.search(body):
        return "flat"
    return None


def prompt_asks_for_a_rule(prompt: str) -> bool:
    return bool(_RULE_RE.search(prompt or ""))


def constant_signal_warning(code: str, prompt: str) -> str | None:
    """Warn when a rule prompt came back as an always-long or always-flat signal."""
    stance = signal_stance(code)
    if stance is None or not prompt_asks_for_a_rule(prompt):
        return None
    pair = _SMA_PAIR.search(prompt or "")
    if pair:
        asked = f"a {pair.group(1)}/{pair.group(2)} SMA crossover"
    else:
        asked = "a rule-based strategy"
    kind = "always long" if stance == "long" else "always flat"
    return (
        f"The generated signal is constant ({kind}). The prompt asked for {asked}, "
        "and this run did not implement that rule."
    )


def strategy_label(path: Path, code: str, prompt: str = "", *, at_root: bool = False) -> str | None:
    """Name the strategy from its code or, when the code does not say, from the prompt.

    A constant signal is not given the prompt's name. ``pd.Series(1.0)`` under a
    20/50 SMA prompt stays "Always long".
    """
    body = _code_body(code)
    stance = signal_stance(code)
    if stance == "long":
        return "Always long"
    if stance == "flat":
        return "Always flat"
    windows = [int(match) for match in _ROLLING_RE.findall(body)]
    if len(windows) >= 2:
        fast, slow = sorted(windows[:2])
        return f"{fast}/{slow} SMA"
    pair = _SMA_PAIR.search(prompt or "")
    if pair:
        fast, slow = sorted((int(pair.group(1)), int(pair.group(2))))
        return f"{fast}/{slow} SMA"
    if path.name.lower() == "sma" or re.search(r"\bsma\b", body, re.IGNORECASE):
        return "SMA"
    if at_root or _RUN_ID.match(path.name):
        return None
    return path.name


def _name_strategy(parsed: dict[str, Any], path: Path, prompt: str, *, at_root: bool, retried: bool = False) -> None:
    code = parsed.get("code") or ""
    parsed["strategy_label"] = strategy_label(path, code, prompt, at_root=at_root)
    warning = constant_signal_warning(code, prompt)
    if warning and retried:
        warning += " Generation was retried once and the signal was still constant."
    parsed["strategy_warning"] = warning


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


_SKIP_CSV = {
    "equity.csv",
    "trades.csv",
    "metrics.csv",
    "positions.csv",
    "target_positions.csv",
    "fills.csv",
    "orders.csv",
    "validation.csv",
}
_NAMED_BARS = {"bars.csv": 1, "price_series.csv": 2, "prices.csv": 2, "ohlcv.csv": 2}
_DATE_KEYS = ("trade_date", "timestamp", "time", "date", "datetime")
_CLOSE_KEYS = ("close", "adj_close", "adj close")


def _bar_day(value: Any) -> str | None:
    text = str(value or "").strip()
    if len(text) >= 8 and text[:8].isdigit():
        try:
            parsed = date(int(text[:4]), int(text[4:6]), int(text[6:8]))
        except ValueError:
            return None
        return parsed.isoformat()
    text = text.replace("/", "-")
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        return None


def _close_cell(row: dict[str, Any]) -> Any:
    folded = {str(key).strip().lower(): value for key, value in row.items()}
    for key in _CLOSE_KEYS:
        if folded.get(key) not in (None, ""):
            return folded[key]
    return None


def _rows_look_like_bars(path: Path) -> bool:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            header = next(csv.reader(handle), [])
    except OSError:
        return False
    names = {item.strip().lower() for item in header}
    return bool(names & set(_DATE_KEYS)) and bool(names & set(_CLOSE_KEYS))


def _bar_rows(path: Path, codes: list[str]) -> list[dict[str, Any]]:
    wanted = {item.upper() for item in codes}
    file_code = path.stem[6:] if path.stem.lower().startswith("ohlcv_") else ""
    rows: list[dict[str, Any]] = []
    for raw in _read_csv(path):
        row_code = str(raw.get("code") or raw.get("symbol") or file_code or "").strip()
        if wanted and row_code and row_code.upper() not in wanted:
            continue
        day = None
        for key in _DATE_KEYS:
            if raw.get(key):
                day = _bar_day(raw.get(key))
                if day:
                    break
        close = _close_cell(raw)
        if day is None or close in (None, ""):
            continue
        rows.append({"time": day, "close": close, "code": row_code})
    deduped: dict[str, dict[str, Any]] = {}
    for row in rows:
        deduped[row["time"]] = row
    return [deduped[key] for key in sorted(deduped)]


def _ranked_bar_files(artifacts: Path, codes: list[str]) -> list[Path]:
    if not artifacts.is_dir():
        return []
    files = [
        path
        for path in artifacts.glob("*.csv")
        if path.is_file() and path.name.lower() not in _SKIP_CSV
    ]

    def rank(path: Path) -> tuple[int, int, str]:
        if path.stem.lower().startswith("ohlcv_"):
            code = path.stem[6:]
            match = 0 if any(code.upper() == item.upper() for item in codes) else 1
            return (0, match, path.name.lower())
        named = _NAMED_BARS.get(path.name.lower())
        if named is not None:
            return (named, 0, path.name.lower())
        return (5, 0, path.name.lower())

    chosen: list[Path] = []
    for path in sorted(files, key=rank):
        kind = rank(path)[0]
        if kind == 5 and not _rows_look_like_bars(path):
            continue
        if kind <= 5:
            chosen.append(path)
    return chosen


def load_price_bars(directory: Path, codes: list[str] | None = None) -> tuple[list[dict[str, Any]], str | None]:
    """Read one close series from the run's artifacts.

    Live Vibe-Trading 0.1.19 writes ``artifacts/ohlcv_<TICKER>.csv``
    (``trade_date,open,high,low,close,volume``). ``bars.csv``,
    ``price_series.csv``, and any other OHLCV csv in that folder are accepted.
    The ticker named on the run wins when several files are present.
    """
    named = [str(item) for item in (codes or []) if str(item).strip()]
    for path in _ranked_bar_files(directory / "artifacts", named):
        rows = _bar_rows(path, named)
        if len(rows) >= 2:
            return rows, f"artifacts/{path.name}"
    return [], None


def fetch_yahoo_bars(symbol: str, start: str, end: str) -> list[dict[str, Any]]:
    """Daily closes from Yahoo Finance for one ticker and an inclusive date range."""
    import yfinance as yf

    start_day = date.fromisoformat(str(start)[:10])
    end_day = date.fromisoformat(str(end)[:10]) + timedelta(days=1)
    frame = yf.Ticker(symbol).history(
        start=start_day.isoformat(),
        end=end_day.isoformat(),
        interval="1d",
        auto_adjust=False,
    )
    if frame is None or len(frame) == 0:
        return []
    rows: list[dict[str, Any]] = []
    for stamp, row in frame.iterrows():
        day = stamp.date().isoformat() if hasattr(stamp, "date") else str(stamp)[:10]
        close = row["Close"] if "Close" in row else None
        try:
            value = float(close)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(value) or value <= 0:
            continue
        rows.append({"time": day, "close": value, "code": symbol})
    return rows


def _bar_symbol(parsed: dict[str, Any]) -> str | None:
    codes = parsed.get("codes") or []
    if codes:
        return str(codes[0])
    config = parsed.get("config") if isinstance(parsed.get("config"), dict) else {}
    raw = config.get("codes") if isinstance(config, dict) else None
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    if isinstance(raw, list) and raw:
        return str(raw[0])
    return None


def ensure_price_bars(parsed: dict[str, Any]) -> None:
    """Download closes when the run directory has no OHLCV file."""
    if parsed.get("price_bars"):
        return
    symbol = _bar_symbol(parsed)
    start = parsed.get("start_date")
    end = parsed.get("end_date")
    if not symbol or not start or not end:
        return
    try:
        rows = fetch_yahoo_bars(symbol, str(start), str(end))
    except Exception:
        logging.getLogger("desk").warning("Yahoo bar fetch failed for %s", symbol, exc_info=True)
        return
    if len(rows) < 2:
        return
    parsed["price_bars"] = rows
    parsed["price_bar_source"] = (
        f"Yahoo Finance (yfinance) for {symbol} from {start} to {end}, "
        "because the run artifacts had no OHLCV file"
    )


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
        if not parsed.get("codes"):
            parsed["codes"] = _codes(config)
        if parsed.get("start_date") is None and config.get("start_date"):
            parsed["start_date"] = config.get("start_date")
            parsed["end_date"] = parsed.get("end_date") or config.get("end_date")
    if not parsed.get("price_bars"):
        bars, source = load_price_bars(directory, parsed.get("codes") or [])
        if bars:
            parsed["price_bars"] = bars
            parsed["price_bar_source"] = source


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


def resolve_result(
    payload: dict[str, Any],
    code: dict[str, Any] | str | None = None,
    *,
    retried: bool = False,
) -> dict[str, Any]:
    """Use a nested strategy directory when the run root is the comparison."""
    prompt = payload.get("prompt") if isinstance(payload.get("prompt"), str) else ""
    directory = payload.get("run_directory") or payload.get("run_dir")
    root = Path(directory) if isinstance(directory, str) and directory else None
    if root is None or not root.is_dir():
        parsed = parse_run(payload, code)
        _name_strategy(parsed, Path("run"), prompt, at_root=True, retried=retried)
        return _with_report(parsed)
    primary, benchmark = choose_strategy(root)
    if primary == root and benchmark is None:
        fills = _read_fills(root)
        source = _read_code(root) or strategy_source(code)
        parsed = parse_run(_merge_run_payload(_payload_from_dir(root), payload), source or code, fills=fills)
        _apply_files(parsed, root)
        ensure_price_bars(parsed)
        if payload.get("run_id"):
            parsed["run_id"] = payload["run_id"]
        if payload.get("status"):
            parsed["status"] = payload["status"]
        _name_strategy(parsed, root, prompt, at_root=True, retried=retried)
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
    ensure_price_bars(parsed)
    _name_strategy(parsed, primary, prompt, at_root=primary == root, retried=retried)
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
