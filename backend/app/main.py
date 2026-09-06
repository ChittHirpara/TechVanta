import os
import shutil
import time
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import api_router
from app.core.config import get_settings
from app.db.session import get_db

settings = get_settings()

app = FastAPI(
    title="Land Record Digitizer",
    description="Enterprise API for digitizing, OCR-processing, verifying, and querying land records.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    debug=settings.debug,
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
        "storage": storage_info,
    }
