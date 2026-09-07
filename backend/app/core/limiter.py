"""
Centralized slowapi rate-limiter configuration.

Usage in route handlers
──────────────────────
    from app.core.limiter import limiter

    @router.post("/upload")
    @limiter.limit("30/minute")
    async def upload(request: Request, ...):
        ...

Usage in main.py
────────────────
    from app.core.limiter import limiter, rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

Key design decisions
────────────────────
- Key function uses the real client IP, falling back to the forwarded-for header
  so it works correctly behind Nginx/Caddy/load balancers.
- When REDIS_URL is configured, limits are shared across all worker processes
  (important for multi-worker deployments: uvicorn --workers N).
- When REDIS_URL is empty, limits are in-memory only (single-process dev mode).
"""
from __future__ import annotations

import logging

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

log = logging.getLogger(__name__)


def _get_real_ip(request: Request) -> str:
    """
    Extract the real client IP, respecting X-Forwarded-For and X-Real-IP
    headers set by reverse proxies (Nginx, Caddy, AWS ALB, Cloudflare, etc.).

    Falls back to the direct connection IP if no proxy headers are present.
    """
    # X-Real-IP is set by Nginx with proxy_set_header X-Real-IP $remote_addr
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    # X-Forwarded-For: client, proxy1, proxy2 — take the leftmost (real client)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    # Direct connection — use slowapi's built-in helper
    return get_remote_address(request)


def _build_limiter() -> Limiter:
    """
    Build a Limiter instance.

    If REDIS_URL is set in config, use a Redis storage backend so that limits
    are shared across all Uvicorn worker processes.
    Otherwise fall back to in-memory storage (safe for single-process dev).
    """
    # Lazy import to avoid circular dependency during module load
    from app.core.config import get_settings

    cfg = get_settings()

    if cfg.redis_url:
        log.info(
            "[limiter] Using Redis storage backend: %s",
            cfg.redis_url.split("@")[-1],  # redact password from log
        )
        storage_uri = cfg.redis_url
    else:
        log.info("[limiter] Using in-memory rate-limit storage (single-process mode).")
        storage_uri = "memory://"

    return Limiter(
        key_func=_get_real_ip,
        storage_uri=storage_uri,
        # Don't raise on HEAD requests — only count GET/POST/etc.
        headers_enabled=True,   # adds X-RateLimit-* response headers
        swallow_errors=False,   # surface storage errors instead of silently ignoring
    )


# ── Singleton ─────────────────────────────────────────────────────────────────
limiter: Limiter = _build_limiter()


# ── Exception handler ─────────────────────────────────────────────────────────

def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """
    Return a clean 429 JSON response when a rate limit is hit.

    Registered in main.py::

        app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    """
    log.warning(
        "[rate_limit] %s %s exceeded limit — client IP: %s",
        request.method,
        request.url.path,
        _get_real_ip(request),
    )
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Too many requests. Please slow down and try again.",
            "limit": str(exc.detail),
        },
        headers={
            "Retry-After": "60",
            "X-RateLimit-Limit": str(exc.detail),
        },
    )
