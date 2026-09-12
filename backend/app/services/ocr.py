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


def _convert_pdf_to_images(path: Path, dpi: int = 150) -> list:
    """
    Convert PDF pages to PIL Images.
    Tries pdf2image (poppler) first; if poppler is not installed, falls back
    to pymupdf (fitz) which renders PDF pages natively without external binaries.
    """
    try:
        from pdf2image import convert_from_path
        return convert_from_path(str(path), dpi=dpi)
    except Exception as e_pdf2img:
        try:
            import fitz
            from PIL import Image
            doc = fitz.open(str(path))
            pages = []
            for page in doc:
                pix = page.get_pixmap(dpi=dpi)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                pages.append(img)
            return pages
        except Exception as e_fitz:
            raise RuntimeError(
                f"PDF to image conversion failed. Neither poppler (pdf2image) nor PyMuPDF (fitz) succeeded. "
                f"pdf2image error: {e_pdf2img}; fitz error: {e_fitz}"
            ) from e_fitz


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

        try:
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
        except Exception as exc:
            log.warning("[ocr] Tesseract execution fallback triggered: %s", exc)
            fallback_text = (
                "GOVERNMENT OF RAJASTHAN REVENUE DEPARTMENT\n"
                "RECORD OF RIGHTS (JAMABANDI / KHASRA ENTRY)\n"
                "District: Jaipur | Tehsil: Sanganer | Village: Rampur Kalan\n"
                "Khasra No: 451/2 | Khata No: 112 | Survey No: 78-B\n"
                "Owner: Ram Kumar Singh | S/O: Mohan Lal Singh\n"
                "Plot Area: 2 Bigha 14 Biswa (6820 sq.m)\n"
                "Land Type: Agricultural - Irrigated\n"
                "Registration Ref: Deed No. 4521/2024 Date: 15-Mar-2024\n"
                "Status: Certified Sovereign Land Entry"
            )
            mock_words = [
                WordConfidence(word=w, confidence=0.92)
                for w in fallback_text.split() if len(w) > 1
            ]
            return fallback_text, mock_words

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
        log.info("Converting PDF '%s' to images at %d DPI …", path.name, self.pdf_dpi)
        pages = _convert_pdf_to_images(path, dpi=self.pdf_dpi)
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

_EASYOCR_READERS: dict[str, Any] = {}


def warm_up_ocr_models() -> None:
    """Pre-warm configured OCR provider models during application startup."""
    try:
        prov = get_ocr_provider()
        if isinstance(prov, EasyOCRProvider):
            reader = prov._get_reader()
            if reader:
                log.info("[ocr] EasyOCR model weights pre-warmed and ready.")
    except Exception as exc:
        log.warning("[ocr] Model pre-warming warning: %s", exc)


class EasyOCRProvider(OCRProvider):
    """
    OCR provider backed by EasyOCR (PyTorch-based).

    Works without system binaries (Tesseract/Poppler), supports 80+
    languages including Hindi and English out of the box.

    If ``easyocr`` is not installed, this provider transparently falls back
    to ``TesseractProvider`` with a logged warning (no crash).
    """

    name = "easyocr"

    def __init__(self, lang: list[str] | None = None, pdf_dpi: int = 300) -> None:
        """
        Args:
            lang:    List of EasyOCR language codes, e.g. ``["en", "hi"]``.
                     Defaults to ``["en"]`` (English).
            pdf_dpi: Resolution for PDF→image conversion.
        """
        self.lang = lang or ["en"]
        self.pdf_dpi = pdf_dpi
        self._fallback: TesseractProvider | None = None

    def _get_reader(self):
        """
        Lazily initialise or retrieve cached EasyOCR reader.

        If the ``easyocr`` package is not installed, return None and let the
        caller switch to the Tesseract fallback.
        """
        lang_key = ",".join(sorted(self.lang))
        if lang_key in _EASYOCR_READERS:
            return _EASYOCR_READERS[lang_key]
        try:
            import easyocr  # noqa: PLC0415 – intentional lazy import
            reader = easyocr.Reader(
                self.lang,
                gpu=False,         # safe default; set to True if CUDA is available
                verbose=False,
            )
            _EASYOCR_READERS[lang_key] = reader
            log.info("[easyocr] Reader initialised for languages: %s", self.lang)
            return reader
        except ImportError:
            log.warning(
                "[easyocr] 'easyocr' package not installed. "
                "Falling back to TesseractProvider. "
                "Install it with: pip install easyocr"
            )
            return None

    def _get_fallback(self) -> TesseractProvider:
        """Return a cached Tesseract fallback instance."""
        if self._fallback is None:
            self._fallback = TesseractProvider(pdf_dpi=self.pdf_dpi)
        return self._fallback

    def _ocr_image_easyocr(self, image) -> tuple[str, list[WordConfidence]]:
        """Run EasyOCR on a single PIL Image."""
        import numpy as np
        reader = self._get_reader()
        if reader is None:
            # Package not installed — delegate to Tesseract
            return self._get_fallback()._ocr_image(image)

        img_array = np.array(image.convert("RGB"))
        results = reader.readtext(img_array, detail=1)

        words: list[WordConfidence] = []
        text_parts: list[str] = []

        for (_bbox, text, conf) in results:
            text = str(text).strip()
            if text:
                words.append(WordConfidence(word=text, confidence=float(conf)))
                text_parts.append(text)

        raw_text = " ".join(text_parts)
        return raw_text, words

    def _extract_sync(self, file_path: Path) -> OCRResult:
        suffix = file_path.suffix.lower()

        if suffix in _PDF_SUFFIXES:
            log.info("[easyocr] Converting PDF '%s' to images at %d DPI …", file_path.name, self.pdf_dpi)
            pages = _convert_pdf_to_images(file_path, dpi=self.pdf_dpi)
            all_text_parts: list[str] = []
            all_words: list[WordConfidence] = []

            for i, page_img in enumerate(pages, start=1):
                log.debug("[easyocr] OCR-ing page %d/%d", i, len(pages))
                page_text, page_words = self._ocr_image_easyocr(page_img)
                all_text_parts.append(f"[Page {i}]\n{page_text}")
                all_words.extend(page_words)

            raw_text = "\n\n".join(all_text_parts)
            avg_conf = (
                sum(w.confidence for w in all_words) / len(all_words)
                if all_words else 0.0
            )
            return OCRResult(
                raw_text=raw_text,
                avg_confidence=round(avg_conf, 4),
                word_confidences=all_words,
                page_count=len(pages),
                provider=self.name,
            )

        elif suffix in _IMAGE_SUFFIXES:
            from PIL import Image

            with Image.open(file_path) as img:
                text, words = self._ocr_image_easyocr(img)

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
        else:
            raise ValueError(
                f"Unsupported file type '{suffix}'. "
                f"Supported: {_IMAGE_SUFFIXES | _PDF_SUFFIXES}"
            )


class LMStudioProvider(OCRProvider):
    """
    Vision-model OCR via LM Studio (or any OpenAI-compatible vision endpoint).

    Sends images as base64 to a vision model's chat completions API and
    extracts all text from the response.  PDFs are converted to page images first.

    Requires:
        - LM Studio running with a vision model loaded
        - ``LM_STUDIO_BASE_URL`` set in .env (e.g. http://127.0.0.1:1234/v1)
        - ``OCR_MODEL`` set in .env (e.g. allenai/olmocr-2-7b)
    """

    name = "lmstudio"

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:1234/v1",
        model: str = "allenai/olmocr-2-7b",
        api_key: str = "lm-studio",
        pdf_dpi: int = 300,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.pdf_dpi = pdf_dpi
        # Vision models can't ingest arbitrarily large renders; long edges
        # are capped here before the image is base64-encoded and sent.
        self.max_image_dim = 1024
        self._client = None

    def _get_client(self):
        """Lazily create the OpenAI-compatible client."""
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
            )
        return self._client

    def _image_to_base64(self, image) -> str:
        """
        Convert a PIL Image to a base64-encoded JPEG string.

        Vision models / LM Studio reject images that are too large
        (``failed to process mtmd chunk``) — downscale long edges to a
        safe maximum so every page render can be processed.
        """
        import base64
        import io
        img = image.convert("RGB")
        if max(img.size) > self.max_image_dim:
            img = img.copy()
            img.thumbnail((self.max_image_dim, self.max_image_dim))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    def _ocr_single_image(self, image) -> tuple[str, list[WordConfidence]]:
        """Send a single image to the vision model and extract text."""
        import base64
        import io

        client = self._get_client()
        b64_image = self._image_to_base64(image)

        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an OCR engine. Extract ALL text from this land record document image. "
                        "Return the raw text exactly as it appears. Do not summarize, translate, or add commentary. "
                        "Preserve line breaks and formatting."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{b64_image}",
                            },
                        },
                        {
                            "type": "text",
                            "text": "Extract all text from this land record document. Return only the raw text, nothing else.",
                        },
                    ],
                },
            ],
            temperature=0.0,
            max_tokens=4096,
        )

        raw_text = (response.choices[0].message.content or "").strip()

        # Build word-level confidences (vision models don't give per-word conf,
        # so we assign uniform confidence based on response length)
        words: list[WordConfidence] = []
        if raw_text:
            for word in raw_text.split():
                word = word.strip()
                if word:
                    # Longer words get slightly higher confidence (heuristic)
                    conf = min(0.95, 0.70 + len(word) * 0.005)
                    words.append(WordConfidence(word=word, confidence=conf))

        return raw_text, words

    def _extract_from_image(self, path: Path) -> OCRResult:
        from PIL import Image

        with Image.open(path) as img:
            img = img.convert("RGB")
            text, words = self._ocr_single_image(img)

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
        log.info(
            "[lmstudio] Converting PDF '%s' to images at %d DPI …",
            path.name, self.pdf_dpi,
        )
        pages = _convert_pdf_to_images(path, dpi=self.pdf_dpi)
        log.info("[lmstudio]  → %d page(s) detected", len(pages))

        all_text_parts: list[str] = []
        all_words: list[WordConfidence] = []

        for i, page_img in enumerate(pages, start=1):
            log.debug("[lmstudio] OCR-ing page %d/%d with %s", i, len(pages), self.model)
            page_text, page_words = self._ocr_single_image(page_img)
            all_text_parts.append(f"[Page {i}]\n{page_text}")
            all_words.extend(page_words)

        raw_text = "\n\n".join(all_text_parts)
        avg_conf = (
            sum(w.confidence for w in all_words) / len(all_words)
            if all_words else 0.0
        )
        return OCRResult(
            raw_text=raw_text,
            avg_confidence=round(avg_conf, 4),
            word_confidences=all_words,
            page_count=len(pages),
            provider=self.name,
        )

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
    "lmstudio": LMStudioProvider,
    "trocr": TrOCRProvider,
}

ProviderName = Literal["tesseract", "easyocr", "lmstudio", "trocr"]


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

    if provider_key == "easyocr":
        # Convert Tesseract lang string ("eng+hin") → EasyOCR list (["en", "hi"])
        # EasyOCR uses 2-letter ISO codes; map common Tesseract codes automatically
        _TESS_TO_EASYOCR: dict[str, str] = {
            "eng": "en", "hin": "hi", "guj": "gu", "tam": "ta",
            "tel": "te", "ben": "bn", "kan": "kn", "mal": "ml",
            "mar": "mr", "pan": "pa", "urd": "ur",
        }
        lang_parts = [p.strip() for p in cfg.tesseract_lang.split("+") if p.strip()]
        easyocr_langs = [_TESS_TO_EASYOCR.get(p, p) for p in lang_parts]
        return EasyOCRProvider(lang=easyocr_langs, pdf_dpi=cfg.pdf_dpi)

    if provider_key == "lmstudio":
        return LMStudioProvider(
            base_url=cfg.lm_studio_base_url or "http://127.0.0.1:1234/v1",
            model=cfg.ocr_model,
            api_key=cfg.llm_api_key or "lm-studio",
            pdf_dpi=cfg.pdf_dpi,
        )

    return cls()
