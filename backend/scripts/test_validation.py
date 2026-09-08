#!/usr/bin/env python3
"""
Standalone validation test script.

Usage
─────
Run from the project root (land-record-digitizer/):

    # Full test suite against sample data
    python scripts/test_validation.py

    # Only a specific section
    python scripts/test_validation.py --section validate
    python scripts/test_validation.py --section duplicates
    python scripts/test_validation.py --section confidence

    # JSON output (pipe-friendly)
    python scripts/test_validation.py --json

    # Custom threshold (overrides .env)
    python scripts/test_validation.py --threshold 0.70

    # Custom fuzzy threshold
    python scripts/test_validation.py --fuzzy 80
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── ANSI colours ─────────────────────────────────────────────────────────────
_TTY = sys.stdout.isatty()


def _c(code: str, t: str) -> str:
    return f"\033[{code}m{t}\033[0m" if _TTY else t


def bold(t: str) -> str:   return _c("1", t)
def cyan(t: str) -> str:   return _c("96", t)
def green(t: str) -> str:  return _c("92", t)
def yellow(t: str) -> str: return _c("93", t)
def red(t: str) -> str:    return _c("91", t)
def grey(t: str) -> str:   return _c("90", t)
def dim(t: str) -> str:    return _c("2", t)


SEV_COLOR = {"error": red, "warning": yellow}
PASS = green("✔ PASS")
FAIL = red("✘ FAIL")


def _header(title: str) -> None:
    print()
    print(bold("═" * 64))
    print(bold(f"  {title}"))
    print(bold("═" * 64))


def _subheader(title: str) -> None:
    print()
    print(bold(f"  ── {title} ──"))


# ─────────────────────────────────────────────────────────────────────────────
# Test data
# ─────────────────────────────────────────────────────────────────────────────

# A complete, valid land record
GOOD_RECORD = {
    "owner_name": "Ram Kumar Singh",
    "survey_number": "78-B",
    "khasra_number": "451/2",
    "khata_number": "112",
    "plot_area": "2 Bigha 14 Biswa",
    "village": "Rampur Kalan",
    "tehsil": "Sanganer",
    "district": "Jaipur",
    "land_classification": "Agricultural – Irrigated",
    "ownership_details": "Single owner, no encumbrance",
    "mutation_record": "Entry 23 dated 15-Mar-2019",
    "registration_info": "Sale Deed No. 4521/2019",
}

# Missing required fields
MISSING_REQUIRED = {
    "owner_name": "Priya Sharma",
    "survey_number": None,       # ← missing
    "khasra_number": "22/1",
    "khata_number": None,
    "plot_area": "1.2 acres",
    "village": None,             # ← missing
    "tehsil": None,              # ← missing
    "district": None,            # ← missing
    "land_classification": None,
    "ownership_details": None,
    "mutation_record": None,
    "registration_info": None,
}

# Invalid format fields
BAD_FORMATS = {
    "owner_name": "X",                 # too short (< 3 chars)
    "survey_number": "ABC##XYZ",       # non-standard
    "khasra_number": "!@#",            # non-standard
    "khata_number": "112",
    "plot_area": "large parcel",       # no leading digit
    "village": "Rampur",
    "tehsil": "Sanganer",
    "district": "Jaipur",
    "land_classification": None,
    "ownership_details": None,
    "mutation_record": None,
    "registration_info": None,
}

# Candidate documents for duplicate detection
EXISTING_DOCS = [
    {
        "document_id": 1,
        "filename": "deed_001.pdf",
        "owner_name": "Ram Kumar Singh",     # exact match
        "survey_number": "78-B",
    },
    {
        "document_id": 2,
        "filename": "deed_002.pdf",
        "owner_name": "Ram Kumar Singh S/O Shyam Lal",  # close match
        "survey_number": "78B",              # slightly different
    },
    {
        "document_id": 3,
        "filename": "deed_003.pdf",
        "owner_name": "Priya Sharma Devi",   # close to "Priya Sharma"
        "survey_number": "99/1",
    },
    {
        "document_id": 4,
        "filename": "deed_004.pdf",
        "owner_name": "Suresh Gupta",        # completely different
        "survey_number": "200",
    },
    {
        "document_id": 5,
        "filename": "deed_005.pdf",
        "owner_name": "",                    # blank owner
        "survey_number": "78-B",             # same survey
    },
]

# Confidence matrix: (ocr_confidence, extraction_confidence) → expected behaviour
CONFIDENCE_CASES = [
    # (label,              ocr,   ext_conf,   expect_flagged_at_0.75)
    ("High OCR + High LLM",   0.95, "high",   False),
    ("High OCR + Med LLM",    0.90, "medium", False),
    ("High OCR + Low LLM",    0.90, "low",    True),
    ("Med OCR  + High LLM",   0.60, "high",   False),
    ("Med OCR  + Med LLM",    0.60, "medium", True),
    ("Low OCR  + High LLM",   0.30, "high",   True),
    ("Low OCR  + Low LLM",    0.20, "low",    True),
    ("Perfect",               1.00, "high",   False),
    ("Zero",                  0.00, "low",    True),
]

# ─────────────────────────────────────────────────────────────────────────────
# Section runners
# ─────────────────────────────────────────────────────────────────────────────

def run_validate(args: argparse.Namespace) -> list[dict]:
    from app.services.validation import validate_fields

    results = []

    test_cases = [
        ("Complete valid record – expect 0 errors",       GOOD_RECORD,      0, 0),
        ("Missing required fields – expect 4 errors",     MISSING_REQUIRED, 4, None),
        ("Bad format fields – expect errors + warnings",  BAD_FORMATS,      1, None),
    ]

    _header("validate_fields()")

    for label, data, min_errors, max_errors in test_cases:
        _subheader(label)
        violations = validate_fields(data)
        errors   = [v for v in violations if v.severity == "error"]
        warnings = [v for v in violations if v.severity == "warning"]

        print(f"  Errors   : {red(str(len(errors)))   if errors   else green('0')}")
        print(f"  Warnings : {yellow(str(len(warnings))) if warnings else green('0')}")

        for v in violations:
            col = SEV_COLOR.get(v.severity, grey)
            print(f"    {col('▸')} [{col(v.severity.upper())}] "
                  f"{cyan(v.field)}: {v.message[:80]}")

        ok = len(errors) >= min_errors
        if max_errors is not None:
            ok = ok and len(errors) <= max_errors

        status = PASS if ok else FAIL
        print(f"  → {status}  ({len(violations)} total violation(s))")

        results.append({
            "test": label,
            "errors": len(errors),
            "warnings": len(warnings),
            "violations": [v.to_dict() for v in violations],
            "passed": ok,
        })

    return results


def run_duplicates(args: argparse.Namespace) -> list[dict]:
    from app.services.validation import find_duplicates_in_memory

    _header("find_duplicates_in_memory()")

    threshold = args.fuzzy if args.fuzzy else 85.0

    dup_cases = [
        # (label,                     owner,                 survey, expect_min_matches)
        ("Exact owner + survey",      "Ram Kumar Singh",     "78-B", 1),
        ("Fuzzy owner (typo)",        "Ram Kumar Sing",      "78-B", 1),
        ("Different record",          "Anil Patel",          "500",  0),
        ("Only owner provided",       "Priya Sharma",        None,   1),
        ("Only survey provided",      None,                  "78-B", 1),
        ("Both None – skip",          None,                  None,   0),
    ]

    results = []
    for label, owner, survey, min_expected in dup_cases:
        _subheader(label)
        print(f"  owner_name    : {cyan(str(owner))}")
        print(f"  survey_number : {cyan(str(survey))}")
        print(f"  threshold     : {threshold}")

        matches = find_duplicates_in_memory(
            owner, survey, EXISTING_DOCS, threshold=threshold
        )

        for m in matches:
            print(
                f"    {yellow('▸')} doc #{m.document_id} '{m.filename}'  "
                f"owner_sim={m.owner_similarity:.1f}  "
                f"survey_sim={m.survey_similarity:.1f}  "
                f"combined={green(f'{m.combined_score:.1f}')}"
            )

        ok = len(matches) >= min_expected
        status = PASS if ok else FAIL
        print(f"  → {status}  ({len(matches)} match(es), expected ≥ {min_expected})")

        results.append({
            "test": label,
            "matches": [m.to_dict() for m in matches],
            "passed": ok,
        })

    return results


def run_confidence(args: argparse.Namespace) -> list[dict]:
    from app.services.validation import compute_confidence, should_flag, REVIEW_THRESHOLD

    _header("compute_confidence() + should_flag()")

    threshold = args.threshold if args.threshold else REVIEW_THRESHOLD()
    print(f"  REVIEW_THRESHOLD = {cyan(str(threshold))}")

    col_label = 30
    col_score = 8

    header_row = (
        f"  {'Case':<{col_label}}  {'Score':>{col_score}}  "
        f"{'Flagged?':<10}  {'Expected'}"
    )
    print()
    print(bold(header_row))
    print("  " + "─" * 62)

    results = []
    all_ok = True
    for label, ocr_c, ext_c, expect_flagged in CONFIDENCE_CASES:
        score   = compute_confidence(ocr_c, ext_c)
        flagged = score < threshold

        ok = flagged == expect_flagged
        all_ok = all_ok and ok

        score_col  = (green if score >= 0.75 else yellow if score >= 0.50 else red)(
            f"{score:.4f}"
        )
        flag_col   = red("YES ▲") if flagged else green("no")
        exp_col    = red("flag") if expect_flagged else green("pass")
        status_col = PASS if ok else FAIL

        print(
            f"  {label:<{col_label}}  {score_col:>{col_score}}  "
            f"{flag_col:<10}  {exp_col}  {status_col}"
        )

        results.append({
            "label": label,
            "ocr_confidence": ocr_c,
            "extraction_confidence": ext_c,
            "combined_score": score,
            "flagged": flagged,
            "expected_flagged": expect_flagged,
            "passed": ok,
        })

    print()
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    overall = PASS if all_ok else FAIL
    print(f"  {overall}  {passed}/{total} confidence cases correct")
    return results


def run_build_reports(args: argparse.Namespace) -> list[dict]:
    from app.services.validation import build_field_reports, validate_fields

    _header("build_field_reports() – end-to-end per-field report")

    # Simulate a real extraction result
    ocr_confidences = {k: 0.82 for k in GOOD_RECORD}
    ocr_confidences["survey_number"] = 0.45   # artificially low OCR on this field
    ocr_confidences["mutation_record"] = 0.30

    extraction_confidences = {k: "high" for k in GOOD_RECORD}
    extraction_confidences["mutation_record"] = "low"
    extraction_confidences["registration_info"] = "medium"

    violations = validate_fields(GOOD_RECORD)
    reports = build_field_reports(
        GOOD_RECORD, ocr_confidences, extraction_confidences, violations
    )

    col = max(len(r.field_name) for r in reports) + 2
    print()
    print(bold(f"  {'Field':<{col}}  {'Combined':>8}  {'Flagged?':<10}  {'Ext.Conf':<8}  Value"))
    print("  " + "─" * 70)

    for r in reports:
        score_fn = green if r.combined_confidence >= 0.75 else (
            yellow if r.combined_confidence >= 0.50 else red
        )
        flagged_col = red("YES ▲") if r.is_flagged else green("no")
        val_preview = (r.value or dim("null"))[:30]
        print(
            f"  {r.field_name:<{col}}  "
            f"{score_fn(f'{r.combined_confidence:.4f}'):>8}  "
            f"{flagged_col:<10}  "
            f"{r.extraction_confidence:<8}  {val_preview}"
        )

    flagged_count = sum(1 for r in reports if r.is_flagged)
    print()
    print(f"  Fields flagged for review: {red(str(flagged_count))}/{len(reports)}")
    return [r.to_dict() for r in reports]


# ─────────────────────────────────────────────────────────────────────────────
# Entry-point
# ─────────────────────────────────────────────────────────────────────────────

def main(args: argparse.Namespace) -> int:
    section = args.section

    output: dict = {}

    try:
        if section in (None, "validate"):
            output["validate_fields"] = run_validate(args)
        if section in (None, "duplicates"):
            output["find_duplicates"] = run_duplicates(args)
        if section in (None, "confidence"):
            output["compute_confidence"] = run_confidence(args)
        if section in (None, "reports"):
            output["build_field_reports"] = run_build_reports(args)
    except ImportError as exc:
        print(f"{red('Import error:')} {exc}")
        print("Run from the project root with your virtualenv active.")
        return 1

    # ── Summary ───────────────────────────────────────────────────────────────
    if not args.json:
        print()
        print(bold("═" * 64))
        print(bold("  Summary"))
        print(bold("═" * 64))

        all_passed = True
        for section_name, items in output.items():
            if isinstance(items, list) and items and "passed" in items[0]:
                passed = sum(1 for i in items if i.get("passed"))
                total  = len(items)
                ok     = passed == total
                all_passed = all_passed and ok
                status = PASS if ok else FAIL
                print(f"  {status}  {cyan(section_name)}: {passed}/{total}")

        print()
        print(bold("  Overall: ") + (PASS if all_passed else FAIL))
        print()
        return 0 if all_passed else 2

    # ── JSON output ───────────────────────────────────────────────────────────
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Test validation service with sample land-record data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--section",
        choices=["validate", "duplicates", "confidence", "reports"],
        default=None,
        help="Run only one test section (default: all).",
    )
    p.add_argument(
        "--threshold",
        type=float,
        default=None,
        metavar="FLOAT",
        help="Override REVIEW_THRESHOLD (default from config: 0.75).",
    )
    p.add_argument(
        "--fuzzy",
        type=float,
        default=None,
        metavar="SCORE",
        help="Override FUZZY_THRESHOLD (default from config: 85.0).",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON result (pipe-friendly).",
    )
    return p.parse_args()


if __name__ == "__main__":
    sys.exit(main(_parse_args()))
