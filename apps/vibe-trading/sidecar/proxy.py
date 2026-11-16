"""HTTP client for the local ``vibe-trading serve`` process.

The desk calls the four routes the backtest flow needs. Tests pass an
``httpx.Client`` backed by a mock transport, so nothing here opens a socket
on its own.
"""

from __future__ import annotations

import queue
import threading
from typing import Any, Iterator

import httpx

from events import TERMINAL_EVENTS, apply_event, empty_state, parse_sse
from results import resolve_result

_RETRY_PROMPT = (
    "The signal_engine.py you wrote returns a constant series, so the book is always long or always flat. "
    "The request was a rule that changes with the data. Rewrite code/signal_engine.py so the signal is not constant, "
    "then run the backtest again."
)

SERVE_URL = "http://127.0.0.1:8899"


class VibeClient:
    def __init__(self, base_url: str = SERVE_URL, client: httpx.Client | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = client

    def _http(self) -> httpx.Client:
        if self._client is None:
            timeout = httpx.Timeout(30.0, read=None)
            self._client = httpx.Client(base_url=self.base_url, timeout=timeout)
        return self._client

    def create_session(self, title: str = "Vibe Backtest desk") -> str:
        response = self._http().post("/sessions", json={"title": title})
        response.raise_for_status()
        body = response.json()
        session_id = body.get("session_id")
        if not isinstance(session_id, str) or not session_id:
            raise RuntimeError("Vibe-Trading did not return a session id.")
        return session_id

    def send_message(self, session_id: str, content: str) -> dict[str, Any]:
        response = self._http().post(f"/sessions/{session_id}/messages", json={"content": content})
        response.raise_for_status()
        body = response.json()
        return body if isinstance(body, dict) else {"body": body}

    def iter_events(
        self,
        session_id: str,
        opened: threading.Event | None = None,
    ) -> Iterator[tuple[str, dict[str, Any]]]:
        with self._http().stream(
            "GET",
            f"/sessions/{session_id}/events",
            params={"replay": "active"},
            headers={"Accept": "text/event-stream"},
        ) as response:
            response.raise_for_status()
            if opened is not None:
                opened.set()
            yield from parse_sse(response.iter_lines())

    def get_run(self, run_id: str) -> dict[str, Any]:
        response = self._http().get(f"/runs/{run_id}")
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            raise RuntimeError("Run payload was not an object.")
        return body

    def get_code(self, run_id: str) -> dict[str, Any]:
        response = self._http().get(f"/runs/{run_id}/code")
        if response.status_code == 404:
            return {}
        response.raise_for_status()
        body = response.json()
        return body if isinstance(body, dict) else {}


def _stream_attempt(
    client: VibeClient,
    session_id: str,
    content: str,
    holder: dict[str, Any],
) -> Iterator[tuple[str, dict[str, Any]]]:
    """Subscribe, send one message, and yield phase updates.

    ``holder`` receives ``state`` and ``error`` when the attempt ends. The
    stream is opened before the message so ``replay=active`` still has a buffer.
    """
    events: queue.Queue[tuple[str, dict[str, Any]] | None] = queue.Queue()
    started = threading.Event()
    errors: list[BaseException] = []

    def reader() -> None:
        try:
            for item in client.iter_events(session_id, opened=started):
                events.put(item)
                if item[0] in TERMINAL_EVENTS:
                    break
        except BaseException as exc:  # noqa: BLE001 — the desk turns this into one error event
            errors.append(exc)
        finally:
            started.set()
            events.put(None)

    thread = threading.Thread(target=reader, name="vibe-events", daemon=True)
    thread.start()
    if not started.wait(timeout=30):
        raise TimeoutError("The Vibe-Trading event stream did not open.")
    if errors:
        raise errors[0]

    client.send_message(session_id, content)
    state = empty_state()
    while True:
        item = events.get()
        if item is None:
            break
        event_type, data = item
        for phase in apply_event(state, event_type, data):
            yield "phase", phase
        if state["terminal"]:
            break
    thread.join(timeout=5)
    holder["state"] = state
    holder["error"] = errors[0] if errors else None


def _result_from_state(
    client: VibeClient,
    state: dict[str, Any],
    prompt: str,
    *,
    retried: bool = False,
) -> dict[str, Any]:
    if state.get("error"):
        raise RuntimeError(str(state["error"]))
    run_id = state.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise RuntimeError("The session ended without a backtest run id.")
    payload = client.get_run(run_id)
    code = client.get_code(run_id)
    if isinstance(payload, dict):
        payload = dict(payload)
        payload["prompt"] = prompt
    return resolve_result(payload, code, retried=retried)


def drive_live(client: VibeClient, prompt: str) -> Iterator[tuple[str, dict[str, Any]]]:
    """Open the event stream, send the prompt, then load the finished run.

    A constant signal under a rule-based prompt is sent back once. The second
    result is the one shown, including its warning when the signal stays constant.
    """
    session_id = client.create_session()
    holder: dict[str, Any] = {}
    yield from _stream_attempt(client, session_id, prompt, holder)
    state = holder.get("state") or {}
    if holder.get("error") and not state.get("terminal"):
        raise holder["error"]
    result = _result_from_state(client, state, prompt)
    if result.get("strategy_warning"):
        yield (
            "phase",
            {
                "id": "code",
                "title": "Code",
                "status": "working",
                "body": "The signal was constant. Asking for one rewrite.",
            },
        )
        second: dict[str, Any] = {}
        try:
            yield from _stream_attempt(client, session_id, _RETRY_PROMPT, second)
            follow = second.get("state") or {}
            if second.get("error") and not follow.get("terminal"):
                raise second["error"]
            result = _result_from_state(client, follow, prompt, retried=True)
        except Exception:
            warning = str(result.get("strategy_warning") or "")
            result["strategy_warning"] = (
                f"{warning} Generation was retried once and did not finish."
            ).strip()
            notes = (result.get("report") or {}).get("notes")
            if isinstance(notes, dict):
                notes["strategy_warning"] = result["strategy_warning"]
    yield "result", result
