"""Lightweight per-IP sliding-window rate limiter and security headers middleware."""

from __future__ import annotations

import collections
import time
from typing import Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

_RATE_LIMITED_PREFIXES = (
    "/api/v1/daily",
    "/api/v1/checkin",
    "/api/v1/examen",
    "/api/v1/confession-prep",
    "/api/v1/lectio",
    "/api/v1/audio/voice-note",
)


class SecurityAndRateLimitMiddleware(BaseHTTPMiddleware):
    """Protects LLM & TTS endpoints from burst abuse and adds standard HTTP security headers."""

    def __init__(
        self,
        app,
        *,
        requests_per_minute: int = 30,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(app)
        self.requests_per_minute = max(0, requests_per_minute)
        self.clock = clock
        self._buckets: dict[str, collections.deque[float]] = collections.defaultdict(
            collections.deque
        )

    def _is_limited_path(self, path: str) -> bool:
        return any(path.startswith(prefix) for prefix in _RATE_LIMITED_PREFIXES)

    async def dispatch(self, request: Request, call_next):
        if self.requests_per_minute > 0 and self._is_limited_path(request.url.path):
            client_ip = request.client.host if request.client else "unknown"
            now = self.clock()
            cutoff = now - 60.0
            bucket = self._buckets[client_ip]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self.requests_per_minute:
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Rate limit exceeded. Please pause a moment before sending another request."
                    },
                    headers={"Retry-After": "60"},
                )
            bucket.append(now)

        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return response
