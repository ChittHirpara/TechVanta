"""
Validation service unit tests.

No DB or API required — pure function tests.
Covers: field validation rules, duplicate detection (in-memory), confidence scoring.
"""
import pytest
from app.services.validation import (
    validate_fields,
    find_duplicates_in_memory,
    compute_confidence,
    should_flag,
    build_field_reports,
    REQUIRED_FIELDS,
)


# ─────────────────────────────────────────────────────────────────────────────
# validate_fields
# ─────────────────────────────────────────────────────────────────────────────

_GOOD = {
    "owner_name": "Ram Kumar Singh",
    "survey_number": "78-B",
    "khasra_number": "451/2",
    "khata_number": "112",
    "plot_area": "2 Bigha 14 Biswa",
    "village": "Rampur Kalan",
    "tehsil": "Sanganer",
    "district": "Jaipur",
    "land_classification": "Agricultural",
    "ownership_details": "Single owner",
    "mutation_record": "Entry 23",
    "registration_info": "Deed 4521/2019",
}


def test_validate_clean_record_has_no_errors():
    violations = validate_fields(_GOOD)
    errors = [v for v in violations if v.severity == "error"]
    assert errors == [], [v.message for v in errors]


def test_validate_missing_required_fields():
    data = {**_GOOD, "owner_name": None, "survey_number": None, "district": ""}
    violations = validate_fields(data)
    error_fields = {v.field for v in violations if v.severity == "error"}
    assert "owner_name" in error_fields
    assert "survey_number" in error_fields
    assert "district" in error_fields


def test_validate_all_required_fields_missing():
    data = {k: None for k in _GOOD}
    violations = validate_fields(data)
    error_fields = {v.field for v in violations if v.severity == "error"}
    for req in REQUIRED_FIELDS:
        assert req in error_fields, f"'{req}' should be an error"


def test_validate_survey_number_bad_format():
    data = {**_GOOD, "survey_number": "ABC##XYZ"}
    violations = validate_fields(data)
    survey_violations = [v for v in violations if v.field == "survey_number"]
    assert any(v.rule == "format_survey_number" for v in survey_violations)


def test_validate_survey_number_valid_formats():
    valid = ["123", "45/2", "78-B", "12/3A", "4A", "100/1B"]
    for s in valid:
        data = {**_GOOD, "survey_number": s}
        violations = validate_fields(data)
        format_violations = [
            v for v in violations
            if v.field == "survey_number" and v.rule == "format_survey_number"
        ]
        assert format_violations == [], f"'{s}' should be valid but got {format_violations}"


def test_validate_khasra_number_bad_format():
    data = {**_GOOD, "khasra_number": "!@#$"}
    violations = validate_fields(data)
    assert any(
        v.field == "khasra_number" and v.rule == "format_khasra_number"
        for v in violations
    )


def test_validate_plot_area_must_start_with_digit():
    data = {**_GOOD, "plot_area": "large parcel"}
    violations = validate_fields(data)
    assert any(v.field == "plot_area" and v.severity == "error" for v in violations)


def test_validate_plot_area_valid_with_units():
    valid_areas = ["2.5", "1200 sq mt", "2 Bigha 14 Biswa", "1.45 acres", "500"]
    for area in valid_areas:
        data = {**_GOOD, "plot_area": area}
        violations = validate_fields(data)
        area_errors = [
            v for v in violations
            if v.field == "plot_area" and v.severity == "error"
        ]
        assert area_errors == [], f"'{area}' should be valid, got {area_errors}"


def test_validate_short_owner_name_is_warning():
    data = {**_GOOD, "owner_name": "AB"}
    violations = validate_fields(data)
    assert any(
        v.field == "owner_name" and v.severity == "warning"
        for v in violations
    )


def test_validate_missing_recommended_fields_are_warnings():
    data = {**_GOOD, "khasra_number": None, "khata_number": None}
    violations = validate_fields(data)
    warning_fields = {v.field for v in violations if v.severity == "warning"}
    assert "khasra_number" in warning_fields
    assert "khata_number" in warning_fields


# ─────────────────────────────────────────────────────────────────────────────
# Duplicate detection (in-memory)
# ─────────────────────────────────────────────────────────────────────────────

_CANDIDATES = [
    {"document_id": 1, "filename": "deed1.pdf",
     "owner_name": "Ram Kumar Singh",          "survey_number": "78-B"},
    {"document_id": 2, "filename": "deed2.pdf",
     "owner_name": "Ram Kumar Singh S/O Shyam", "survey_number": "78B"},
    {"document_id": 3, "filename": "deed3.pdf",
     "owner_name": "Priya Sharma Devi",         "survey_number": "99/1"},
    {"document_id": 4, "filename": "deed4.pdf",
     "owner_name": "Suresh Gupta",              "survey_number": "200"},
    {"document_id": 5, "filename": "deed5.pdf",
     "owner_name": "",                           "survey_number": "78-B"},
]


def test_duplicates_exact_match():
    matches = find_duplicates_in_memory("Ram Kumar Singh", "78-B", _CANDIDATES)
    ids = {m.document_id for m in matches}
    assert 1 in ids, "Exact match doc should always be found"


def test_duplicates_fuzzy_name_match():
    # Slight typo in name
    matches = find_duplicates_in_memory("Ram Kumar Sing", "78-B", _CANDIDATES)
    ids = {m.document_id for m in matches}
    assert 1 in ids or 2 in ids, "Fuzzy match should find at least one near-match"


def test_duplicates_different_record_not_found():
    matches = find_duplicates_in_memory("Anil Patel", "500/9", _CANDIDATES)
    assert matches == [], f"Unrelated record should return no matches: {matches}"


def test_duplicates_only_owner_provided():
    matches = find_duplicates_in_memory("Priya Sharma", None, _CANDIDATES)
    ids = {m.document_id for m in matches}
    assert 3 in ids


def test_duplicates_only_survey_provided():
    matches = find_duplicates_in_memory(None, "78-B", _CANDIDATES)
    assert len(matches) >= 1


def test_duplicates_both_none_returns_empty():
    matches = find_duplicates_in_memory(None, None, _CANDIDATES)
    assert matches == []


def test_duplicates_custom_threshold():
    # Very high threshold → only exact matches
    matches_high = find_duplicates_in_memory(
        "Ram Kumar Singh", "78-B", _CANDIDATES, threshold=99.0
    )
    matches_low = find_duplicates_in_memory(
        "Ram Kumar Singh", "78-B", _CANDIDATES, threshold=50.0
    )
    assert len(matches_low) >= len(matches_high)


def test_duplicates_sorted_by_score_descending():
    matches = find_duplicates_in_memory("Ram Kumar Singh", "78-B", _CANDIDATES)
    scores = [m.combined_score for m in matches]
    assert scores == sorted(scores, reverse=True)


def test_duplicates_result_fields_populated():
    matches = find_duplicates_in_memory("Ram Kumar Singh", "78-B", _CANDIDATES)
    for m in matches:
        assert 0 <= m.combined_score <= 100
        assert m.document_id > 0
        assert isinstance(m.filename, str)


# ─────────────────────────────────────────────────────────────────────────────
# compute_confidence + should_flag
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("ocr,ext,expected_range", [
    (1.0, "high",   (0.95, 1.00)),   # perfect OCR + perfect LLM → near 1.0
    (0.0, "low",    (0.00, 0.20)),   # worst case → near 0.0
    (0.5, "medium", (0.45, 0.70)),   # mid everything → mid score
    (0.9, "low",    (0.40, 0.60)),   # good OCR but low LLM confidence
    (0.2, "high",   (0.60, 0.80)),   # poor OCR but high LLM confidence
])
def test_compute_confidence_in_expected_range(ocr, ext, expected_range):
    score = compute_confidence(ocr, ext)
    lo, hi = expected_range
    assert lo <= score <= hi, (
        f"compute_confidence({ocr}, {ext!r}) = {score} not in [{lo}, {hi}]"
    )


def test_compute_confidence_clamped_to_0_1():
    # Extreme values should never escape [0, 1]
    assert 0.0 <= compute_confidence(2.0, "high") <= 1.0
    assert 0.0 <= compute_confidence(-1.0, "low") <= 1.0


def test_compute_confidence_unknown_ext_treated_as_low():
    score_unknown = compute_confidence(0.5, "unknown")
    score_low     = compute_confidence(0.5, "low")
    assert score_unknown == score_low


def test_should_flag_below_threshold():
    assert should_flag(0.50) is True
    assert should_flag(0.74) is True


def test_should_flag_above_threshold():
    assert should_flag(0.80) is False
    assert should_flag(1.00) is False


def test_should_flag_at_boundary():
    """Exactly at threshold (0.75) should NOT be flagged (< not <=)."""
    assert should_flag(0.75) is False


# ─────────────────────────────────────────────────────────────────────────────
# build_field_reports
# ─────────────────────────────────────────────────────────────────────────────

def test_build_field_reports_count():
    reports = build_field_reports(
        _GOOD,
        {k: 0.85 for k in _GOOD},
        {k: "high" for k in _GOOD},
    )
    assert len(reports) == len(_GOOD)


def test_build_field_reports_flagged_on_low_confidence():
    # Force low combined confidence by setting both to low
    reports = build_field_reports(
        _GOOD,
        {k: 0.10 for k in _GOOD},   # terrible OCR
        {k: "low" for k in _GOOD},  # terrible LLM
    )
    flagged = [r for r in reports if r.is_flagged]
    assert len(flagged) == len(_GOOD), "All fields should be flagged"


def test_build_field_reports_not_flagged_on_high_confidence():
    reports = build_field_reports(
        _GOOD,
        {k: 0.99 for k in _GOOD},
        {k: "high" for k in _GOOD},
    )
    flagged = [r for r in reports if r.is_flagged]
    assert flagged == [], f"No fields should be flagged: {[r.field_name for r in flagged]}"


def test_build_field_reports_violations_attached():
    bad_data = {**_GOOD, "owner_name": None, "plot_area": "unknown area"}
    violations = validate_fields(bad_data)
    reports = build_field_reports(
        bad_data,
        {k: 0.80 for k in bad_data},
        {k: "high" for k in bad_data},
        violations,
    )
    owner_report = next(r for r in reports if r.field_name == "owner_name")
    area_report  = next(r for r in reports if r.field_name == "plot_area")
    assert len(owner_report.violations) > 0
    assert len(area_report.violations) > 0


def test_should_flag_per_field_override():
    # khasra_number has a higher threshold (0.85). A confidence of 0.80 passes global 0.75 but fails khasra 0.85
    assert should_flag(0.80, field_name="khasra_number") is True
    assert should_flag(0.88, field_name="khasra_number") is False


def test_should_flag_per_field_fallback():
    # Unlisted field falls back to global 0.75
    assert should_flag(0.80, field_name="random_unlisted_field") is False
    assert should_flag(0.70, field_name="random_unlisted_field") is True

