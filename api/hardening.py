"""Things a public site needs and a local one does not: a rate limit and a background warm-up."""
from __future__ import annotations

import logging
import threading
import time
from collections import deque

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

log = logging.getLogger("api.hardening")


class RateLimiter:
    """Sliding window: at most `limit` calls per `window` seconds for each key (for example an IP address)."""

    def __init__(self, limit: int, window: float = 60.0, clock=time.monotonic):
        if limit < 1 or window <= 0:
            raise ValueError("limit must be >= 1 and window > 0")
        self.limit, self.window, self._clock = limit, window, clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> float:
        """Returns 0 if the call is allowed, otherwise the number of seconds to wait."""
        now = self._clock()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return self.window - (now - hits[0])
            hits.append(now)
            if len(self._hits) > 10_000:   # forget idle keys, so the table cannot grow without bound
                for k in [k for k, v in self._hits.items() if not v or now - v[-1] >= self.window]:
                    del self._hits[k]
            return 0.0


def client_key(request: Request, proxy_hops: int) -> str:
    """The address to rate-limit by.

    Behind a proxy every request seems to come from the proxy, so we read X-Forwarded-For. Each proxy
    APPENDS the address it saw, so the client-supplied part is at the front and cannot be trusted: with
    `proxy_hops` trusted proxies in front of us, the real client is the entry that many places from the end.
    With proxy_hops = 0 the header is ignored (anyone could fake it).
    """
    if proxy_hops > 0:
        parts = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
        if len(parts) >= proxy_hops:
            return parts[-proxy_hops]
    return request.client.host if request.client else "unknown"


def add_rate_limit(app: FastAPI, per_minute: int, proxy_hops: int = 0, clock=time.monotonic) -> RateLimiter:
    limiter = RateLimiter(per_minute, 60.0, clock)

    @app.middleware("http")
    async def rate_limit(request: Request, call_next):
        # The page itself and the health check are free; only the work-doing API is limited.
        if request.url.path.startswith("/api/") and request.url.path != "/api/health":
            wait = limiter.check(client_key(request, proxy_hops))
            if wait > 0:
                return JSONResponse({"detail": "Too many requests. Please wait a moment and try again."},
                                    status_code=429, headers={"Retry-After": str(int(wait) + 1)})
        return await call_next(request)

    return limiter


def warm_up(registry, names: list[str]) -> threading.Thread:
    """Load tokenizers in the background so the first visitor does not wait for the downloads."""
    def work():
        for name in names:
            try:
                registry.get(name)
                log.info("warmed up %s", name)
            except Exception as exc:   # a gated model without a token must not stop the server
                log.warning("warm-up of %s failed: %s", name, str(exc)[:200])

    thread = threading.Thread(target=work, name="warm-up", daemon=True)
    thread.start()
    return thread
