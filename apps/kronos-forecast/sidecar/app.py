"""FastAPI sidecar: free candles in, Kronos-mini forecast fan out."""

from __future__ import annotations

import asyncio
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from forecast import LOOKBACK, MIN_LOOKBACK, run_forecast, score_against
from market import TIMEFRAMES, MarketError, fetch_ohlcv

DISCLAIMER = "Not financial advice."
_state = {"ready": False, "error": None}
_lock = threading.Lock()


def _load_model() -> None:
    try:
        from forecast import load_predictor

        load_predictor()
        _state["ready"] = True
    except Exception as exc:
        _state["error"] = str(exc)
        print(f"Model load failed: {exc}", flush=True)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    threading.Thread(target=_load_model, daemon=True).start()
    yield


app = FastAPI(title="Kronos forecast", lifespan=lifespan)


class ForecastRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    timeframe: str
    horizon: int = Field(default=24, ge=4, le=48)
    samples: int = Field(default=8, ge=4, le=16)
    mode: str = "forecast"
    holdout: int = Field(default=12, ge=4, le=48)


@app.get("/api/health")
def health() -> dict:
    return {
        "ready": _state["ready"],
        "error": _state["error"],
        "model": "NeoQuasar/Kronos-mini",
        "disclaimer": DISCLAIMER,
    }


@app.post("/api/forecast")
async def forecast(request: ForecastRequest) -> dict:
    if _state["error"]:
        raise HTTPException(status_code=500, detail=_state["error"])
    if not _state["ready"]:
        raise HTTPException(status_code=503, detail="Kronos-mini is still loading.")
    if request.timeframe not in TIMEFRAMES:
        raise HTTPException(status_code=400, detail="Timeframe must be 15m, 1h, 4h, or 1d.")
    if request.mode not in ("forecast", "test"):
        raise HTTPException(status_code=400, detail="Mode must be forecast or test.")
    if not _lock.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="A forecast is already running.")
    try:
        return await asyncio.to_thread(_forecast_sync, request)
    except MarketError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        _lock.release()


def _forecast_sync(request: ForecastRequest) -> dict:
    symbol = request.symbol.strip().upper()
    holdout = request.holdout if request.mode == "test" else 0
    limit = min(1000, LOOKBACK + holdout + 30)
    frame = fetch_ohlcv(symbol, request.timeframe, limit)
    if request.mode == "test":
        if len(frame) < MIN_LOOKBACK + request.holdout:
            raise ValueError(
                f"Need at least {MIN_LOOKBACK + request.holdout} candles for a {request.holdout}-bar test, got {len(frame)}."
            )
        visible = frame.iloc[:-request.holdout].reset_index(drop=True)
        actual = frame.iloc[-request.holdout:].reset_index(drop=True)
        result = run_forecast(
            visible,
            request.timeframe,
            request.holdout,
            request.samples,
            y_timestamp=actual["timestamp"],
        )
        judged = score_against(result, actual)
        actuals = judged["actuals"]
        score = judged["score"]
        mode = "test"
    else:
        result = run_forecast(frame, request.timeframe, request.horizon, request.samples)
        actuals = None
        score = None
        mode = "forecast"

    return {
        "symbol": symbol,
        "timeframe": request.timeframe,
        "mode": mode,
        "model": "NeoQuasar/Kronos-mini",
        "history": result["history"],
        "forecastTimes": result["forecastTimes"],
        "paths": result["paths"],
        "median": result["median"],
        "summary": result["summary"],
        "actuals": actuals,
        "score": score,
        "elapsedSeconds": result["elapsedSeconds"],
        "disclaimer": DISCLAIMER,
    }
