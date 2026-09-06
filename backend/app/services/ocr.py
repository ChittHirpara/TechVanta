"""
OCR service layer.

Architecture
────────────
OCRProvider (ABC)          ← stable interface
    └─ TesseractProvider   ← default implementation
    └─ (future: EasyOCRProvider, TrOCRProvider …)

get_ocr_provider()         ← factory; reads OCR_PROVIDER from config
"""
from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------

@dataclass
class WordConfidence:
    word: str
    confidence: float  # 0.0 – 1.0


@dataclass
class OCRResult:
    """Unified result object returned by every provider."""
    raw_text: str
    avg_confidence: float                        # 0.0 – 1.0
    word_confidences: list[WordConfidence] = field(default_factory=list)
    page_count: int = 1                          # >1 for multi-page PDFs
    provider: str = "unknown"

    def to_dict(self) -> dict:
        return {
            "raw_text": self.raw_text,
            "avg_confidence": self.avg_confidence,
            "word_confidences": [
                {"word": wc.word, "confidence": wc.confidence}
                for wc in self.word_confidences
            ],
            "page_count": self.page_count,
            "provider": self.provider,
        }


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class OCRProvider(ABC):
    """
    Contract that every OCR backend must satisfy.

    Implementations must override ``_extract_sync``; the public
    ``extract_text`` coroutine runs that blocking call in a thread-pool
    executor so it never blocks the event loop.
    """

    # Subclasses set this for identification
    name: str = "base"

    @abstractmethod
    def _extract_sync(self, file_path: Path) -> OCRResult:
        """
        Synchronous extraction – called from a thread executor.

        Args:
            file_path: Absolute path to an image or PDF file.

        Returns:
            OCRResult with text, confidences, and page count.
        """
        ...

    async def extract_text(self, file_path: str | Path) -> OCRResult:
        """
        Async public API.  Dispatches ``_extract_sync`` to a thread so
        CPU-bound / blocking OCR calls do not stall the event loop.

        Args:
            file_path: Path (str or Path) to an image or PDF file.

        Returns:
            OCRResult
        """
        path = Path(file_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"OCR input not found: {path}")

        loop = asyncio.get_event_loop()
        result: OCRResult = await loop.run_in_executor(None, self._extract_sync, path)
        return result


# ---------------------------------------------------------------------------
# Tesseract implementation
# ---------------------------------------------------------------------------

#: File extensions treated as images (no PDF conversion needed)
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}
#: File extensions that require pdf2image conversion
_PDF_SUFFIXES = {".pdf"}


class TesseractProvider(OCRProvider):
    """
    OCR via Tesseract (pytesseract wrapper).

    Handles:
    • Image files  → passed directly to pytesseract
    • PDF files    → each page converted to a PIL image via pdf2image,
                     then OCR-ed; pages are concatenated with page breaks.

    Word-level confidences come from ``image_to_data`` (HOCR-lite output).
    """

    name = "tesseract"

    def __init__(self, lang: str = "eng", pdf_dpi: int = 300) -> None:
        """
        Args:
            lang:    Tesseract language string, e.g. ``"eng"`` or ``"eng+hin"``.
            pdf_dpi: Resolution for PDF→image conversion.  300 DPI gives
                     ~A4-sized images at good quality; use 200 for faster
                     processing of large documents.
        """
        self.lang = lang
        self.pdf_dpi = pdf_dpi

    # ── private helpers ───────────────────────────────────────────────────────

    def _ocr_image(self, image) -> tuple[str, list[WordConfidence]]:
        """
        Run Tesseract on a single PIL Image.

        Returns (text, word_confidences).
        """
        import pytesseract  # lazy import – not available in every environment

        # image_to_data returns a dict with per-word metadata
        data = pytesseract.image_to_data(
            image,
            lang=self.lang,
            output_type=pytesseract.Output.DICT,
        )

        words: list[WordConfidence] = []
        for text, conf in zip(data["text"], data["conf"]):
            text = text.strip()
            # Tesseract returns -1 confidence for non-word blocks; skip them
            if text and conf != -1:
                words.append(WordConfidence(word=text, confidence=float(conf) / 100.0))

        # Full page text (cleaner than joining `data["text"]`)
        raw = pytesseract.image_to_string(image, lang=self.lang)
        return raw.strip(), words

    def _extract_from_image(self, path: Path) -> OCRResult:
        from PIL import Image

        with Image.open(path) as img:
            img = img.convert("RGB")
            text, words = self._ocr_image(img)

        avg_conf = (
            sum(w.confidence for w in words) / len(words) if words else 0.0
        )
        return OCRResult(
            raw_text=text,
            avg_confidence=round(avg_conf, 4),
            word_confidences=words,
            page_count=1,
            provider=self.name,
        )

    def _extract_from_pdf(self, path: Path) -> OCRResult:
        from pdf2image import convert_from_path

        log.info("Converting PDF '%s' to images at %d DPI …", path.name, self.pdf_dpi)
        pages = convert_from_path(str(path), dpi=self.pdf_dpi)
        log.info("  → %d page(s) detected", len(pages))

        all_text_parts: list[str] = []
        all_words: list[WordConfidence] = []

        for i, page_img in enumerate(pages, start=1):
            log.debug("  OCR-ing page %d/%d", i, len(pages))
            page_text, page_words = self._ocr_image(page_img)
            all_text_parts.append(f"[Page {i}]\n{page_text}")
            all_words.extend(page_words)

        raw_text = "\n\n".join(all_text_parts)
        avg_conf = (
            sum(w.confidence for w in all_words) / len(all_words)
            if all_words
            else 0.0
        )
        return OCRResult(
            raw_text=raw_text,
            avg_confidence=round(avg_conf, 4),
            word_confidences=all_words,
            page_count=len(pages),
            provider=self.name,
        )

    # ── public sync entry-point (called by base class executor) ──────────────

    def _extract_sync(self, file_path: Path) -> OCRResult:
        suffix = file_path.suffix.lower()
        if suffix in _PDF_SUFFIXES:
            return self._extract_from_pdf(file_path)
        elif suffix in _IMAGE_SUFFIXES:
            return self._extract_from_image(file_path)
        else:
            raise ValueError(
                f"Unsupported file type '{suffix}'. "
                f"Supported: {_IMAGE_SUFFIXES | _PDF_SUFFIXES}"
            )


# ---------------------------------------------------------------------------
# Future provider stubs (swap in without changing calling code)
# ---------------------------------------------------------------------------

class EasyOCRProvider(OCRProvider):
    """Placeholder – implement when EasyOCR is added to requirements."""
    name = "easyocr"

    def _extract_sync(self, file_path: Path) -> OCRResult:
        raise NotImplementedError(
            "EasyOCRProvider is not yet implemented. "
            "Set OCR_PROVIDER=tesseract in your .env."
        )


class TrOCRProvider(OCRProvider):
    """Placeholder – implement when TrOCR (HuggingFace) is added."""
    name = "trocr"

    def _extract_sync(self, file_path: Path) -> OCRResult:
        raise NotImplementedError(
            "TrOCRProvider is not yet implemented. "
            "Set OCR_PROVIDER=tesseract in your .env."
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, type[OCRProvider]] = {
    "tesseract": TesseractProvider,
    "easyocr": EasyOCRProvider,
    "trocr": TrOCRProvider,
}

ProviderName = Literal["tesseract", "easyocr", "trocr"]


def get_ocr_provider() -> OCRProvider:
    """
    Factory function.  Reads ``OCR_PROVIDER``, ``TESSERACT_LANG``, and
    ``PDF_DPI`` from config and returns a ready-to-use ``OCRProvider``.

    Swap the backend by changing ``OCR_PROVIDER`` in ``.env`` – no code
    changes required in callers.

    Returns:
        A concrete ``OCRProvider`` instance.

    Raises:
        ValueError: if ``OCR_PROVIDER`` names an unregistered backend.
    """
    from app.core.config import get_settings

    cfg = get_settings()
    provider_key = cfg.ocr_provider.lower().strip()

    cls = _REGISTRY.get(provider_key)
    if cls is None:
        raise ValueError(
            f"Unknown OCR provider '{provider_key}'. "
            f"Available: {list(_REGISTRY)}"
        )

    # Provider-specific construction args
    if provider_key == "tesseract":
        return TesseractProvider(lang=cfg.tesseract_lang, pdf_dpi=cfg.pdf_dpi)

    return cls()
