"""FastAPI desk: health, sample replay, and a proxied Vibe-Trading session."""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import urllib.error
import urllib.request
import sys
import threading
import time
import traceback
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from providers import (
    PROVIDERS,
    anthropic_choices,
    default_model,
    key_is_set,
    preferred_provider,
    provider_child_env,
    resolve_model,
)
from tickers import data_error_message, empty_price_message, missing_symbol, ticker_error

SIDECAR = Path(__file__).resolve().parent
load_dotenv(SIDECAR.parent / ".env", override=False)

SAMPLE_PATH = SIDECAR / "sample_run.json"
RUN_DATA = SIDECAR / ".run-data"


def _env_port(*names: str, default: int) -> int:
    for name in names:
        raw = os.environ.get(name, "").strip()
        if not raw:
            continue
        try:
            value = int(raw)
        except ValueError as exc:
            raise RuntimeError(f"{name} must be a TCP port. Got {raw}.") from exc
        if value < 1 or value > 65535:
            raise RuntimeError(f"{name} must be a TCP port. Got {raw}.")
        return value
    return default


SERVE_PORT = _env_port("VIBE_PORT", "VIBE_SERVE_PORT", default=8899)
SERVE_URL = f"http://127.0.0.1:{SERVE_PORT}"

PRESETS = [
    {
        "id": "aapl",
        "label": "AAPL 20/50",
        "prompt": "Backtest a 20/50 SMA crossover on AAPL for 2024 vs buy-and-hold, report max drawdown",
    },
    {
        "id": "btc",
        "label": "BTC-USDT",
        "prompt": "Backtest a BTC-USDT 20/50 moving-average crossover for 2024. Compare it with buy-and-hold and report maximum drawdown.",
    },
    {
        "id": "reliance",
        "label": "RELIANCE.NS",
        "prompt": "Backtest a 20/50 SMA crossover on RELIANCE.NS for 2024 vs buy-and-hold, report max drawdown",
    },
]

_run_lock = threading.Lock()
_serve_lock = threading.Lock()
_serve_proc: subprocess.Popen[bytes] | None = None
_serve_provider: str | None = None
_serve_error: str | None = None


class RunIn(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000)
    provider: str = "xai"
    mode: str = "auto"
    model: str = ""


def _sample() -> dict[str, Any]:
    return json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))


def _replay_result() -> dict[str, Any]:
    """Replay the saved RELIANCE layout: SMA headline, buy-and-hold benchmark."""
    from results import resolve_result

    fixture = SIDECAR / "fixtures" / "reliance_sma"
    resolved = resolve_result(
        {
            "run_id": "20261115_125847_46_bb8d5a",
            "status": "illustrative",
            "run_directory": str(fixture),
        }
    )
    resolved["illustrative"] = True
    resolved["status"] = "illustrative"
    return resolved


def _provider_payload() -> list[dict[str, Any]]:
    payload = []
    for provider_id, spec in PROVIDERS.items():
        payload.append(
            {
                "id": provider_id,
                "label": spec["label"],
                "env": spec["env"],
                "key_set": key_is_set(spec["env"]),
                "model": default_model(provider_id),
                "models": anthropic_choices() if provider_id == "anthropic" else [],
                "note": spec["note"],
            }
        )
    return payload


def serve_running() -> bool:
    return _serve_proc is not None and _serve_proc.poll() is None


def stop_serve() -> None:
    global _serve_proc, _serve_provider
    proc = _serve_proc
    _serve_proc = None
    _serve_provider = None
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()


def serve_http_ready(base_url: str = SERVE_URL) -> bool:
    """Readiness uses ``GET /health``. ``GET /`` 404s: the package has no web UI."""
    try:
        with urllib.request.urlopen(f"{base_url.rstrip('/')}/health", timeout=0.4) as response:
            return 200 <= response.status < 300
    except (OSError, urllib.error.URLError, TimeoutError):
        return False


def port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, port)) == 0


def port_busy_message(port: int, label: str) -> str:
    return (
        f"{label} port {port} is already in use. "
        f"Free it with: lsof -ti tcp:{port} | xargs kill"
    )


def _wait_for_port(proc: subprocess.Popen[bytes], timeout: float = 90) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(
                f"vibe-trading serve exited ({proc.returncode}). "
                f"{port_busy_message(SERVE_PORT, 'Vibe-Trading')}"
            )
        if serve_http_ready():
            return
        time.sleep(0.3)
    raise RuntimeError(port_busy_message(SERVE_PORT, "Vibe-Trading"))


def ensure_serve(provider_id: str, model: str | None = None) -> None:
    """Start or restart ``vibe-trading serve`` with this provider's child env."""
    global _serve_proc, _serve_provider, _serve_error
    chosen = model or default_model(provider_id)
    identity = f"{provider_id}:{chosen}"
    with _serve_lock:
        if serve_running() and _serve_provider == identity:
            return
        stop_serve()
        if port_in_use(SERVE_PORT):
            raise RuntimeError(port_busy_message(SERVE_PORT, "Vibe-Trading"))
        RUN_DATA.mkdir(parents=True, exist_ok=True)
        env = provider_child_env(provider_id, model=chosen)
        env["VIBE_TRADING_HOME"] = str(RUN_DATA)
        env["PYTHONUNBUFFERED"] = "1"
        env["VIBE_PORT"] = str(SERVE_PORT)
        env["VIBE_SERVE_PORT"] = str(SERVE_PORT)
        log_handle = (RUN_DATA / "serve.log").open("ab")
        proc = subprocess.Popen(
            [sys.executable, str(SIDECAR / "launch_serve.py")],
            cwd=str(SIDECAR),
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
        )
        _serve_proc = proc
        _serve_provider = identity
        try:
            _wait_for_port(proc)
        except Exception as exc:
            _serve_error = str(exc)
            stop_serve()
            raise
        _serve_error = None


def _autostart() -> None:
    global _serve_error
    try:
        ensure_serve(preferred_provider())
    except Exception as exc:  # noqa: BLE001 — replay must keep working if serve fails
        _serve_error = str(exc)


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    if os.environ.get("VIBE_DESK_AUTOSTART") == "1":
        threading.Thread(target=_autostart, name="vibe-serve", daemon=True).start()
    yield
    stop_serve()


app = FastAPI(title="Vibe Backtest desk", lifespan=_lifespan)


@app.get("/api/health")
def health() -> dict[str, Any]:
    sample = _sample()
    return {
        "ok": True,
        "advice": "Research/simulation only, not financial advice.",
        "providers": _provider_payload(),
        "presets": PRESETS,
        "nse": {"accepted": True, "market": "india_equity", "example": "RELIANCE.NS"},
        "sample": {"label": sample["label"], "source": sample["source"]},
        "serve": {"running": serve_running(), "error": _serve_error},
    }


def _prepare(body: RunIn) -> dict[str, Any]:
    if body.mode not in {"auto", "live", "replay"}:
        raise ValueError("Mode must be auto, live, or replay.")
    spec = PROVIDERS.get(body.provider)
    if spec is None:
        raise ValueError("Unknown provider.")
    prompt = body.prompt.strip()
    if not prompt:
        raise ValueError("Enter a strategy prompt.")
    if body.mode != "replay":
        missing = missing_symbol(prompt)
        if missing:
            raise ValueError(ticker_error(missing))
    model = resolve_model(body.provider, body.model)
    has_key = key_is_set(spec["env"])
    if body.mode == "live" and not has_key:
        raise ValueError(f"{spec['env']} is not set.")
    replay = body.mode == "replay" or (body.mode == "auto" and not has_key)
    if replay and body.mode == "replay":
        reason = "You opened the shipped sample run."
    elif replay:
        reason = f"{spec['env']} is not set, so this is the shipped sample instead of a live session."
    else:
        reason = None
    return {
        "replay": replay,
        "reason": reason,
        "prompt": prompt,
        "provider": body.provider,
        "model": model,
    }


def _sse(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _meta(prepared: dict[str, Any], sample: dict[str, Any] | None) -> dict[str, Any]:
    if prepared["replay"]:
        assert sample is not None
        return {
            "mode": "replay",
            "banner": sample["label"],
            "reason": prepared["reason"],
            "provider": "sample",
            "model": "illustrative",
            "prompt": sample["prompt"],
        }
    return {
        "mode": "live",
        "banner": None,
        "reason": None,
        "provider": prepared["provider"],
        "model": prepared["model"],
        "prompt": prepared["prompt"],
    }


def _iterate(prepared: dict[str, Any]):
    sample = _sample() if prepared["replay"] else None
    yield "meta", _meta(prepared, sample)
    if prepared["replay"]:
        assert sample is not None
        delay = float(os.environ.get("VIBE_DESK_REPLAY_DELAY", "0.45"))
        for phase in sample["phases"]:
            if delay > 0:
                time.sleep(delay)
            yield "phase", phase
        if delay > 0:
            time.sleep(delay)
        yield "result", _replay_result()
        yield "done", {"mode": "replay"}
        return

    ensure_serve(prepared["provider"], prepared["model"])
    from proxy import VibeClient, drive_live

    client = VibeClient(SERVE_URL)
    try:
        for name, payload in drive_live(client, prepared["prompt"]):
            if name == "result":
                empty = empty_price_message(prepared["prompt"], payload)
                if empty:
                    raise RuntimeError(empty)
            yield name, payload
    except Exception as exc:
        rewritten = data_error_message(prepared["prompt"], str(exc))
        if rewritten and rewritten != str(exc):
            raise RuntimeError(rewritten) from exc
        raise
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
        events: asyncio.Queue = asyncio.Queue()

        def worker() -> None:
            try:
                for name, payload in _iterate(prepared):
                    loop.call_soon_threadsafe(events.put_nowait, (name, payload))
            except Exception as exc:  # noqa: BLE001 — one error event, then the server stays up
                traceback.print_exc()
                message = str(exc).strip() or exc.__class__.__name__
                loop.call_soon_threadsafe(events.put_nowait, ("error", {"message": message}))
            finally:
                loop.call_soon_threadsafe(events.put_nowait, None)
                _run_lock.release()

        threading.Thread(target=worker, daemon=True).start()
        yield ": stream-open\n\n"
        while True:
            item = await events.get()
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
