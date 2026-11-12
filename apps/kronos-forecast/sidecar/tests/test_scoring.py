from scoring import score_holdout, summarize


def test_summary_direction_and_spread():
    summary = summarize(100.0, [101.0, 110.0], [[108.0, 108.0], [110.0, 110.0], [112.0, 112.0]])
    assert summary["direction"] == "up"
    assert summary["medianChangePct"] == 10.0
    assert "up 10.00%" in summary["text"]
    assert summary["spreadPct"] > 0


def test_flat_summary_uses_small_move():
    summary = summarize(100.0, [100.01], [[100.0], [100.02]])
    assert summary["direction"] == "flat"
    assert "about flat" in summary["text"]


def test_holdout_hits_and_mape():
    score = score_holdout(100.0, [110.0, 90.0], [120.0, 80.0])
    assert score["directionHits"] == 2
    assert score["directionTotal"] == 2
    # mean of |110-120|/120 and |90-80|/80 = 10.4167%
    assert abs(score["mapePct"] - 10.4167) < 0.01


def test_holdout_counts_a_miss():
    score = score_holdout(100.0, [110.0], [90.0])
    assert score["directionHits"] == 0
    assert "0 of 1" in score["text"]
