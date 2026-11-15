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
    assert "17.64 percentage points" in report["summary"]
    assert "flat from 2024-07-01 until the next entry on 2024-09-01" in report["summary"]
    assert "still open" in report["summary"]
    assert "Aug 14" not in report["summary"]

    assert _row(report, "return")["strategy"] == pytest.approx(0.116)
    assert _row(report, "return")["benchmark"] == pytest.approx(-0.0604)
    assert _row(report, "sharpe")["strategy"] == 0.8
    assert _row(report, "sharpe")["benchmark"] == -0.16
    assert _row(report, "sortino")["strategy"] is None
    assert _row(report, "volatility")["strategy"] is None
    assert _row(report, "max_drawdown")["strategy"] == -0.0959
    assert _row(report, "max_drawdown")["benchmark"] == -0.0604
    assert _row(report, "win_rate")["strategy"] == 1
    assert _row(report, "win_rate")["benchmark"] is None
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
    assert report["notes"]["warmup"] is None
    assert report["notes"]["fee_model"] is None
    assert report["notes"]["starting_capital"] == 100
    assert report["notes"]["fees"] == 7355
    assert report["notes"]["sources"] == ["yfinance"]
    assert "not recomputed" in report["notes"]["sharpe_note"]
    assert "—" in report["markdown"]
    assert "17.64 percentage points" in report["markdown"]
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
