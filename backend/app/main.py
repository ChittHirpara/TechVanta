import logging
import os
import shutil
import time
from pathlib import Path

from fastapi import Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler as _slowapi_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import api_router
from app.core.config import get_settings
from app.core.limiter import limiter, rate_limit_exceeded_handler
from app.db.session import get_db

logger = logging.getLogger("app.main")
settings = get_settings()

app = FastAPI(
    title="Land Record Digitizer",
    description="Enterprise API for digitizing, OCR-processing, verifying, and querying land records.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    debug=settings.debug,
)

# ── Rate Limiter ──────────────────────────────────────────────────────────────
# Attach limiter instance to app state (required by slowapi decorator resolution)
app.state.limiter = limiter
# Register 429 handler so rate-limit violations return clean JSON (not raw HTTP)
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
# Add SlowAPI middleware — intercepts responses to attach X-RateLimit-* headers
app.add_middleware(SlowAPIMiddleware)


# ── Global exception handler ──────────────────────────────────────────────────
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch unhandled runtime errors, log server-side, and return sanitized 500."""
    logger.exception(
        "Unhandled exception occurred processing %s %s: %s",
        request.method,
        request.url.path,
        exc,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(api_router)

# ── Static UI Mounting ────────────────────────────────────────────────────────
_STATIC_DIR = Path(__file__).parent / "static"
_INDEX_HTML = _STATIC_DIR / "index.html"

if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
@app.get("/ui", include_in_schema=False)
async def serve_ui():
    """Serve the interactive Verifier Dashboard single-page application."""
    if _INDEX_HTML.exists():
        return FileResponse(_INDEX_HTML)
    return {"message": "BhoomiScan AI Backend running. Visit /docs for API documentation."}


# ── Health & Diagnostics ──────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """Liveness probe – returns service status."""
    return {
        "status": "ok",
        "env": settings.app_env,
        "version": app.version,
    }


@app.get("/health/diagnostics", tags=["Health"])
async def system_diagnostics(db: AsyncSession = Depends(get_db)) -> dict:
    """Deep system diagnostics for evaluators, health checks, and monitoring."""
    t0 = time.perf_counter()
    try:
        await db.execute(text("SELECT 1"))
        db_latency_ms = round((time.perf_counter() - t0) * 1000, 2)
        db_status = "HEALTHY"
    except Exception as exc:
        db_latency_ms = None
        db_status = f"ERROR: {exc}"

    tess_path = shutil.which("tesseract")
    ocr_info = {
        "provider": settings.ocr_provider,
        "languages": settings.tesseract_lang,
        "tesseract_installed": tess_path is not None,
        "tesseract_binary": tess_path or "not in system PATH (using mock/cloud)",
    }

    upload_dir = Path("uploads")
    storage_info = {
        "path": str(upload_dir.resolve()),
        "writable": os.access(upload_dir, os.W_OK) if upload_dir.exists() else False,
        "document_count": len(list(upload_dir.glob("*"))) if upload_dir.exists() else 0,
    }

    # Check Redis connectivity if configured
    redis_info: dict = {"configured": bool(settings.redis_url)}
    if settings.redis_url:
        try:
            import redis as redis_lib
            r = redis_lib.from_url(settings.redis_url, socket_connect_timeout=1)
            r.ping()
            redis_info["status"] = "HEALTHY"
        except Exception as redis_exc:
            redis_info["status"] = f"ERROR: {redis_exc}"

    return {
        "app_status": "ONLINE",
        "version": app.version,
        "environment": settings.app_env,
        "database": {
            "status": db_status,
            "latency_ms": db_latency_ms,
        },
        "ocr_engine": ocr_info,
        "llm_engine": {
            "model": settings.llm_model,
            "temperature": settings.llm_temperature,
            "base_url": settings.llm_base_url or "api.openai.com",
        },
        "rate_limiting": {
            "upload_limit": settings.rate_limit_upload,
            "login_limit": settings.rate_limit_login,
            "api_limit": settings.rate_limit_api,
            "backend": "redis" if settings.redis_url else "in-memory",
        },
        "storage": storage_info,
        **( {"redis": redis_info} if settings.redis_url else {} ),
    }
