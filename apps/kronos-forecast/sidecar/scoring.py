"""Plain-language forecast summary and holdout score. No model imports."""

from __future__ import annotations

import numpy as np

FLAT_PCT = 0.05


def _sign(delta: float) -> int:
    if delta > 0:
        return 1
    if delta < 0:
        return -1
    return 0


def direction_word(change_pct: float) -> str:
    if abs(change_pct) < FLAT_PCT:
        return "flat"
    if change_pct > 0:
        return "up"
    return "down"


def summarize(last_close: float, median_closes: list[float], path_closes: list[list[float]]) -> dict:
    if last_close == 0:
        raise ValueError("last close is zero")
    if not median_closes or not path_closes:
        raise ValueError("forecast is empty")

    end = float(median_closes[-1])
    change_pct = (end - last_close) / last_close * 100.0
    finals = [float(path[-1]) for path in path_closes]
    lo = float(np.percentile(finals, 10))
    hi = float(np.percentile(finals, 90))
    spread_pct = (hi - lo) / abs(last_close) * 100.0
    word = direction_word(change_pct)
    if word == "flat":
        move = f"about flat ({change_pct:+.2f}%)"
    else:
        move = f"{word} {abs(change_pct):.2f}%"
    text = (
        f"The median path ends {move} versus the last close. "
        f"The fan's horizon closes, from the 10th to the 90th percentile, "
        f"span about {spread_pct:.2f}% of price."
    )
    return {
        "direction": word,
        "medianChangePct": round(change_pct, 4),
        "spreadPct": round(spread_pct, 4),
        "text": text,
    }


def score_holdout(last_close: float, median_closes: list[float], actual_closes: list[float]) -> dict:
    if len(median_closes) != len(actual_closes) or not actual_closes:
        raise ValueError("median and actual closes must be the same non-empty length")
    if last_close == 0:
        raise ValueError("last close is zero")

    hits = 0
    prev_pred = last_close
    prev_actual = last_close
    abs_pct: list[float] = []
    for pred, actual in zip(median_closes, actual_closes):
        if _sign(pred - prev_pred) == _sign(actual - prev_actual):
            hits += 1
        if actual != 0:
            abs_pct.append(abs(pred - actual) / abs(actual))
        prev_pred = pred
        prev_actual = actual

    total = len(actual_closes)
    mape = (sum(abs_pct) / len(abs_pct)) * 100.0 if abs_pct else 0.0
    text = (
        f"On the hidden window the median path matched the actual up/down step "
        f"{hits} of {total} times. Close MAPE is {mape:.2f}%."
    )
    return {
        "directionHits": hits,
        "directionTotal": total,
        "mapePct": round(mape, 4),
        "text": text,
    }
