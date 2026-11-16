import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from report import build_report
from results import resolve_result

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "reliance_sma"


def _row(report, row_id):
    return next(row for row in report["comparison"] if row["id"] == row_id)


def _reliance():
    payload = {
        "run_id": "sample",
        "status": "illustrative",
        "run_directory": str(FIXTURE),
        "metrics": {
            "total_return": -0.0604,
            "annual_return": -0.0604,
            "sharpe": -0.16,
            "max_drawdown": -0.024,
            "win_rate": 0,
        },
        "run_card": {
            "data_sources": ["yfinance"],
            "backtest": {
                "codes": ["RELIANCE.NS"],
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "source": "yfinance",
            },
        },
    }
    return resolve_result(payload, {"signal_engine.py": "buy and hold"})


def test_reliance_report_uses_only_the_fixture_files():
    report = _reliance()["report"]
    assert "18.74 percentage points" in report["summary"]
    assert "flat from 2024-07-01 until the next entry on 2024-09-01" in report["summary"]
    assert "still open" in report["summary"]
    assert "Aug 14" not in report["summary"]

    assert _row(report, "return")["strategy"] == pytest.approx(0.116)
    assert _row(report, "return")["benchmark"] == pytest.approx(-0.0713544263228375)
    assert _row(report, "sharpe")["strategy"] == 0.8
    assert _row(report, "sharpe")["benchmark"] == pytest.approx(-2.527448435519075)
    assert _row(report, "sortino")["strategy"] is None
    assert _row(report, "volatility")["strategy"] is None
    assert _row(report, "max_drawdown")["strategy"] == -0.0959
    assert _row(report, "max_drawdown")["benchmark"] == pytest.approx(-0.0796555718763402)
    assert _row(report, "win_rate")["strategy"] == 1
    assert _row(report, "win_rate")["benchmark"] == 0
    assert _row(report, "trades")["benchmark"] == 1
    assert _row(report, "profit_factor")["strategy"] is None
    assert _row(report, "avg_win")["strategy"] == 120
    assert _row(report, "avg_loss")["strategy"] is None
    assert _row(report, "best")["strategy"] == 120
    assert _row(report, "worst")["strategy"] == 120
    assert _row(report, "trades")["strategy"] == 1
    assert _row(report, "fees_pct")["strategy"] == 7355 / 120
    assert _row(report, "exposure")["benchmark"] == 1

    months = report["monthly"][0]["months"]
    assert report["monthly"][0]["year"] == 2024
    assert months == [None] * 12

    closed, still_open = report["round_trips"]
    assert closed["entry_time"] == "2024-03-01"
    assert closed["exit_time"] == "2024-07-01"
    assert closed["entry_price"] == 100
    assert closed["exit_price"] == 112
    assert closed["holding_days"] == 122
    assert closed["pnl"] == 120
    assert closed["return_pct"] == 0.12
    assert closed["fees"] == 4500
    assert closed["open"] is False
    assert still_open["entry_time"] == "2024-09-01"
    assert still_open["exit_time"] is None
    assert still_open["pnl"] is None
    assert still_open["holding_days"] == 121
    assert still_open["fees"] == 2855
    assert still_open["open"] is True

    assert report["drawdowns"] == [
        {"start": "2024-06-03", "trough": "2024-12-31", "recovery": None, "depth": -0.0959}
    ]
    assert report["notes"]["warmup"] == "2024-01-01 to 2024-01-02"
    assert report["notes"]["frequency"] == "irregular"
    assert report["notes"]["fee_model"] is None
    assert report["notes"]["starting_capital"] == 100
    assert report["notes"]["fees"] == 7355
    assert report["notes"]["sources"] == ["Yahoo Finance (yfinance)"]
    assert "not recomputed" in report["notes"]["sharpe_note"]
    assert "—" in report["markdown"]
    assert "18.74 percentage points" in report["markdown"]
    assert report["notes"]["benchmark_source"] == "Buy & hold, fees included: one entry + one exit"
    assert "recorded a buy-and-hold run at -6.04%" in report["notes"]["recorded_benchmark"]
    assert "2024-03-01,2024-07-01,100,112,10,122,120,0.12,4500,closed" in report["trades_csv"]


def test_adjacent_months_and_a_daily_curve_fill_sortino():
    equity = []
    day = date(2024, 1, 2)
    level = 100.0
    changes = [0.01, -0.02, 0.015, -0.005] * 8
    for change in changes:
        equity.append({"time": day.isoformat(), "equity": level, "drawdown": 0 if change >= 0 else -0.01})
        level *= 1 + change
        day += timedelta(days=1)
    result = {
        "strategy_label": "Probe",
        "benchmark_label": None,
        "codes": ["TEST"],
        "start_date": "2024-01-01",
        "end_date": "2024-02-29",
        "sources": ["local"],
        "metrics": {
            "total_return": None,
            "cagr": None,
            "sharpe": None,
            "max_drawdown": None,
            "win_rate": None,
            "benchmark_return": None,
            "fees": None,
            "fees_reported": False,
        },
        "equity": equity,
        "trades": [
            {"time": "2024-01-02", "code": "TEST", "side": "buy", "price": 10, "qty": 1, "pnl": 0, "event": "entry"},
            {"time": "2024-01-05", "code": "TEST", "side": "sell", "price": 9, "qty": 1, "pnl": -1, "event": "exit"},
            {"time": "2024-01-08", "code": "TEST", "side": "buy", "price": 10, "qty": 1, "pnl": 0, "event": "entry"},
            {"time": "2024-01-12", "code": "TEST", "side": "sell", "price": 12, "qty": 1, "pnl": 2, "event": "exit"},
        ],
    }
    report = build_report(result, [])
    february = report["monthly"][0]["months"][1]
    assert february is not None
    assert _row(report, "sortino")["strategy"] is not None
    assert _row(report, "volatility")["strategy"] is not None
    assert _row(report, "profit_factor")["strategy"] == 2
    assert _row(report, "avg_loss")["strategy"] == -1
    assert _row(report, "win_rate")["strategy"] == 0.5
    assert report["notes"]["sharpe_note"] is None
    assert report["notes"]["frequency"] == "daily"
    assert report["notes"]["warmup"] == "2024-01-01 to 2024-01-02"


DAILY = Path(__file__).resolve().parents[1] / "fixtures" / "reliance_daily"


def _shown(value: float) -> str:
    number = value * 100
    if number > 0:
        return f"+{number:.2f}%"
    return f"{number:.2f}%"


def test_daily_flat_layout_matches_the_card_and_keeps_the_benchmark():
    result = resolve_result(
        {
            "run_id": "reliance-daily",
            "status": "success",
            "run_directory": str(DAILY),
        }
    )
    report = result["report"]
    card_return = result["metrics"]["total_return"]
    report_return = _row(report, "return")["strategy"]
    report_benchmark = _row(report, "return")["benchmark"]
    assert card_return == pytest.approx(0.116, abs=1e-4)
    assert report_return == pytest.approx(card_return, abs=1e-4)
    assert report_benchmark == pytest.approx(result["metrics"]["benchmark_return"], abs=1e-4)
    assert report_benchmark == pytest.approx(-0.0713544263228375)
    assert _row(report, "cagr")["strategy"] == pytest.approx(result["metrics"]["cagr"], abs=1e-4)
    assert _row(report, "max_drawdown")["strategy"] == pytest.approx(result["metrics"]["max_drawdown"], abs=1e-4)
    assert result["strategy_label"] == "20/50 SMA"
    assert result["strategy_warning"] is None
    assert result["benchmark_label"] == "Buy & hold"
    assert report["notes"]["benchmark_source"] == "Buy & hold, fees included: one entry + one exit"
    assert "artifacts/ohlcv_RELIANCE.NS.csv" in report["notes"]["benchmark_detail"]
    assert report["monthly"][0]["marks"][0] == "capital"
    assert report["monthly"][0]["months"][0] is not None
    assert _row(report, "trades")["benchmark"] == 1
    assert _row(report, "exposure")["benchmark"] == pytest.approx(1)
    assert _row(report, "win_rate")["benchmark"] == 0
    assert report["notes"]["starting_capital"] == 1_000_000
    assert report["notes"]["frequency"] == "daily"
    assert report["notes"]["warmup"] == "2023-08-01 to 2024-01-01"
    assert report["notes"]["fee_model"] == "slippage 10 bps, STT 10 bps"
    assert report["notes"]["sharpe_note"] is not None
    assert "not a regular daily series" not in report["notes"]["sharpe_note"]
    assert "Buy-and-hold was not recorded" not in report["summary"]
    assert "flat from 2024-08-14 through 2024-12-31" in report["summary"]
    assert "2024-05-03" not in report["summary"]
    assert _shown(card_return) in report["summary"]
    assert _shown(report_benchmark) in report["summary"]
    assert len(result["equity"]) > 200
    assert all(point["benchmark"] is not None for point in result["equity"])


def test_prompt_names_a_root_strategy_when_the_code_does_not(tmp_path: Path):
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "equity.csv").write_text(
        "timestamp,equity,drawdown\n2024-01-02,100,0\n2024-01-03,101,0\n",
        encoding="utf-8",
    )
    (artifacts / "trades.csv").write_text("timestamp,code,side,price,qty,pnl,event\n", encoding="utf-8")
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "signal_engine.py").write_text("class SignalEngine:\n    pass\n", encoding="utf-8")
    (tmp_path / "run_card.json").write_text("{}", encoding="utf-8")
    result = resolve_result(
        {
            "run_directory": str(tmp_path),
            "prompt": "Backtest a 20/50 SMA crossover on RELIANCE.NS",
        }
    )
    assert result["strategy_label"] == "20/50 SMA"
    assert result["benchmark_label"] is None


def test_a_benchmark_folder_does_not_change_the_computed_buy_and_hold(tmp_path: Path):
    """The same closes, capital, and costs produce one figure with or without a bh/ run."""
    bars = (DAILY / "artifacts" / "ohlcv_RELIANCE.NS.csv").read_text(encoding="utf-8")
    for name in ("flat", "nested"):
        root = tmp_path / name
        artifacts = root / "artifacts"
        artifacts.mkdir(parents=True)
        filename = "ohlcv_RELIANCE.NS.csv" if name == "nested" else "bars.csv"
        (artifacts / filename).write_text(bars, encoding="utf-8")
        (artifacts / "equity.csv").write_text(
            "timestamp,equity,drawdown\n2024-01-02,1000000,0\n2024-12-31,1100000,0\n",
            encoding="utf-8",
        )
        (artifacts / "trades.csv").write_text("timestamp,code,side,price,qty,pnl,event\n", encoding="utf-8")
        (root / "run_card.json").write_text(
            json.dumps(
                {
                    "data_sources": ["yahoo"],
                    "backtest": {
                        "codes": ["RELIANCE.NS"],
                        "start_date": "2024-01-01",
                        "end_date": "2024-12-31",
                        "initial_cash": 1_000_000,
                    },
                }
            ),
            encoding="utf-8",
        )
    nested = tmp_path / "nested"
    bh = nested / "bh" / "artifacts"
    bh.mkdir(parents=True)
    (bh / "equity.csv").write_text(
        "timestamp,equity,drawdown\n2024-01-02,100,0\n2024-12-31,50,-0.5\n",
        encoding="utf-8",
    )
    (bh / "trades.csv").write_text("timestamp,code,side,price,qty,pnl,event\n", encoding="utf-8")
    (bh / "metrics.csv").write_text(
        "total_return,annual_return,sharpe,max_drawdown,win_rate\n-0.5,-0.5,0,-0.5,0\n",
        encoding="utf-8",
    )
    (nested / "bh" / "code").mkdir()
    (nested / "bh" / "code" / "signal_engine.py").write_text("signal = 1\n# buy and hold\n", encoding="utf-8")
    flat = resolve_result({"run_directory": str(tmp_path / "flat")})
    with_folder = resolve_result({"run_directory": str(nested)})
    flat_return = _row(flat["report"], "return")["benchmark"]
    folder_return = _row(with_folder["report"], "return")["benchmark"]
    assert flat_return == pytest.approx(folder_return)
    assert flat_return == pytest.approx(-0.0713544263228375)
    assert "recorded a buy-and-hold run" in with_folder["report"]["notes"]["recorded_benchmark"]
    assert with_folder["report"]["notes"]["sources"] == ["Yahoo Finance (yfinance)"]
    assert flat["report"]["notes"]["sources"] == ["Yahoo Finance (yfinance)"]


def test_months_before_the_first_equity_bar_are_warmup():
    equity = []
    day = date(2024, 3, 1)
    level = 100.0
    while day <= date(2024, 4, 30):
        if day.weekday() < 5:
            equity.append({"time": day.isoformat(), "equity": level, "drawdown": 0})
            level *= 1.001
        day += timedelta(days=1)
    report = build_report(
        {
            "strategy_label": "Probe",
            "start_date": "2024-01-01",
            "end_date": "2024-04-30",
            "sources": [],
            "metrics": {},
            "equity": equity,
            "trades": [],
            "initial_cash": 100,
        },
        [],
    )
    year = report["monthly"][0]
    assert year["months"][0] == 0
    assert year["marks"][0] == "warmup"
    assert year["months"][1] == 0
    assert year["marks"][1] == "warmup"
    assert year["marks"][2] == "capital"
    assert year["months"][2] is not None


def test_ohlcv_ticker_file_matches_bars_csv(tmp_path: Path):
    """The live artifact name and bars.csv are the same closes."""
    text = (DAILY / "artifacts" / "ohlcv_RELIANCE.NS.csv").read_text(encoding="utf-8")
    card = {
        "data_sources": ["yfinance"],
        "backtest": {
            "codes": ["RELIANCE.NS"],
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_cash": 1_000_000,
            "engine": "india_equity",
        },
    }
    returns = []
    for name in ("ohlcv_RELIANCE.NS.csv", "bars.csv"):
        root = tmp_path / name
        artifacts = root / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / name).write_text(text, encoding="utf-8")
        (artifacts / "equity.csv").write_text(
            "timestamp,equity,drawdown\n2024-01-02,1000000,0\n2024-12-31,1100000,0\n",
            encoding="utf-8",
        )
        (root / "run_card.json").write_text(json.dumps(card), encoding="utf-8")
        result = resolve_result({"run_directory": str(root)})
        returns.append(_row(result["report"], "return")["benchmark"])
        assert result["price_bar_source"] == f"artifacts/{name}"
    assert returns[0] == pytest.approx(returns[1])
    assert returns[0] == pytest.approx(-0.0713544263228375)


def test_compact_trade_date_ohlcv_is_a_price_file(tmp_path: Path):
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "ohlcv_TEST.csv").write_text(
        "trade_date,open,high,low,close,volume\n20240102,100,101,99,100,1\n20240103,90,91,89,90,1\n",
        encoding="utf-8",
    )
    (artifacts / "equity.csv").write_text(
        "timestamp,equity,drawdown\n2024-01-02,1000,0\n2024-01-03,1100,0\n",
        encoding="utf-8",
    )
    (tmp_path / "run_card.json").write_text(
        '{"backtest": {"initial_cash": 1000, "codes": ["TEST"], "start_date": "2024-01-02", "end_date": "2024-01-03"}}',
        encoding="utf-8",
    )
    result = resolve_result({"run_directory": str(tmp_path)})
    assert result["price_bar_source"] == "artifacts/ohlcv_TEST.csv"
    assert _row(result["report"], "return")["benchmark"] == pytest.approx(-0.1)


def test_missing_ohlcv_fetches_yahoo_bars(tmp_path: Path, monkeypatch):
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "equity.csv").write_text(
        "timestamp,equity,drawdown,benchmark_equity\n2024-01-02,1000,0,1000\n2024-01-03,1100,0,900\n",
        encoding="utf-8",
    )
    (tmp_path / "run_card.json").write_text(
        json.dumps(
            {
                "data_sources": ["yahoo"],
                "backtest": {
                    "codes": ["AAPL"],
                    "start_date": "2024-01-02",
                    "end_date": "2024-01-03",
                    "initial_cash": 1000,
                },
            }
        ),
        encoding="utf-8",
    )
    seen = {}

    def fake_fetch(symbol, start, end):
        seen["symbol"] = symbol
        seen["start"] = start
        seen["end"] = end
        return [{"time": "2024-01-02", "close": 100}, {"time": "2024-01-03", "close": 80}]

    monkeypatch.setattr("results.fetch_yahoo_bars", fake_fetch)
    result = resolve_result({"run_directory": str(tmp_path)})
    assert seen == {"symbol": "AAPL", "start": "2024-01-02", "end": "2024-01-03"}
    assert "Yahoo Finance (yfinance)" in result["price_bar_source"]
    assert _row(result["report"], "return")["benchmark"] == pytest.approx(-0.2)
    assert "price-only" in result["report"]["notes"]["recorded_benchmark"]


def test_constant_signal_is_not_titled_from_the_prompt(tmp_path: Path):
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "equity.csv").write_text(
        "timestamp,equity,drawdown\n2024-01-02,100,0\n2024-06-01,90,0\n",
        encoding="utf-8",
    )
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "signal_engine.py").write_text(
        "import pandas as pd\n\n"
        "class SignalEngine:\n"
        "    def generate(self, data):\n"
        "        return pd.Series(1.0, index=data.index)\n",
        encoding="utf-8",
    )
    (tmp_path / "run_card.json").write_text("{}", encoding="utf-8")
    result = resolve_result(
        {
            "run_directory": str(tmp_path),
            "prompt": "Backtest a 20/50 SMA crossover on RELIANCE.NS",
        }
    )
    assert result["strategy_label"] == "Always long"
    assert result["strategy_label"] != "20/50 SMA"
    assert "constant (always long)" in result["strategy_warning"]
    assert "20/50 SMA" in result["strategy_warning"]
    assert result["report"]["notes"]["strategy_warning"] == result["strategy_warning"]
    assert result["strategy_warning"] in result["report"]["markdown"]


def test_price_bars_supply_buy_and_hold_when_the_equity_file_has_no_benchmark(tmp_path: Path):
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "equity.csv").write_text(
        "timestamp,equity,drawdown\n2024-01-02,1000,0\n2024-01-03,1100,0\n",
        encoding="utf-8",
    )
    (artifacts / "trades.csv").write_text("timestamp,code,side,price,qty,pnl,event\n", encoding="utf-8")
    (artifacts / "bars.csv").write_text(
        "timestamp,close\n2024-01-02,100\n2024-01-03,90\n",
        encoding="utf-8",
    )
    (tmp_path / "run_card.json").write_text(
        '{"backtest": {"initial_cash": 1000, "codes": ["TEST"]}}',
        encoding="utf-8",
    )
    result = resolve_result({"run_directory": str(tmp_path)})
    assert result["benchmark_label"] == "Buy & hold"
    assert result["report"]["notes"]["benchmark_source"] == "Buy & hold, fees included: one entry + one exit"
    assert _row(result["report"], "return")["benchmark"] == pytest.approx(-0.1)
    assert _row(result["report"], "trades")["benchmark"] == 1
    assert _row(result["report"], "exposure")["benchmark"] == pytest.approx(1)
