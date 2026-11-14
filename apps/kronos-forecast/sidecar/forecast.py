"""Kronos-mini fan forecasts. Weights download into sidecar/.cache on first use."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from market import future_timestamps
from scoring import score_holdout, summarize

VENDOR = Path(__file__).resolve().parent / "vendor"
if str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))

from model import Kronos, KronosPredictor, KronosTokenizer  # noqa: E402
from model.kronos import calc_time_stamps  # noqa: E402

LOOKBACK = 400
MIN_LOOKBACK = 128
MODEL_ID = "NeoQuasar/Kronos-mini"
TOKENIZER_ID = "NeoQuasar/Kronos-Tokenizer-2k"
PRICE_COLS = ["open", "high", "low", "close"]

_predictor: KronosPredictor | None = None


def load_predictor() -> KronosPredictor:
    global _predictor
    if _predictor is None:
        import torch

        torch.set_num_threads(4)
        print(f"Loading {MODEL_ID} on CPU...", flush=True)
        started = time.time()
        tokenizer = KronosTokenizer.from_pretrained(TOKENIZER_ID)
        model = Kronos.from_pretrained(MODEL_ID)
        tokenizer.eval()
        model.eval()
        _predictor = KronosPredictor(model, tokenizer, device="cpu", max_context=512)
        print(f"Model ready in {time.time() - started:.1f}s", flush=True)
    return _predictor


def run_forecast(
    frame: pd.DataFrame,
    timeframe: str,
    pred_len: int,
    sample_count: int,
    y_timestamp: pd.Series | None = None,
) -> dict:
    if len(frame) < MIN_LOOKBACK:
        raise ValueError(f"Need at least {MIN_LOOKBACK} closed candles, got {len(frame)}.")
    predictor = load_predictor()
    history = frame.iloc[-LOOKBACK:].reset_index(drop=True)
    x_timestamp = pd.Series(pd.to_datetime(history["timestamp"], utc=True))
    if y_timestamp is None:
        future = future_timestamps(x_timestamp, pred_len, timeframe)
        y_timestamp = pd.Series(future)
    else:
        y_timestamp = pd.Series(pd.to_datetime(y_timestamp, utc=True)).reset_index(drop=True)
    if len(y_timestamp) != pred_len:
        raise ValueError(f"Expected {pred_len} forecast timestamps, got {len(y_timestamp)}.")

    started = time.time()
    samples = _predict_paths(predictor, history, x_timestamp, y_timestamp, pred_len, sample_count)
    elapsed = time.time() - started
    if not np.isfinite(samples).all():
        raise ValueError("Kronos returned a non-finite sample.")

    samples[:, :, :4] = np.maximum(samples[:, :, :4], 1e-8)
    path_closes = [[float(value) for value in samples[index, :, 3]] for index in range(samples.shape[0])]
    median = np.median(samples, axis=0)
    median_bars = []
    for step in range(pred_len):
        open_, high, low, close = (float(median[step, i]) for i in range(4))
        high = max(open_, high, low, close)
        low = min(open_, high, low, close)
        median_bars.append(
            {
                "time": int(pd.Timestamp(y_timestamp.iloc[step]).timestamp()),
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
            }
        )
    last_close = float(history.iloc[-1]["close"])
    summary = summarize(last_close, [bar["close"] for bar in median_bars], path_closes)
    print(
        f"sampled {sample_count} paths x {pred_len} bars from {len(history)} candles in {elapsed:.1f}s",
        flush=True,
    )
    return {
        "history": _bars(history),
        "forecastTimes": [bar["time"] for bar in median_bars],
        "paths": [{"close": closes} for closes in path_closes],
        "median": median_bars,
        "summary": summary,
        "elapsedSeconds": round(elapsed, 2),
        "lastClose": last_close,
    }


def score_against(result: dict, actual: pd.DataFrame) -> dict:
    actual_bars = _bars(actual)
    if len(actual_bars) != len(result["median"]):
        raise ValueError("Actual window does not match the forecast length.")
    score = score_holdout(
        result["lastClose"],
        [bar["close"] for bar in result["median"]],
        [bar["close"] for bar in actual_bars],
    )
    return {"actuals": actual_bars, "score": score}


def _predict_paths(predictor, history, x_timestamp, y_timestamp, pred_len: int, sample_count: int) -> np.ndarray:
    work = history.copy()
    if "volume" not in work.columns:
        work["volume"] = 0.0
        work["amount"] = 0.0
    if "amount" not in work.columns:
        work["amount"] = work["volume"] * work[PRICE_COLS].mean(axis=1)
    values = work[PRICE_COLS + ["volume", "amount"]].astype(np.float32).to_numpy()
    if np.isnan(values).any():
        raise ValueError("Candle history contains NaN values.")

    x_stamp = calc_time_stamps(x_timestamp).to_numpy(dtype=np.float32)
    y_stamp = calc_time_stamps(y_timestamp).to_numpy(dtype=np.float32)
    mean = values.mean(axis=0)
    std = values.std(axis=0)
    normalized = np.clip((values - mean) / (std + 1e-5), -predictor.clip, predictor.clip)

    preds = predictor.generate(
        normalized[np.newaxis, :],
        x_stamp[np.newaxis, :],
        y_stamp[np.newaxis, :],
        pred_len,
        1.0,
        0,
        0.9,
        sample_count,
        False,
        True,
    )
    # (batch, samples, pred_len, features)
    paths = preds[0] * (std + 1e-5) + mean
    return paths


def _bars(frame: pd.DataFrame) -> list[dict]:
    rows = []
    for record in frame.itertuples(index=False):
        rows.append(
            {
                "time": int(pd.Timestamp(record.timestamp).timestamp()),
                "open": float(record.open),
                "high": float(record.high),
                "low": float(record.low),
                "close": float(record.close),
            }
        )
    return rows
