#!/usr/bin/env python3
"""
Standalone OCR validation script.

Usage
─────
Run from the project root (land-record-digitizer/) so the app package is
on the Python path:

    # Basic – uses provider from .env (default: tesseract)
    python scripts/test_ocr.py path/to/document.pdf

    # Override language
    python scripts/test_ocr.py scan.png --lang eng+hin

    # Show every extracted word with its confidence
    python scripts/test_ocr.py scan.tiff --words

    # Save raw text to a file
    python scripts/test_ocr.py scan.jpg --out extracted.txt

    # Run against the bundled sample (downloads a tiny public-domain image)
    python scripts/test_ocr.py --sample
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import textwrap
import time
import urllib.request
from pathlib import Path

# ── Make sure the project root is importable even when run directly ───────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ── ANSI colours (degrade gracefully on Windows without VT enabled) ───────────
def _supports_color() -> bool:
    import os
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty() and os.name != "nt" or (
        os.name == "nt" and os.environ.get("TERM_PROGRAM") in ("vscode", "mintty")
    )


if _supports_color():
    CYAN   = "\033[96m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    RED    = "\033[91m"
    BOLD   = "\033[1m"
    RESET  = "\033[0m"
else:
    CYAN = GREEN = YELLOW = RED = BOLD = RESET = ""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _bar(value: float, width: int = 30) -> str:
    """ASCII progress-bar for a 0–1 confidence value."""
    filled = round(value * width)
    colour = GREEN if value >= 0.80 else YELLOW if value >= 0.50 else RED
    bar = "█" * filled + "░" * (width - filled)
    return f"{colour}{bar}{RESET} {value * 100:5.1f}%"


def _confidence_label(value: float) -> str:
    if value >= 0.80:
        return f"{GREEN}HIGH{RESET}"
    if value >= 0.50:
        return f"{YELLOW}MEDIUM{RESET}"
    return f"{RED}LOW{RESET}"


def _download_sample(dest: Path) -> Path:
    """Download a small public-domain image for quick smoke-testing."""
    url = (
        "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a7/"
        "Camponotus_flavomarginatus_ant.jpg/320px-Camponotus_flavomarginatus_ant.jpg"
    )
    # Prefer a proper text image; fall back to the Wikipedia test page PNG
    url = (
        "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/"
        "Hello_World_B%C3%BCromaschine.jpg/320px-Hello_World_B%C3%BCromaschine.jpg"
    )
    img_path = dest / "sample_ocr_test.jpg"
    if not img_path.exists():
        print(f"{CYAN}Downloading sample image …{RESET}")
        urllib.request.urlretrieve(url, img_path)
        print(f"  Saved to {img_path}")
    return img_path


# ── Main ──────────────────────────────────────────────────────────────────────

async def run(args: argparse.Namespace) -> int:
    # Lazy-import so the script gives a nice error if deps are missing
    try:
        from app.services.ocr import get_ocr_provider, TesseractProvider
    except ImportError as exc:
        print(f"{RED}Import error:{RESET} {exc}")
        print("Make sure you are inside the project virtualenv with requirements installed.")
        return 1

    # Resolve file path
    if args.sample:
        tmp_dir = PROJECT_ROOT / "scripts" / ".samples"
        tmp_dir.mkdir(exist_ok=True)
        file_path = _download_sample(tmp_dir)
    else:
        file_path = Path(args.file).resolve()

    if not file_path.exists():
        print(f"{RED}Error:{RESET} File not found: {file_path}")
        return 1

    # Build provider (CLI flags override .env)
    if args.lang or args.dpi:
        provider = TesseractProvider(
            lang=args.lang or "eng",
            pdf_dpi=args.dpi or 300,
        )
    else:
        try:
            provider = get_ocr_provider()
        except Exception as exc:
            print(
                f"{YELLOW}Warning:{RESET} Could not load provider from config "
                f"({exc}). Falling back to TesseractProvider(eng)."
            )
            provider = TesseractProvider()

    # ── Banner ────────────────────────────────────────────────────────────────
    print()
    print(f"{BOLD}{'─' * 60}{RESET}")
    print(f"{BOLD}  Land Record Digitizer – OCR Validator{RESET}")
    print(f"{BOLD}{'─' * 60}{RESET}")
    print(f"  File    : {CYAN}{file_path}{RESET}")
    print(f"  Provider: {CYAN}{provider.name}{RESET}")
    print(f"{'─' * 60}")

    # ── Extract ───────────────────────────────────────────────────────────────
    print(f"\n{BOLD}Running OCR …{RESET}")
    t0 = time.perf_counter()
    try:
        result = await provider.extract_text(file_path)
    except FileNotFoundError as exc:
        print(f"{RED}Error:{RESET} {exc}")
        return 1
    except Exception as exc:
        print(f"{RED}OCR failed:{RESET} {exc}")
        raise
    elapsed = time.perf_counter() - t0

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{BOLD}{'─' * 60}")
    print("  Results")
    print(f"{'─' * 60}{RESET}")
    print(f"  Pages processed : {result.page_count}")
    print(f"  Words detected  : {len(result.word_confidences)}")
    print(f"  Elapsed         : {elapsed:.2f}s")
    print(
        f"  Avg confidence  : {_bar(result.avg_confidence)}  "
        f"[{_confidence_label(result.avg_confidence)}]"
    )

    # ── Extracted text ────────────────────────────────────────────────────────
    print(f"\n{BOLD}{'─' * 60}")
    print("  Extracted Text")
    print(f"{'─' * 60}{RESET}")
    if result.raw_text.strip():
        # Wrap long lines for readability in the terminal
        for line in result.raw_text.splitlines():
            wrapped = textwrap.fill(line, width=78, initial_indent="  ", subsequent_indent="  ")
            print(wrapped if wrapped.strip() else "")
    else:
        print(f"  {YELLOW}(no text extracted – check image quality or language setting){RESET}")

    # ── Per-word confidences (optional) ───────────────────────────────────────
    if args.words and result.word_confidences:
        print(f"\n{BOLD}{'─' * 60}")
        print("  Per-word Confidences")
        print(f"{'─' * 60}{RESET}")
        col_w = max(len(wc.word) for wc in result.word_confidences) + 2
        for wc in result.word_confidences:
            bar = _bar(wc.confidence, width=20)
            print(f"  {wc.word:<{col_w}} {bar}")

    # ── Low-confidence words ──────────────────────────────────────────────────
    flagged = [wc for wc in result.word_confidences if wc.confidence < 0.50]
    if flagged:
        print(f"\n{YELLOW}{BOLD}  ⚠  Low-confidence words (< 50%):{RESET}")
        flagged_str = ", ".join(f"'{wc.word}' ({wc.confidence*100:.0f}%)" for wc in flagged[:20])
        if len(flagged) > 20:
            flagged_str += f" … and {len(flagged) - 20} more"
        print(f"  {flagged_str}")

    # ── Save output ───────────────────────────────────────────────────────────
    if args.out:
        out_path = Path(args.out)
        out_path.write_text(result.raw_text, encoding="utf-8")
        print(f"\n{GREEN}✔{RESET}  Raw text saved to {out_path}")

    print(f"\n{BOLD}{'─' * 60}{RESET}\n")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate OCR quality on an image or PDF file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="Path to an image (.png/.jpg/.tiff) or PDF file.",
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Download and OCR a bundled sample image (for smoke-testing).",
    )
    parser.add_argument(
        "--lang",
        default="",
        metavar="LANG",
        help="Tesseract language string, e.g. 'eng' or 'eng+hin'. "
             "Overrides TESSERACT_LANG in .env.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=0,
        metavar="DPI",
        help="PDF→image resolution (default: 300). Higher = slower but more accurate.",
    )
    parser.add_argument(
        "--words",
        action="store_true",
        help="Print per-word confidence scores.",
    )
    parser.add_argument(
        "--out",
        metavar="FILE",
        help="Save extracted raw text to this file.",
    )

    ns = parser.parse_args()
    if not ns.sample and not ns.file:
        parser.error("Provide a file path or use --sample for a quick smoke-test.")
    return ns


if __name__ == "__main__":
    args = _parse_args()
    sys.exit(asyncio.run(run(args)))
