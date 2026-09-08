#!/usr/bin/env python3
"""
Standalone extraction validation script.

Usage
─────
Run from the project root (land-record-digitizer/) with your .env in place:

    # Pass raw text directly as a quoted argument
    python scripts/test_extraction.py "Owner: Ram Kumar. Khasra No. 451/2, Village Rampur"

    # Read raw text from a file
    python scripts/test_extraction.py --file path/to/ocr_output.txt

    # Pipe raw text from stdin
    cat ocr_output.txt | python scripts/test_extraction.py --stdin

    # Pretty-print with confidence colour-coding (default)
    python scripts/test_extraction.py --file ocr.txt

    # Output plain JSON (for piping to jq or saving)
    python scripts/test_extraction.py --file ocr.txt --json

    # Override model and base URL without editing .env
    python scripts/test_extraction.py --file ocr.txt --model gpt-4o-mini

    # Use a local Ollama endpoint
    python scripts/test_extraction.py --file ocr.txt \\
        --model llama3 --base-url http://localhost:11434/v1

    # Quick smoke-test with a built-in sample text (no real API key needed if mocked)
    python scripts/test_extraction.py --sample
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

# ── Ensure project root is importable ────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── ANSI colours ─────────────────────────────────────────────────────────────
_IS_TTY = sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _IS_TTY else text


def bold(t: str) -> str:   return _c("1", t)
def cyan(t: str) -> str:   return _c("96", t)
def green(t: str) -> str:  return _c("92", t)
def yellow(t: str) -> str: return _c("93", t)
def red(t: str) -> str:    return _c("91", t)
def grey(t: str) -> str:   return _c("90", t)
def dim(t: str) -> str:    return _c("2", t)


_CONF_COLOUR = {
    "high":   green,
    "medium": yellow,
    "low":    red,
}
_CONF_ICON = {"high": "●", "medium": "◐", "low": "○"}

# ── Built-in sample land-record text ─────────────────────────────────────────

_SAMPLE_TEXT = """
GOVERNMENT OF RAJASTHAN
REVENUE DEPARTMENT – KHASRA REGISTER

District    : Jaipur
Tehsil      : Sanganer
Village     : Rampur Kalan
Halqa No.   : 14

Khata No.   : 112
Khasra No.  : 451/2
Survey No.  : 78-B

Owner Name  : Ram Kumar Singh S/O Shyam Lal Singh
Land Area   : 2 Bigha 14 Biswa (approx 1.45 acres)
Land Class  : Agricultural – Irrigated (Sichit Krishi Bhoomi)

Mutation Record:
  Entry 23 dated 15-Mar-2019: Transfer from Shyam Lal Singh to Ram Kumar Singh
  Registered vide Sale Deed No. 4521/2019 at Sub-Registrar Office, Sanganer

Registration Info:
  Sale Deed registered on 15-Mar-2019
  Stamp Duty paid: Rs. 12,500
  Sub-Registrar: Sanganer, Jaipur

Ownership Details:
  Single owner. No encumbrance. No mortgage recorded as of date of issue.

Issued by: Patwari, Halqa No. 14, Sanganer Tehsil
Date of Issue: 01-Sep-2026
""".strip()


# ── Pretty printer ────────────────────────────────────────────────────────────

def _print_result(result, elapsed: float) -> None:
    from app.services.extraction import FIELD_NAMES

    print()
    print(bold("─" * 62))
    print(bold("  Land Record Digitizer – Extraction Result"))
    print(bold("─" * 62))
    print(f"  Model          : {cyan(result.model)}")
    print(f"  Parse attempts : {result.attempt_count}")
    print(f"  Elapsed        : {elapsed:.2f}s")
    if result.parse_error:
        print(f"  {red('Parse error')}    : {result.parse_error}")
    print(bold("─" * 62))

    col_w = max(len(n) for n in FIELD_NAMES) + 2
    for name in FIELD_NAMES:
        fe = result.fields[name]
        conf_fn  = _CONF_COLOUR.get(fe.confidence, grey)
        icon     = _CONF_ICON.get(fe.confidence, "?")
        conf_tag = conf_fn(f"{icon} {fe.confidence:<6}")

        if fe.value is not None:
            val_str = green(fe.value) if fe.confidence == "high" else fe.value
        else:
            val_str = dim("null")

        label = f"{name}:".ljust(col_w)
        print(f"  {cyan(label)}  {val_str}")
        print(f"  {'':>{col_w}}  {grey('confidence:')} {conf_tag}")
        print()

    # Summary stats
    found    = sum(1 for fe in result.fields.values() if fe.value is not None)
    total    = len(result.fields)
    high_c   = sum(1 for fe in result.fields.values() if fe.confidence == "high")
    medium_c = sum(1 for fe in result.fields.values() if fe.confidence == "medium")
    low_c    = sum(1 for fe in result.fields.values() if fe.confidence == "low")

    print(bold("─" * 62))
    print(f"  Fields found   : {green(str(found))}/{total}")
    print(
        f"  Confidence     : "
        f"{green(str(high_c))} high  "
        f"{yellow(str(medium_c))} medium  "
        f"{red(str(low_c))} low"
    )
    print(bold("─" * 62))
    print()


# ── Main ─────────────────────────────────────────────────────────────────────

async def run(args: argparse.Namespace) -> int:
    # ── Resolve raw text ─────────────────────────────────────────────────────
    if args.sample:
        raw_text = _SAMPLE_TEXT
        print(f"{cyan('Using built-in sample text.')}")
    elif args.stdin:
        raw_text = sys.stdin.read()
    elif args.file:
        p = Path(args.file)
        if not p.exists():
            print(f"{red('Error:')} File not found: {p}")
            return 1
        raw_text = p.read_text(encoding="utf-8")
    elif args.text:
        raw_text = args.text
    else:
        print(f"{red('Error:')} Provide --text, --file, --stdin, or --sample.")
        return 1

    if not raw_text.strip():
        print(f"{red('Error:')} Input text is empty.")
        return 1

    # ── Override config via CLI flags ─────────────────────────────────────────
    if args.model or args.base_url:
        os.environ.setdefault("LLM_MODEL",    args.model    or "gpt-4o")
        os.environ.setdefault("LLM_BASE_URL", args.base_url or "")

    # ── Import after path fix ─────────────────────────────────────────────────
    try:
        from app.services.extraction import extract_fields
    except ImportError as exc:
        print(f"{red('Import error:')} {exc}")
        print("Run from the project root with your virtualenv active.")
        return 1

    # ── Show input summary ────────────────────────────────────────────────────
    if not args.json:
        print()
        print(bold("─" * 62))
        print(bold("  Input Text Preview"))
        print(bold("─" * 62))
        preview = raw_text[:400].replace("\n", "\n  ")
        print(f"  {preview}")
        if len(raw_text) > 400:
            print(f"  {grey(f'… ({len(raw_text) - 400} more characters)')}")
        print(bold("─" * 62))
        print(f"\n{bold('Calling LLM …')}")

    # ── Extract ───────────────────────────────────────────────────────────────
    t0 = time.perf_counter()
    try:
        result = await extract_fields(raw_text)
    except Exception as exc:
        print(f"{red('Extraction error:')} {exc}")
        return 1
    elapsed = time.perf_counter() - t0

    # ── Output ────────────────────────────────────────────────────────────────
    if args.json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    else:
        _print_result(result, elapsed)

    # ── Save ──────────────────────────────────────────────────────────────────
    if args.out:
        out_path = Path(args.out)
        out_path.write_text(
            json.dumps(result.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"{green('✔')}  Output saved to {out_path}")

    return 0 if result.parse_error is None else 2


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Validate LLM field extraction from raw land-record text.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    src = p.add_mutually_exclusive_group()
    src.add_argument("text", nargs="?", help="Raw text passed directly as a CLI argument.")
    src.add_argument("--file",   metavar="PATH", help="Read raw text from this file.")
    src.add_argument("--stdin",  action="store_true", help="Read raw text from stdin.")
    src.add_argument("--sample", action="store_true", help="Use built-in sample land-record text.")

    p.add_argument("--model",    metavar="NAME",  default="", help="Override LLM_MODEL.")
    p.add_argument("--base-url", metavar="URL",   default="", help="Override LLM_BASE_URL.")
    p.add_argument("--json",     action="store_true", help="Print plain JSON (pipe-friendly).")
    p.add_argument("--out",      metavar="FILE",  help="Save JSON result to this file.")

    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    sys.exit(asyncio.run(run(args)))
