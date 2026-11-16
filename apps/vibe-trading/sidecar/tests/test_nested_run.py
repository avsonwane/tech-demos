import json
from pathlib import Path

import pytest

from results import resolve_result

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "reliance_sma"


def _parent_payload() -> dict:
    """What GET /runs returns for the run root: the buy-and-hold comparison."""
    return {
        "run_id": "20261115_125847_46_bb8d5a",
        "status": "success",
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
        "artifacts_equity_csv": [
            {"timestamp": "2024-01-02", "equity": "100", "drawdown": "0"},
            {"timestamp": "2024-12-31", "equity": "93.96", "drawdown": "-0.0604"},
        ],
        "artifacts_trades_csv": [
            {"timestamp": "2024-01-02", "code": "RELIANCE.NS", "side": "buy", "price": "100", "qty": "1"}
        ],
    }


def test_nested_sma_is_the_headline_and_buy_and_hold_is_the_benchmark():
    parent_code = {"signal_engine.py": (FIXTURE / "code" / "signal_engine.py").read_text(encoding="utf-8")}
    result = resolve_result(_parent_payload(), parent_code)
    assert result["strategy_label"] == "20/50 SMA"
    assert result["benchmark_label"] == "Buy & hold"
    assert result["run_id"] == "20261115_125847_46_bb8d5a"
    assert result["codes"] == ["RELIANCE.NS"]
    assert result["sources"] == ["Yahoo Finance (yfinance)"]
    assert result["start_date"] == "2024-01-01"
    assert result["end_date"] == "2024-12-31"
    assert result["metrics"]["total_return"] == 0.116
    assert result["metrics"]["cagr"] == 0.116
    assert result["metrics"]["sharpe"] == 0.8
    assert result["metrics"]["max_drawdown"] == -0.0959
    assert result["metrics"]["fees"] == 7355
    assert result["metrics"]["fees_reported"] is True
    assert result["metrics"]["benchmark_return"] == pytest.approx(-0.0713544263228375)
    assert result["metrics"]["fees"] != 99
    assert len(result["trades"]) == 3
    assert result["equity"][-1]["equity"] == 111.6
    assert result["equity"][-1]["benchmark"] == pytest.approx(92.86455736771624)
    assert result["equity"][0]["benchmark"] == pytest.approx(100.08887628832035)
    assert "rolling(20)" in result["code"]
    assert "rolling(50)" in result["code"]
    assert "Buy and hold" not in result["code"]


def test_fills_sum_when_the_metrics_file_has_no_fee_total(tmp_path: Path):
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    (artifacts / "metrics.csv").write_text(
        "total_return,annual_return,sharpe,max_drawdown,win_rate\n0.1,0.1,1,0,1\n",
        encoding="utf-8",
    )
    (artifacts / "equity.csv").write_text(
        "timestamp,equity,drawdown\n2024-01-02,100,0\n",
        encoding="utf-8",
    )
    (artifacts / "trades.csv").write_text(
        "timestamp,code,side,price,qty,pnl,event\n2024-01-02,AAPL,buy,1,1,0,entry\n",
        encoding="utf-8",
    )
    (artifacts / "fills.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"fee": 1.5}),
                json.dumps({"commission": 2.25}),
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "run_card.json").write_text(
        json.dumps({"data_sources": ["yahoo"], "backtest": {"codes": ["AAPL"]}}),
        encoding="utf-8",
    )
    result = resolve_result(
        {
            "run_id": "flat",
            "status": "success",
            "run_directory": str(tmp_path),
            "metrics": {"total_return": 0.1, "annual_return": 0.1, "sharpe": 1, "max_drawdown": 0, "win_rate": 1},
            "run_card": {"data_sources": ["yahoo"], "backtest": {"codes": ["AAPL"]}},
            "artifacts_equity_csv": [{"timestamp": "2024-01-02", "equity": "100", "drawdown": "0"}],
            "artifacts_trades_csv": [],
        }
    )
    assert result["metrics"]["fees"] == 3.75
    assert result["metrics"]["fees_reported"] is True
    assert result["strategy_label"] is None
    assert result["benchmark_label"] is None
