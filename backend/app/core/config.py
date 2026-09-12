from functools import lru_cache
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


from pathlib import Path

_ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=(_ENV_PATH, ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    app_env: str = "development"
    debug: bool = False
    enable_multilingual_ui: bool = False

    # ── CORS ─────────────────────────────────────────────────────────────────
    # Comma-separated list of allowed origins or list of strings
    allowed_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:19006",
        "http://localhost:8081",
    ]

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [orig.strip() for orig in v.split(",") if orig.strip()]
        return v

    # ── Database ─────────────────────────────────────────────────────────────
    # Defaults to SQLite for zero-config local development.
    # Override with a PostgreSQL URL for production:
    #   postgresql+asyncpg://user:password@host:5432/land_records
    db_url: str = "sqlite+aiosqlite:///./land_records.db"

    # ── JWT ──────────────────────────────────────────────────────────────────
    # IMPORTANT: always override JWT_SECRET in production via .env or env var!
    jwt_secret: str = "dev-only-insecure-secret-CHANGE-IN-PRODUCTION"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # ── LLM (Extraction) ─────────────────────────────────────────────────────
    llm_api_key: str = ""
    llm_model: str = "gpt-4o"
    # Optional override for OpenAI-compatible endpoints (Ollama, Azure, etc.)
    # e.g. http://localhost:11434/v1  — leave blank to use api.openai.com
    llm_base_url: str = ""
    llm_temperature: float = 0.0   # 0 = deterministic; good for structured extraction
    llm_max_tokens: int = 2048
    llm_max_retries: int = 2       # how many JSON-parse-retry attempts

    # ── LM Studio (local vision + extraction) ────────────────────────────────
    # Base URL of the LM Studio server (OpenAI-compatible /v1 endpoint)
    # e.g. http://127.0.0.1:1234/v1
    lm_studio_base_url: str = ""
    # Vision model used for OCR (image → text)
    ocr_model: str = "allenai/olmocr-2-7b"
    # Text model used for structured field extraction from OCR text
    extraction_model: str = "qwen/qwen3-vl-8b"

    # ── OCR ──────────────────────────────────────────────────────────────────
    # Supported values: "tesseract" | "easyocr" | "trocr" | "lmstudio"
    ocr_provider: str = "tesseract"
    # Tesseract language(s), e.g. "eng" or "eng+hin" for multilingual docs
    tesseract_lang: str = "eng"
    # DPI used when converting PDF pages to images
    pdf_dpi: int = 300

    # ── Validation ───────────────────────────────────────────────────────────
    # Combined confidence below this → ExtractedField.is_flagged = True
    review_threshold: float = 0.75
    # Per-field confidence threshold overrides (checked before global review_threshold)
    field_confidence_thresholds: dict[str, float] = {
        "khasra_number": 0.85,
        "survey_number": 0.85,
        "khata_number": 0.80,
        "plot_area": 0.80,
    }
    # rapidfuzz similarity threshold (0-100) for duplicate detection
    fuzzy_threshold: float = 85.0
    # Weight given to OCR confidence vs LLM extraction confidence (must sum to 1)
    ocr_confidence_weight: float = 0.40
    extraction_confidence_weight: float = 0.60
    # Verification SLA threshold in hours for admin escalation alerts
    verification_sla_hours: int = 48


    # ── Redis ─────────────────────────────────────────────────────────────────
    # Optional Redis URL for rate limiting (and future caching/task queuing).
    # Leave empty "" to use in-memory rate limiting (fine for single-process dev/test).
    # Production example: redis://localhost:6379/0  or  redis://:password@host:6379/0
    redis_url: str = ""

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    # slowapi / limits format: "<count>/<period>"
    # Examples: "30/minute", "5/second", "1000/hour"
    rate_limit_upload: str = "30/minute"   # per-IP on POST /documents/upload
    rate_limit_login: str = "10/minute"    # per-IP on POST /auth/login (brute-force guard)
    rate_limit_api: str = "120/minute"     # per-IP global on all /api/v1/* routes


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (singleton)."""
    return Settings()
