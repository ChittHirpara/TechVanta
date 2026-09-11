"""
Reference-data comparison & fraud-risk engine.

Purpose
───────
Compares the LLM-extracted field values of a submitted land-record document
against a *trusted reference record* loaded from a project file
(`app/data/reference_records.json`).  Produces a field-by-field discrepancy
report and a risk score/level that drives both the pipeline status and the
API response.

Architecture (preserves the existing pipeline)
──────────────────────────────────────────────
    extracted fields (dict) + document geo
        → load_reference_records()          (file-based, cached)
        → select_reference_record()         (jurisdiction + parcel identifiers)
        → normalize                     (strict / numeric / fuzzy per field)
        → compare per field spec        → FieldDiscrepancy[]
        → compute risk                  → score (0–100), level, reasons

Comparison modes (generic, no hard-coded record values)
────────────────────────────────────────────────────────
    strict      — exact, after whitespace/case normalisation. Used for land
                  identifiers (Survey/Khasra/Khata numbers), where 126/3 and
                  126/8 MUST never compare equal.
    numeric     — parses the numeric value with unit conversion to a common
                  metric before comparing.  3.25 Acres ≠ 4.25 Acres.
    fuzzy       — rapidfuzz ratio/token_sort/token_set (max). Used for names
                  and free-text descriptors.  Small typos (Arjun Deshmuk vs
                  Arjun Deshmukh) are tolerated at REVIEW_LEVEL_FUZZY_SCORE.
    token_fuzzy — fuzzy match on the alphanumeric core tokens only, so dates
                  and entry/deed numbers dominate over OCR noise.

Every field spec carries a risk weight; mismatches accumulate points.
A mismatch in any critical identifier (survey/khasra/plot area) raises the
risk level to HIGH regardless of the accumulated weight.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Reference data file location (project-file based, no database)
# ─────────────────────────────────────────────────────────────────────────────

_REFERENCE_FILE = (
    Path(__file__).resolve().parent.parent / "data" / "reference_records.json"
)


@lru_cache(maxsize=1)
def load_reference_records() -> list[dict[str, Any]]:
    """
    Load all trusted reference records from the project data file (cached).

    Returns:
        A list of record dicts, or ``[]`` if the file is missing/unparseable
        (logged, never raised — a missing reference file must not crash the
        document pipeline).
    """
    if not _REFERENCE_FILE.exists():
        log.error("[ref] reference records file not found: %s", _REFERENCE_FILE)
        return []
    try:
        payload = json.loads(_REFERENCE_FILE.read_text(encoding="utf-8"))
        records = payload.get("records", [])
        log.info("[ref] loaded %d trusted reference record(s) from %s",
                 len(records), _REFERENCE_FILE)
        return records
    except Exception as exc:  # noqa: BLE001 – never let bad ref data crash the pipeline
        log.error("[ref] failed to parse reference records %s: %s", _REFERENCE_FILE, exc)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Types
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FieldDiscrepancy:
    """A single reference-vs-submitted field comparison result."""
    field: str
    mode: str                     # strict | numeric | fuzzy | token_fuzzy
    severity: str                 # error | warning
    reference_value: str | None
    submitted_value: str | None
    similarity: float | None      # 0–100 (only for fuzzy modes)
    reason: str

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "field": self.field,
            "mode": self.mode,
            "severity": self.severity,
            "reference_value": self.reference_value,
            "submitted_value": self.submitted_value,
            "reason": self.reason,
        }
        if self.similarity is not None:
            d["similarity"] = round(self.similarity, 2)
        return d


@dataclass
class ComparisonResult:
    """Full comparison outcome for one document."""
    reference: dict[str, Any] | None
    discrepancies: list[FieldDiscrepancy] = field(default_factory=list)
    compared: list[str] = field(default_factory=list)

    @property
    def matched(self) -> bool:
        return self.reference is not None

    def to_dict(self) -> dict:
        return {
            "reference_matched": self.matched,
            "reference_id": (self.reference or {}).get("id"),
            "reference_jurisdiction": {
                k: (self.reference or {}).get(k)
                for k in ("district", "tehsil", "village")
            },
            "compared_fields": self.compared,
            "mismatches": [d.to_dict() for d in self.discrepancies],
            "mismatch_count": len(self.discrepancies),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Field comparison spec table (generic; applies to any land record)
# ─────────────────────────────────────────────────────────────────────────────

#: (reference key, extracted key, mode, weight, severity on mismatch)
#: Keep the extracted key identical to the reference key so key-name mismatches
#: cannot silently drop a field.
_COMPARISON_SPECS: tuple[tuple[str, str, str, int, str], ...] = (
    ("khasra_number",        "khasra_number",        "strict",      22, "error"),
    ("survey_number",        "survey_number",        "strict",      18, "error"),
    ("khata_number",         "khata_number",         "strict",      12, "error"),
    ("plot_area",            "plot_area",            "numeric",     14, "error"),
    ("owner_name",           "owner_name",           "fuzzy",       10, "error"),
    ("co_owner",             "co_owner",             "fuzzy",        6, "warning"),
    ("land_classification",  "land_classification",  "fuzzy",        4, "warning"),
    ("mutation_record",      "mutation_record",      "token_fuzzy",  5, "warning"),
    ("registration_info",    "registration_info",    "token_fuzzy",  5, "warning"),
    ("ownership_details",    "ownership_details",    "fuzzy",        4, "warning"),
)

#: Fields whose mismatch is treated as a critical, high-risk tamper signal.
_CRITICAL_FIELDS = {"survey_number", "khasra_number", "plot_area"}

#: Fuzzy score (0–100) at/above which a fuzzy field is treated as a match.
FUZZY_MATCH_THRESHOLD = 88.0

#: Reference selection requires at least this match score before a record wins.
_SELECTION_THRESHOLD = 6.0

#: Risk levels
RISK_LEVELS = ("LOW", "MEDIUM", "HIGH")


# ─────────────────────────────────────────────────────────────────────────────
# Normalisation helpers
# ─────────────────────────────────────────────────────────────────────────────

def _norm_strict(value: str | None) -> str:
    """Identifier normalisation — case + whitespace only. Preserves '/', '-', '.'."""
    return re.sub(r"\s+", "", str(value or "").strip().upper())


def _norm_lower(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


#: Indian land area units → square metres (coarse but consistent)
_AREA_UNITS_TO_SQM: dict[str, float] = {
    "acre":    4046.856,
    "acres":   4046.856,
    "hectare": 10000.0,
    "ha":      10000.0,
    "bigha":   2529.285,
    "sq mt":   1.0,
    "sqm":     1.0,
    "sq meter": 1.0,
    "sqmtr":    1.0,
    "m2":       1.0,
}


def _parse_area_sqm(value: str | None) -> float | None:
    """Return area in square metres, or None if it cannot be parsed numerically."""
    if not value or not str(value).strip():
        return None
    raw = _norm_lower(value)
    m = re.search(r"(\d+(?:\.\d+)?)", raw)
    if not m:
        return None
    number = float(m.group(1))
    unit_sqm: float | None = None
    for unit, sqm in _AREA_UNITS_TO_SQM.items():
        # Longest-first ensures "sq meter" wins over "sq mt"/"mt"
        if unit in raw:
            unit_sqm = sqm
    if unit_sqm is None:
        return None
    return round(number * unit_sqm, 4)


def _norm_token_core(value: str | None) -> list[str]:
    """Alphanumeric tokens only — lets dates/entry/deed numbers dominate."""
    return re.findall(r"[a-z0-9]+", _norm_lower(value or ""))


# ─────────────────────────────────────────────────────────────────────────────
# Fuzzy comparison helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fuzzy_score(left: str, right: str) -> float:
    """Best-of rapidfuzz score (0–100) between two strings."""
    from rapidfuzz import fuzz
    a = _norm_lower(left)
    b = _norm_lower(right)
    if not a or not b:
        return 0.0
    return max(
        fuzz.ratio(a, b),
        fuzz.token_sort_ratio(a, b),
        fuzz.token_set_ratio(a, b),
    )


def _token_fuzzy_score(left: str, right: str) -> float:
    from rapidfuzz import fuzz
    a = " ".join(_norm_token_core(left))
    b = " ".join(_norm_token_core(right))
    if not a or not b:
        return 0.0
    return fuzz.token_set_ratio(a, b)


# ─────────────────────────────────────────────────────────────────────────────
# Reference record selection
# ─────────────────────────────────────────────────────────────────────────────

def _record_geo(record: dict) -> dict[str, str]:
    return {
        "district": _norm_lower(record.get("district")),
        "tehsil":   _norm_lower(record.get("tehsil")),
        "village":  _norm_lower(record.get("village")),
    }


def _selection_score(record: dict, geo: dict[str, str], extracted: dict) -> float:
    """
    Score how well a reference record matches the incoming document.
    Exact geography is weighted heavily; parcel identifiers add credibility.
    """
    score = 0.0
    rec_geo = _record_geo(record)

    for key in ("district", "tehsil", "village"):
        ref = rec_geo.get(key, "")
        ext = geo.get(key, "")
        if not ref or not ext:
            continue
        if ref == ext:
            score += 3.0
        elif _fuzzy_score(ref, ext) >= 80.0:
            score += 1.5

    for key in ("survey_number", "khata_number", "khasra_number"):
        ref = _norm_strict(record.get(key))
        ext = _norm_strict(extracted.get(key))
        if not ref or not ext:
            continue
        if ref == ext:
            score += 2.0
        elif _fuzzy_score(ref, ext) >= 70.0:
            score += 1.0

    return score


def select_reference_record(
    extracted: dict[str, Any],
    document: Any | None = None,
    *,
    records: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """
    Select the best trusted reference record for an extracted document.

    Geometry is taken from the extracted fields first, falling back to the
    Document row (which may carry district/tehsil/village from the upload form).

    Returns ``None`` when no reference record reaches the selection threshold —
    the caller should then treat the document as "no trusted baseline" rather
    than fabricate mismatches.
    """
    if records is None:
        records = load_reference_records()
    if not records:
        return None

    geo = {
        "district": _norm_lower(extracted.get("district") or getattr(document, "district", None)),
        "tehsil":   _norm_lower(extracted.get("tehsil") or getattr(document, "tehsil", None)),
        "village":  _norm_lower(extracted.get("village") or getattr(document, "village", None)),
    }

    best: dict[str, Any] | None = None
    best_score = -1.0
    for record in records:
        # Village is the strongest locality anchor — a record from a different
        # village must NEVER win, even if parcel numbers coincide.
        rec_village = _norm_lower(record.get("village"))
        ext_village = geo.get("village")
        if rec_village and ext_village:
            if rec_village != ext_village and _fuzzy_score(rec_village, ext_village) < 85.0:
                log.debug("[ref] skipping %s — village %r != %r",
                          record.get("id"), rec_village, ext_village)
                continue

        score = _selection_score(record, geo, extracted)
        log.debug("[ref] candidate %s score=%.1f", record.get("id"), score)
        if score > best_score:
            best, best_score = record, score

    if best is not None and best_score >= _SELECTION_THRESHOLD:
        log.info(
            "[ref] selected record %s (score=%.1f) for district=%r tehsil=%r village=%r",
            best.get("id"), best_score, geo["district"], geo["tehsil"], geo["village"],
        )
        return best

    log.info(
        "[ref] no trusted reference record selected "
        "(best score=%.1f < %.1f) for district=%r tehsil=%r village=%r",
        best_score, _SELECTION_THRESHOLD, geo["district"], geo["tehsil"], geo["village"],
    )
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Comparison engine
# ─────────────────────────────────────────────────────────────────────────────

def _co_owner_from_ownership(details: str | None) -> str | None:
    """Best-effort: pull a co-owner name from ownership_details free text."""
    if not details:
        return None
    m = re.search(
        r"(?:co[- ]?owner[s]?|joint owner)[\s:]*[-–—]*\s*([A-Za-z][A-Za-z .'\-]*)",
        details,
        re.IGNORECASE,
    )
    return m.group(1).strip() if m else None


def _compare_field(
    ref_key: str,
    ext_key: str,
    mode: str,
    severity: str,
    reference: dict[str, Any],
    extracted: dict[str, Any],
) -> FieldDiscrepancy | None:
    """
    Compare a single field.  Returns None when the field matches (or cannot
    be compared because the reference field is itself empty).
    """
    ref_value = reference.get(ref_key)
    sub_value = extracted.get(ext_key)

    # Best-effort co-owner: extraction schema may not emit co_owner directly,
    # but the LLM drops co-owner names inside ownership_details.
    if ext_key == "co_owner" and not sub_value:
        sub_value = _co_owner_from_ownership(extracted.get("ownership_details"))

    ref_norm = str(ref_value or "").strip()
    sub_norm = str(sub_value or "").strip()

    log.debug(
        "[normalize] field=%s reference=%r submitted=%r (mode=%s)",
        ext_key, ref_value if ref_key == ext_key else ref_value, sub_value, mode,
    )

    # Reference has no value for this field → cannot judge, skip.
    if not ref_norm:
        return None

    # Submitted side missing while reference has one → genuine mismatch.
    if not sub_norm:
        reason = f"'{ext_key}' was not extracted but the trusted record has '{ref_value}'."
        log.info("[comparison] field=%s result=%s", ext_key, "MISMATCH")
        log.info("[risk] field=%s severity=%s reason=%s", ext_key, severity, reason)
        return FieldDiscrepancy(
            field=ext_key, mode=mode, severity=severity,
            reference_value=str(ref_value), submitted_value=None,
            similarity=0.0, reason=reason,
        )

    # ── mode: strict ────────────────────────────────────────────────────────
    if mode == "strict":
        lhs, rhs = _norm_strict(ref_value), _norm_strict(sub_value)
        log.info(
            "[comparison] field=%s mode=strict '%s' vs '%s' → %s",
            ext_key, lhs, rhs, "MATCH" if lhs == rhs else "MISMATCH",
        )
        if lhs == rhs:
            return None
        return FieldDiscrepancy(
            field=ext_key, mode=mode, severity=severity,
            reference_value=str(ref_value), submitted_value=str(sub_value),
            similarity=None,
            reason=(
                f"Identifier mismatch: reference '{ref_value}' != submitted "
                f"'{sub_value}'. Land identifiers must match the trusted record exactly."
            ),
        )

    # ── mode: numeric (area etc.) ───────────────────────────────────────────
    if mode == "numeric":
        lhs = _parse_area_sqm(ref_value)
        rhs = _parse_area_sqm(sub_value)
        # Both sides parse → compare numerically (unit-independent, so
        # '0.4047 ha' vs '1 acre' correctly compare equal).
        if lhs is not None and rhs is not None:
            log.info(
                "[comparison] field=%s mode=numeric %.4f sqm vs %.4f sqm → %s",
                ext_key, lhs, rhs, "MATCH" if abs(lhs - rhs) < 0.5 else "MISMATCH",
            )
            if abs(lhs - rhs) < 0.5:
                return None
            return FieldDiscrepancy(
                field=ext_key, mode=mode, severity=severity,
                reference_value=str(ref_value), submitted_value=str(sub_value),
                similarity=None,
                reason=(
                    f"Area mismatch: trusted record '{ref_value}' != submitted "
                    f"'{sub_value}'. Declared parcel area does not match the "
                    "reference survey measurement."
                ),
            )
        # Not numerically comparable → fall through to token fuzzy on text.
        mode = "token_fuzzy"

    # ── mode: fuzzy / token_fuzzy ───────────────────────────────────────────
    if mode == "fuzzy":
        sim = _fuzzy_score(ref_value, sub_value)
        log.info(
            "[comparison] field=%s mode=fuzzy similarity=%.1f → %s",
            ext_key, sim, "MATCH" if sim >= FUZZY_MATCH_THRESHOLD else "MISMATCH",
        )
        if sim >= FUZZY_MATCH_THRESHOLD:
            return None
        return FieldDiscrepancy(
            field=ext_key, mode=mode, severity=severity,
            reference_value=str(ref_value), submitted_value=str(sub_value),
            similarity=sim,
            reason=(
                f"Possible mismatch (similarity {sim:.0f}%): reference "
                f"'{ref_value}' vs submitted '{sub_value}'. Review manually."
            ),
        )

    if mode == "token_fuzzy":
        sim = _token_fuzzy_score(ref_value, sub_value)
        log.info(
            "[comparison] field=%s mode=token_fuzzy similarity=%.1f → %s",
            ext_key, sim, "MATCH" if sim >= FUZZY_MATCH_THRESHOLD else "MISMATCH",
        )
        if sim >= FUZZY_MATCH_THRESHOLD:
            return None
        return FieldDiscrepancy(
            field=ext_key, mode=mode, severity=severity,
            reference_value=str(ref_value), submitted_value=str(sub_value),
            similarity=sim,
            reason=(
                f"Record text differs (similarity {sim:.0f}%): reference "
                f"'{ref_value}' vs submitted '{sub_value}'. Review manually."
            ),
        )

    return None


def compare_to_reference(
    extracted: dict[str, Any],
    document: Any | None = None,
    *,
    records: list[dict[str, Any]] | None = None,
) -> ComparisonResult:
    """
    Compare extracted field values against the selected trusted reference record.

    Args:
        extracted:  Flat dict of extracted fields (``ExtractionResult.flat_values()``
                    or the persisted ``field_name → value`` map).
        document:   Optional Document row used for geo fall-back in selection.
        records:    Optional override list of reference records (for tests).

    Returns:
        ``ComparisonResult`` with all field outcomes.  If no reference record
        is matched, ``discrepancies`` is empty and ``reference`` is None.
    """
    if records is None:
        records = load_reference_records()
    if not records:
        log.warning("[comparison] skipping — no trusted reference records available.")
        return ComparisonResult(reference=None)

    reference = select_reference_record(extracted, document=document, records=records)
    if reference is None:
        return ComparisonResult(reference=None)

    discrepancies: list[FieldDiscrepancy] = []
    compared: list[str] = []

    for ref_key, ext_key, mode, _weight, severity in _COMPARISON_SPECS:
        compared.append(ext_key)
        log.info(
            "[reference] field=%s value=%r", ref_key, reference.get(ref_key),
        )
        log.info(
            "[extracted] field=%s value=%r", ext_key, extracted.get(ext_key),
        )
        d = _compare_field(
            ref_key, ext_key, mode, severity, reference, extracted,
        )
        if d is not None:
            discrepancies.append(d)
            log.info(
                "[risk] field=%s severity=%s points=n/a reason=%s",
                d.field, d.severity, d.reason,
            )

    log.info(
        "[comparison] %d/%d field(s) matched reference record %s; %d discrepancy(s)",
        len(compared) - len(discrepancies), len(compared),
        reference.get("id"), len(discrepancies),
    )
    return ComparisonResult(
        reference=reference,
        discrepancies=discrepancies,
        compared=compared,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Risk engine
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RiskResult:
    """Final risk assessment for a document."""
    score: int
    level: str
    reasons: list[str]
    mismatch_count: int
    applicable: bool        # False when no trusted reference record was matched

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "level": self.level,
            "reasons": self.reasons,
            "mismatch_count": self.mismatch_count,
            "applicable": self.applicable,
        }


def compute_risk(comparison: ComparisonResult) -> RiskResult:
    """
    Convert a ComparisonResult into a risk score (0–100), level, and reasons.

    Rules:
      - each mismatch adds its field weight to the score (capped at 100);
      - any critical identifier mismatch (survey/khasra/plot area) forces HIGH;
      - no reference record matched ⇒ LOW with an explanatory reason and
        ``applicable=False`` (NOT silently "valid", and NOT fabricated risk).
    """
    if not comparison.matched:
        reason = (
            "No trusted reference record matched the document's jurisdiction/parcel. "
            "Cross-check against the revenue register is required before final verification."
        )
        return RiskResult(
            score=0, level="LOW", reasons=[reason],
            mismatch_count=0, applicable=False,
        )

    meta = {spec[1]: spec for spec in _COMPARISON_SPECS}
    total = 0
    reasons: list[str] = []
    critical_hit = False

    for d in comparison.discrepancies:
        w = meta.get(d.field, (None, d.field, "fuzzy", 0, "warning"))[3]
        total += w
        critical_hit = critical_hit or (d.field in _CRITICAL_FIELDS)
        severity_label = "HIGH" if d.severity == "error" else "REVIEW"
        reasons.append(f"[{severity_label}] {d.field}: {d.reason}")
        log.info("[risk] field=%s points=%s severity=%s", d.field, w, d.severity)

    if critical_hit and total < 70:
        log.info("[risk] critical identifier mismatch detected → floor score to 70")
        total = 70
    total = min(100, total)

    if total == 0:
        level = "LOW"
        reasons.append("No discrepancies found against the trusted reference record.")
    elif total >= 65 or critical_hit:
        level = "HIGH"
    elif total >= 35:
        level = "MEDIUM"
    else:
        level = "LOW"

    log.info("[risk] score=%d level=%s mismatches=%d", total, level, len(comparison.discrepancies))
    return RiskResult(
        score=total,
        level=level,
        reasons=reasons,
        mismatch_count=len(comparison.discrepancies),
        applicable=True,
    )


def full_risk_assessment(
    extracted: dict[str, Any],
    document: Any | None = None,
    *,
    records: list[dict[str, Any]] | None = None,
) -> tuple[ComparisonResult, RiskResult]:
    """Convenience: run selection + comparison + risk in one call."""
    comparison = compare_to_reference(extracted, document=document, records=records)
    risk = compute_risk(comparison)
    return comparison, risk