"""One-shot HTTP GET used by the India fetchers. No retries."""

from __future__ import annotations

import http.cookiejar
import urllib.error
import urllib.request
from dataclasses import dataclass

BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)


@dataclass
class HttpResult:
    status: int
    body: bytes
    error: str | None = None
    blocked: bool = False
    url: str = ""


def build_opener() -> urllib.request.OpenerDirector:
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def http_get(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 20,
    opener: urllib.request.OpenerDirector | None = None,
) -> HttpResult:
    """GET ``url`` once. 401, 403, and 429 come back as ``blocked`` with no second try."""

    request_headers = {"User-Agent": BROWSER_UA, "Accept": "*/*"}
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(url, headers=request_headers)
    try:
        open_fn = opener.open if opener is not None else urllib.request.urlopen
        with open_fn(request, timeout=timeout) as response:
            return HttpResult(status=getattr(response, "status", 200), body=response.read(), url=url)
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read() or b""
        except Exception:
            body = b""
        return HttpResult(
            status=exc.code,
            body=body,
            error=f"HTTP {exc.code}",
            blocked=exc.code in {401, 403, 429},
            url=url,
        )
    except Exception as exc:
        return HttpResult(status=0, body=b"", error=f"{exc.__class__.__name__}: {exc}", url=url)


def timed_out(result: HttpResult) -> bool:
    if result.status != 0 or not result.error:
        return False
    text = result.error.lower()
    return "timed out" in text or "timeout" in text or isinstance(result.error, socket.timeout)
