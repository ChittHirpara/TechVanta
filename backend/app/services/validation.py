"""
Validation service for extracted land-record fields.

Public API
──────────
    violations = validate_fields(extracted_dict)
    duplicates = await find_duplicates(owner_name, survey_number, db)
    score      = compute_confidence(ocr_conf, extraction_conf)
    flagged    = score < REVIEW_THRESHOLD
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Literal

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Configuration constants (read from Settings so they can be overridden in .env)
# ─────────────────────────────────────────────────────────────────────────────

def _cfg():
    from app.core.config import get_settings
    return get_settings()


def REVIEW_THRESHOLD() -> float:        # noqa: N802 – callable constant pattern
    """Fields with combined confidence below this are flagged for review."""
    return _cfg().review_threshold


def FUZZY_THRESHOLD() -> float:         # noqa: N802
    """rapidfuzz score (0-100) above which a document is a suspected duplicate."""
    return _cfg().fuzzy_threshold


# ─────────────────────────────────────────────────────────────────────────────
# Types
# ─────────────────────────────────────────────────────────────────────────────

Severity = Literal["error", "warning"]


@dataclass
class RuleViolation:
    """A single validation rule failure."""
    field: str
    rule: str
    message: str
    severity: Severity = "error"

    def to_dict(self) -> dict:
        return {
            "field": self.field,
            "rule": self.rule,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass
class DuplicateMatch:
    """A candidate duplicate document found via fuzzy matching."""
    document_id: int
    filename: str
    owner_name: str
    survey_number: str | None
    owner_similarity: float    # 0–100 rapidfuzz score
    survey_similarity: float   # 0–100 rapidfuzz score (0 if either is None)
    combined_score: float      # weighted average, 0–100

    def to_dict(self) -> dict:
        return {
            "document_id": self.document_id,
            "filename": self.filename,
            "owner_name": self.owner_name,
            "survey_number": self.survey_number,
            "owner_similarity": round(self.owner_similarity, 2),
            "survey_similarity": round(self.survey_similarity, 2),
            "combined_score": round(self.combined_score, 2),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Rule definitions
# ─────────────────────────────────────────────────────────────────────────────

#: Fields that MUST have a non-null, non-empty value
REQUIRED_FIELDS: tuple[str, ...] = (
    "owner_name",
    "survey_number",
    "district",
    "tehsil",
    "village",
)

#: Fields that are important but not strictly required (warning, not error)
RECOMMENDED_FIELDS: tuple[str, ...] = (
    "khasra_number",
    "khata_number",
    "plot_area",
    "land_classification",
)

# Indian land-record number formats:
#   survey_number / khasra_number examples: "123", "45/2", "78-B", "12/3A", "4A/2"
#   Accepts: digits + optional / or - + optional alphanumeric suffix
_LAND_NUMBER_RE = re.compile(
    r"^\d+(?:[/\-]\d*[A-Za-z]?)?[A-Za-z]?$"
)

# plot_area: must START with a digit (may have unit suffix like "Bigha", "acres", "sq mt")
#   Valid: "2.5", "1.45 acres", "2 Bigha 14 Biswa", "1200 sq mt"
#   Invalid: "approx", "unknown", "large area"
_PLOT_AREA_RE = re.compile(r"^\d[\d.,]*")


# ─────────────────────────────────────────────────────────────────────────────
# validate_fields
# ─────────────────────────────────────────────────────────────────────────────

def validate_fields(extracted: dict) -> list[RuleViolation]:
    """
    Run all validation rules against the extracted field dict.

    Args:
        extracted: Mapping of field_name → value (str or None).
                   Typically ``ExtractionResult.flat_values()``.

    Returns:
        List of ``RuleViolation`` objects, empty if all rules pass.
        Errors must be resolved before a document can be marked ``verified``.
        Warnings should be reviewed but do not block verification.
    """
    violations: list[RuleViolation] = []

    # ── Rule 1: Required field presence ──────────────────────────────────────
    for fname in REQUIRED_FIELDS:
        val = extracted.get(fname)
        if not val or not str(val).strip():
            violations.append(RuleViolation(
                field=fname,
                rule="required_field",
                message=f"'{fname}' is required but was not extracted from the document.",
                severity="error",
            ))

    # ── Rule 2: Recommended field presence ───────────────────────────────────
    for fname in RECOMMENDED_FIELDS:
        val = extracted.get(fname)
        if not val or not str(val).strip():
            violations.append(RuleViolation(
                field=fname,
                rule="recommended_field",
                message=f"'{fname}' is missing; document may be incomplete.",
                severity="warning",
            ))

    # ── Rule 3: survey_number format ─────────────────────────────────────────
    survey = extracted.get("survey_number")
    if survey and str(survey).strip():
        s = str(survey).strip()
        if not _LAND_NUMBER_RE.match(s):
            violations.append(RuleViolation(
                field="survey_number",
                rule="format_survey_number",
                message=(
                    f"survey_number '{s}' does not match expected format "
                    r"(e.g. '123', '45/2', '78-B', '12/3A'). "
                    "Found non-standard characters."
                ),
                severity="warning",
            ))

    # ── Rule 4: khasra_number format ─────────────────────────────────────────
    khasra = extracted.get("khasra_number")
    if khasra and str(khasra).strip():
        k = str(khasra).strip()
        if not _LAND_NUMBER_RE.match(k):
            violations.append(RuleViolation(
                field="khasra_number",
                rule="format_khasra_number",
                message=(
                    f"khasra_number '{k}' does not match expected format "
                    r"(e.g. '451', '451/2', '12-A'). "
                    "Found non-standard characters."
                ),
                severity="warning",
            ))

    # ── Rule 5: plot_area must start with a numeric value ────────────────────
    area = extracted.get("plot_area")
    if area and str(area).strip():
        a = str(area).strip()
        if not _PLOT_AREA_RE.match(a):
            violations.append(RuleViolation(
                field="plot_area",
                rule="numeric_plot_area",
                message=(
                    f"plot_area '{a}' does not start with a numeric value. "
                    "Expected formats: '2.5 acres', '1200 sq mt', '2 Bigha 14 Biswa'."
                ),
                severity="error",
            ))

    # ── Rule 6: Suspiciously short owner_name ────────────────────────────────
    owner = extracted.get("owner_name")
    if owner and len(str(owner).strip()) < 3:
        violations.append(RuleViolation(
            field="owner_name",
            rule="min_length_owner_name",
            message=(
                f"owner_name '{owner}' is suspiciously short (< 3 characters). "
                "Possible OCR extraction error."
            ),
            severity="warning",
        ))

    # ── Rule 7: district/tehsil/village length sanity ────────────────────────
    for geo_field in ("district", "tehsil", "village"):
        gval = extracted.get(geo_field)
        if gval and len(str(gval).strip()) > 150:
            violations.append(RuleViolation(
                field=geo_field,
                rule="max_length_geo_field",
                message=(
                    f"'{geo_field}' value exceeds 150 characters — "
                    "likely an OCR extraction error."
                ),
                severity="warning",
            ))

    log.debug(
        "[validation] %d violation(s) found (%d errors, %d warnings)",
        len(violations),
        sum(1 for v in violations if v.severity == "error"),
        sum(1 for v in violations if v.severity == "warning"),
    )
    return violations


# ─────────────────────────────────────────────────────────────────────────────
# find_duplicates
# ─────────────────────────────────────────────────────────────────────────────

async def find_duplicates(
    owner_name: str | None,
    survey_number: str | None,
    db_session,                          # AsyncSession — typed loosely to avoid circular import
    *,
    threshold: float | None = None,
    owner_weight: float = 0.6,
    survey_weight: float = 0.4,
    limit: int = 200,                    # max documents to load for comparison
) -> list[DuplicateMatch]:
    """
    Find existing ``Document`` rows that are likely duplicates of the incoming
    record using rapidfuzz token_sort_ratio for fault-tolerant matching.

    The combined score is a weighted average of owner_name similarity and
    survey_number similarity.  Only matches above ``threshold`` are returned,
    sorted by combined_score descending.

    Args:
        owner_name:    Extracted owner name (may be None → no owner matching).
        survey_number: Extracted survey number (may be None → no number matching).
        db_session:    An open ``AsyncSession``.
        threshold:     Override ``FUZZY_THRESHOLD`` from config (0–100).
        owner_weight:  Weight for owner_name in the combined score (default 0.6).
        survey_weight: Weight for survey_number in the combined score (default 0.4).
        limit:         Max candidate documents to load (for performance).

    Returns:
        List of ``DuplicateMatch``, sorted by ``combined_score`` descending.
        Empty list if no duplicates are found.
    """
    from sqlalchemy import select
    from rapidfuzz import fuzz

    from app.models.document import Document
    from app.models.extracted_field import ExtractedField

    effective_threshold = threshold if threshold is not None else FUZZY_THRESHOLD()

    # Short-circuit: need at least one non-empty field to compare
    clean_owner  = str(owner_name).strip()  if owner_name  else ""
    clean_survey = str(survey_number).strip() if survey_number else ""

    if not clean_owner and not clean_survey:
        log.debug("[validation] find_duplicates: no input to compare, skipping.")
        return []

    # Load candidate documents (limit to keep comparison fast)
    stmt = select(Document).order_by(Document.id.desc()).limit(limit)
    rows = (await db_session.execute(stmt)).scalars().all()
    if not rows:
        return []

    doc_ids = [d.id for d in rows]
    ef_stmt = select(ExtractedField).where(
        ExtractedField.document_id.in_(doc_ids),
        ExtractedField.field_name.in_(["owner_name", "survey_number"]),
    )
    ef_rows = (await db_session.execute(ef_stmt)).scalars().all()

    doc_fields: dict[int, dict[str, str]] = {}
    for ef in ef_rows:
        doc_fields.setdefault(ef.document_id, {})[ef.field_name] = ef.value or ""

    matches: list[DuplicateMatch] = []

    for doc in rows:
        # ── Owner name similarity ─────────────────────────────────────────────
        doc_owner = str(doc_fields.get(doc.id, {}).get("owner_name") or "").strip()
        owner_sim: float = (
            max(
                fuzz.token_sort_ratio(clean_owner, doc_owner),
                fuzz.token_set_ratio(clean_owner, doc_owner),
            )
            if clean_owner and doc_owner
            else 0.0
        )

        # ── Survey number similarity ──────────────────────────────────────────
        doc_survey = str(doc_fields.get(doc.id, {}).get("survey_number") or "").strip()
        survey_sim: float = (
            fuzz.token_sort_ratio(clean_survey, doc_survey)
            if clean_survey and doc_survey
            else 0.0
        )

        # ── Combined score ────────────────────────────────────────────────────
        if clean_owner and clean_survey:
            combined = owner_weight * owner_sim + survey_weight * survey_sim
        elif clean_owner:
            combined = owner_sim       # only owner available
        else:
            combined = survey_sim      # only survey_number available

        if combined >= effective_threshold:
            matches.append(DuplicateMatch(
                document_id=doc.id,
                filename=doc.filename,
                owner_name=doc_owner or "(unknown)",
                survey_number=doc_survey or None,
                owner_similarity=owner_sim,
                survey_similarity=survey_sim,
                combined_score=combined,
            ))

    matches.sort(key=lambda m: m.combined_score, reverse=True)
    log.info(
        "[validation] find_duplicates: %d candidate(s) above threshold %.1f",
        len(matches),
        effective_threshold,
    )
    return matches


def find_duplicates_in_memory(
    owner_name: str | None,
    survey_number: str | None,
    candidates: list[dict],
    *,
    threshold: float | None = None,
    owner_weight: float = 0.6,
    survey_weight: float = 0.4,
) -> list[DuplicateMatch]:
    """
    Synchronous, in-memory version of ``find_duplicates`` for use in scripts,
    unit tests, and batch processing without a live DB session.

    ``candidates`` is a list of dicts with keys:
        document_id, filename, owner_name, survey_number

    Example::

        candidates = [
            {"document_id": 1, "filename": "deed1.pdf",
             "owner_name": "Ram Kumar Singh", "survey_number": "45/2"},
        ]
        matches = find_duplicates_in_memory("Ram Kumar Singh", "45/2", candidates)
    """
    from rapidfuzz import fuzz

    effective_threshold = threshold if threshold is not None else FUZZY_THRESHOLD()
    clean_owner  = str(owner_name).strip()  if owner_name  else ""
    clean_survey = str(survey_number).strip() if survey_number else ""

    if not clean_owner and not clean_survey:
        return []

    matches: list[DuplicateMatch] = []

    for c in candidates:
        doc_owner  = str(c.get("owner_name")  or "").strip()
        doc_survey = str(c.get("survey_number") or "").strip()

        owner_sim: float = (
            max(
                fuzz.token_sort_ratio(clean_owner, doc_owner),
                fuzz.token_set_ratio(clean_owner, doc_owner),
            )
            if clean_owner and doc_owner else 0.0
        )
        survey_sim: float = (
            fuzz.token_sort_ratio(clean_survey, doc_survey)
            if clean_survey and doc_survey else 0.0
        )

        if clean_owner and clean_survey:
            combined = owner_weight * owner_sim + survey_weight * survey_sim
        elif clean_owner:
            combined = owner_sim
        else:
            combined = survey_sim

        if combined >= effective_threshold:
            matches.append(DuplicateMatch(
                document_id=c["document_id"],
                filename=c.get("filename", ""),
                owner_name=doc_owner or "(unknown)",
                survey_number=doc_survey or None,
                owner_similarity=owner_sim,
                survey_similarity=survey_sim,
                combined_score=combined,
            ))

    matches.sort(key=lambda m: m.combined_score, reverse=True)
    return matches


# ─────────────────────────────────────────────────────────────────────────────
# compute_confidence
# ─────────────────────────────────────────────────────────────────────────────

#: LLM extraction confidence string → numeric weight
_EXTRACTION_CONF_MAP: dict[str, float] = {
    "high":   1.00,
    "medium": 0.65,
    "low":    0.30,
}


def compute_confidence(
    ocr_confidence: float,
    extraction_confidence: str,
    *,
    ocr_weight: float | None = None,
    extraction_weight: float | None = None,
) -> float:
    """
    Combine OCR-level and LLM-extraction-level confidence into a single
    0.0–1.0 score for a field.

    Formula::

        score = ocr_weight * ocr_conf + extraction_weight * extraction_conf_numeric

    Default weights (0.40 / 0.60) can be overridden via .env or the function
    arguments.  Weights are re-normalised if they don't sum to 1.

    Args:
        ocr_confidence:       Float 0.0–1.0 from Tesseract avg word confidence.
        extraction_confidence: "high" | "medium" | "low" from the LLM response.
        ocr_weight:           Override OCR_CONFIDENCE_WEIGHT from config.
        extraction_weight:    Override EXTRACTION_CONFIDENCE_WEIGHT from config.

    Returns:
        Combined confidence float clamped to [0.0, 1.0].
    """
    cfg = _cfg()
    w_ocr = ocr_weight if ocr_weight is not None else cfg.ocr_confidence_weight
    w_ext = extraction_weight if extraction_weight is not None else cfg.extraction_confidence_weight

    # Re-normalise if weights don't sum to 1
    total_w = w_ocr + w_ext
    if total_w <= 0:
        return 0.0
    w_ocr /= total_w
    w_ext /= total_w

    # Clamp OCR confidence
    ocr_conf = max(0.0, min(1.0, float(ocr_confidence)))

    # Map extraction confidence string → numeric
    ext_conf = _EXTRACTION_CONF_MAP.get(
        str(extraction_confidence).lower().strip(), 0.30
    )

    score = w_ocr * ocr_conf + w_ext * ext_conf
    return round(max(0.0, min(1.0, score)), 4)


def should_flag(combined_confidence: float) -> bool:
    """
    Return True if the field should be flagged for manual review.

    Uses ``REVIEW_THRESHOLD`` from config (default 0.75).
    """
    return combined_confidence < REVIEW_THRESHOLD()


# ─────────────────────────────────────────────────────────────────────────────
# Convenience: process all fields in one pass
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FieldReport:
    """Full per-field validation + confidence report."""
    field_name: str
    value: str | None
    ocr_confidence: float
    extraction_confidence: str
    combined_confidence: float
    is_flagged: bool
    violations: list[RuleViolation] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "field_name": self.field_name,
            "value": self.value,
            "ocr_confidence": self.ocr_confidence,
            "extraction_confidence": self.extraction_confidence,
            "combined_confidence": self.combined_confidence,
            "is_flagged": self.is_flagged,
            "violations": [v.to_dict() for v in self.violations],
        }


def build_field_reports(
    extracted_values: dict[str, str | None],
    ocr_confidences: dict[str, float],
    extraction_confidences: dict[str, str],
    rule_violations: list[RuleViolation] | None = None,
) -> list[FieldReport]:
    """
    Produce one ``FieldReport`` per field, combining all validation signals.

    Args:
        extracted_values:        {field_name: value} from ``ExtractionResult.flat_values()``.
        ocr_confidences:         {field_name: 0.0–1.0} per-field OCR confidence.
                                 Use the document-level avg if per-field isn't available.
        extraction_confidences:  {field_name: "high"|"medium"|"low"} from LLM result.
        rule_violations:         Pre-computed violations from ``validate_fields()``.
                                 Computed automatically if None.

    Returns:
        List of ``FieldReport``, one per field in ``extracted_values``.
    """
    if rule_violations is None:
        rule_violations = validate_fields(extracted_values)

    # Index violations by field for fast lookup
    violations_by_field: dict[str, list[RuleViolation]] = {}
    for v in rule_violations:
        violations_by_field.setdefault(v.field, []).append(v)

    reports: list[FieldReport] = []
    for fname, value in extracted_values.items():
        ocr_conf  = ocr_confidences.get(fname, 0.5)      # default mid-range if unknown
        ext_conf  = extraction_confidences.get(fname, "low")
        combined  = compute_confidence(ocr_conf, ext_conf)
        flagged   = should_flag(combined)

        reports.append(FieldReport(
            field_name=fname,
            value=value,
            ocr_confidence=ocr_conf,
            extraction_confidence=ext_conf,
            combined_confidence=combined,
            is_flagged=flagged,
            violations=violations_by_field.get(fname, []),
        ))

    return reports
