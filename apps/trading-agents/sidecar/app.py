"""FastAPI sidecar: health, a live TradingAgents stream, and the sample replay."""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
import traceback
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from providers import PROVIDERS
from runner import key_is_set

SIDECAR = Path(__file__).resolve().parent
load_dotenv(SIDECAR.parent / ".env", override=False)

SAMPLE_PATH = SIDECAR / "sample_run.json"
TICKER_RE_TEXT = r"^[A-Za-z0-9._\-\^=+]{1,32}$"

app = FastAPI(title="TradingAgents desk")
_run_lock = threading.Lock()


class RunIn(BaseModel):
    ticker: str = "NVDA"
    as_of: str
    provider: str = "xai"
    quick_model: str = "grok-4.6"
    deep_model: str = "grok-4.6"
    debate_rounds: int = Field(default=1, ge=1, le=3)
    mode: str = "auto"


def _sample() -> dict:
    return json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))


def _provider_payload() -> list[dict]:
    payload = []
    for provider_id, spec in PROVIDERS.items():
        payload.append(
            {
                "id": provider_id,
                "label": spec["label"],
                "env": spec["env"],
                "key_set": key_is_set(spec["env"]),
                "quick": [{"label": label, "id": model_id} for label, model_id in spec["quick"]],
                "deep": [{"label": label, "id": model_id} for label, model_id in spec["deep"]],
                "quick_default": spec["quick_default"],
                "deep_default": spec["deep_default"],
            }
        )
    return payload


@app.get("/api/health")
def health() -> dict:
    sample = _sample()
    return {
        "ok": True,
        "advice": "Research/simulation only, not financial advice.",
        "providers": _provider_payload(),
        "sample": {
            "ticker": sample["ticker"],
            "as_of": sample["as_of"],
            "label": sample["label"],
            "source": sample["source"],
        },
    }


def _prepare(body: RunIn) -> dict:
    if body.mode not in {"auto", "live", "replay"}:
        raise ValueError("Mode must be auto, live, or replay.")
    spec = PROVIDERS.get(body.provider)
    if spec is None:
        raise ValueError("Unknown provider.")
    quick_ids = {model_id for _, model_id in spec["quick"]}
    deep_ids = {model_id for _, model_id in spec["deep"]}
    if body.quick_model not in quick_ids or body.deep_model not in deep_ids:
        raise ValueError("That model is not in the catalog for the selected provider.")
    has_key = key_is_set(spec["env"])
    if body.mode == "live" and not has_key:
        raise ValueError(f"{spec['env']} is not set.")
    replay = body.mode == "replay" or (body.mode == "auto" and not has_key)
    ticker = body.ticker.strip().upper()
    as_of = body.as_of.strip()
    if not replay:
        import re

        if not re.fullmatch(TICKER_RE_TEXT, ticker):
            raise ValueError("Enter a Yahoo symbol such as NVDA, RELIANCE.NS, or ^NSEI.")
        try:
            parsed = date.fromisoformat(as_of)
        except ValueError as exc:
            raise ValueError("As-of date must be YYYY-MM-DD.") from exc
        if parsed > date.today():
            raise ValueError("As-of date cannot be in the future.")
    if replay and body.mode == "replay":
        reason = "You opened the shipped sample transcript."
    elif replay:
        reason = (
            f"{spec['env']} is not set, so this is the shipped sample instead of a live graph run."
        )
    else:
        reason = None
    return {
        "replay": replay,
        "reason": reason,
        "ticker": ticker,
        "as_of": as_of,
        "provider": body.provider,
        "quick_model": body.quick_model,
        "deep_model": body.deep_model,
        "debate_rounds": body.debate_rounds,
    }


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _meta(prepared: dict, sample: dict | None) -> dict:
    if prepared["replay"]:
        assert sample is not None
        return {
            "mode": "replay",
            "banner": sample["label"],
            "reason": prepared["reason"],
            "ticker": sample["ticker"],
            "as_of": sample["as_of"],
            "provider": sample["provider"],
            "quick_model": sample["quick_model"],
            "deep_model": sample["deep_model"],
            "debate_rounds": sample["debate_rounds"],
        }
    return {
        "mode": "live",
        "banner": None,
        "reason": None,
        "ticker": prepared["ticker"],
        "as_of": prepared["as_of"],
        "provider": prepared["provider"],
        "quick_model": prepared["quick_model"],
        "deep_model": prepared["deep_model"],
        "debate_rounds": prepared["debate_rounds"],
    }


def _iterate(prepared: dict):
    sample = _sample() if prepared["replay"] else None
    yield "meta", _meta(prepared, sample)
    if prepared["replay"]:
        assert sample is not None
        delay = float(os.environ.get("TRADING_AGENTS_REPLAY_DELAY", "0.75"))
        for event in sample["events"]:
            if delay > 0:
                time.sleep(delay)
            yield "stage", event
        yield "done", {"mode": "replay"}
        return

    from runner import live_events

    print(
        f"Live run {prepared['ticker']} {prepared['as_of']} "
        f"{prepared['provider']} {prepared['quick_model']}/{prepared['deep_model']} "
        f"rounds={prepared['debate_rounds']}",
        flush=True,
    )
    for event in live_events(
        prepared["ticker"],
        prepared["as_of"],
        prepared["provider"],
        prepared["quick_model"],
        prepared["deep_model"],
        prepared["debate_rounds"],
    ):
        print(f"stage {event['id']}", flush=True)
        yield "stage", event
    yield "done", {"mode": "live"}


@app.post("/api/run")
async def run(body: RunIn):
    try:
        prepared = _prepare(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not _run_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="A run is already in progress.")

    async def generate():
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def worker() -> None:
            try:
                for name, payload in _iterate(prepared):
                    loop.call_soon_threadsafe(queue.put_nowait, (name, payload))
            except Exception as exc:  # noqa: BLE001 — surface a single error event and keep the server up
                traceback.print_exc()
                message = str(exc).strip() or exc.__class__.__name__
                loop.call_soon_threadsafe(queue.put_nowait, ("error", {"message": message}))
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)
                _run_lock.release()

        threading.Thread(target=worker, daemon=True).start()
        yield ": stream-open\n\n"
        while True:
            item = await queue.get()
            if item is None:
                break
            name, payload = item
            yield _sse(name, payload)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
