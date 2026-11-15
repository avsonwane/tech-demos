from results import parse_run


def _payload() -> dict:
    return {
        "status": "success",
        "run_id": "run-1",
        "metrics": {
            "final_value": "118",
            "total_return": "0.18",
            "annual_return": "0.18",
            "sharpe": "0.9",
            "max_drawdown": "-0.0268",
            "win_rate": "0.5",
            "trade_count": "2",
        },
        "run_card": {
            "data_sources": ["yahoo"],
            "backtest": {
                "codes": ["AAPL"],
                "start_date": "2024-01-02",
                "end_date": "2024-12-31",
                "source": "auto",
            },
        },
        "artifacts_equity_csv": [
            {
                "timestamp": "2024-01-02",
                "equity": "100",
                "drawdown": "0",
                "benchmark_equity": "100",
            },
            {
                "timestamp": "2024-12-31",
                "equity": "118",
                "drawdown": "0",
                "benchmark_equity": "107",
            },
        ],
        "equity_curve": [
            {"time": "2024-01-02", "equity": "100", "drawdown": "0"},
        ],
        "artifacts_trades_csv": [
            {
                "timestamp": "2024-02-01",
                "code": "AAPL",
                "side": "buy",
                "price": "100",
                "qty": "10",
                "pnl": "0",
                "event": "entry",
            }
        ],
    }


def test_parse_run_prefers_full_equity_rows_and_the_run_card():
    result = parse_run(_payload(), {"signal_engine.py": "class SignalEngine:\n    pass\n"})
    assert result["illustrative"] is False
    assert result["codes"] == ["AAPL"]
    assert result["sources"] == ["yahoo"]
    assert result["start_date"] == "2024-01-02"
    assert result["end_date"] == "2024-12-31"
    assert result["equity"][0]["benchmark"] == 100
    assert result["equity"][1]["equity"] == 118
    assert len(result["equity"]) == 2
    assert result["metrics"]["total_return"] == 0.18
    assert result["metrics"]["cagr"] == 0.18
    assert result["metrics"]["sharpe"] == 0.9
    assert result["metrics"]["max_drawdown"] == -0.0268
    assert result["metrics"]["win_rate"] == 0.5
    assert result["metrics"]["fees_reported"] is False
    assert result["metrics"]["fees"] is None
    assert result["trades"][0]["side"] == "buy"
    assert result["code"].startswith("class SignalEngine")


def test_fee_field_and_trade_fee_column():
    payload = _payload()
    payload["metrics"]["total_commission"] = "4.5"
    parsed = parse_run(payload, {})
    assert parsed["metrics"]["fees"] == 4.5
    assert parsed["metrics"]["fees_reported"] is True

    payload["metrics"].pop("total_commission")
    payload["artifacts_trades_csv"][0]["fee"] = "1.25"
    payload["artifacts_trades_csv"].append({"timestamp": "2024-06-03", "code": "AAPL", "fee": "2.75"})
    summed = parse_run(payload, {})
    assert summed["metrics"]["fees"] == 4.0


def test_missing_code_is_an_empty_string():
    assert parse_run(_payload(), {})["code"] == ""
    assert parse_run(_payload(), None)["code"] == ""
