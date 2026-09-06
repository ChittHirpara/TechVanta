from functools import lru_cache
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    app_env: str = "development"
    debug: bool = False

    # ── CORS ─────────────────────────────────────────────────────────────────
    # Comma-separated list of allowed origins or list of strings
    allowed_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
    ]

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [orig.strip() for orig in v.split(",") if orig.strip()]
        return v

    # ── Database ─────────────────────────────────────────────────────────────
    db_url: str  # e.g. postgresql+asyncpg://user:pass@host:port/db

    # ── JWT ──────────────────────────────────────────────────────────────────
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # ── LLM ──────────────────────────────────────────────────────────────────
    llm_api_key: str = ""
    llm_model: str = "gpt-4o"
    # Optional override for OpenAI-compatible endpoints (Ollama, Azure, etc.)
    # e.g. http://localhost:11434/v1  — leave blank to use api.openai.com
    llm_base_url: str = ""
    llm_temperature: float = 0.0   # 0 = deterministic; good for structured extraction
    llm_max_tokens: int = 2048
    llm_max_retries: int = 2       # how many JSON-parse-retry attempts

    # ── OCR ──────────────────────────────────────────────────────────────────
    # Supported values: "tesseract" | "easyocr" | "trocr"
    ocr_provider: str = "tesseract"
    # Tesseract language(s), e.g. "eng" or "eng+hin" for multilingual docs
    tesseract_lang: str = "eng"
    # DPI used when converting PDF pages to images
    pdf_dpi: int = 300

    # ── Validation ───────────────────────────────────────────────────────────
    # Combined confidence below this → ExtractedField.is_flagged = True
    review_threshold: float = 0.75
    # rapidfuzz similarity threshold (0-100) for duplicate detection
    fuzzy_threshold: float = 85.0
    # Weight given to OCR confidence vs LLM extraction confidence (must sum to 1)
    ocr_confidence_weight: float = 0.40
    extraction_confidence_weight: float = 0.60


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (singleton)."""
    return Settings()
