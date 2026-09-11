"""
Tests for the reference-data comparison & fraud-risk engine.

These cover the reported bug: a submitted document whose values differ from the
trusted reference record (khasra 126/3 ⇒ 126/8, area 3.25 ⇒ 4.25 Acres,
co-owner typo) MUST produce mismatches and a non-zero risk level.
"""
from __future__ import annotations

import pytest

from app.services.reference_comparison import (
    ComparisonResult,
    RiskResult,
    compare_to_reference,
    compute_risk,
    full_risk_assessment,
    load_reference_records,
    select_reference_record,
)


@pytest.fixture(scope="module")
def records():
    return load_reference_records()


@pytest.fixture
def nashik_reference() -> dict:
    return {
        "district": "Nashik",
        "tehsil": "Dindori",
        "village": "Karanjwan",
        "survey_number": "126-A",
        "khasra_number": "126/3",
        "khata_number": "307",
        "plot_area": "3.25 Acres",
        "land_classification": "Agricultural - Dry Crop",
        "ownership_details": "Joint ownership - 2 co-owners",
        "mutation_record": "Entry 41, 22-Nov-2021",
        "registration_info": "Deed 7814/2021",
        "owner_name": "Meera Deshmukh",
        "co_owner": "Arjun Deshmukh",
    }


@pytest.fixture
def matching_doc(nashik_reference) -> dict:
    return dict(nashik_reference)


@pytest.fixture
def fraud_doc(nashik_reference) -> dict:
    """The intentional dissimilarity document: khasra + area + co-owner differ."""
    doc = dict(nashik_reference)
    doc["khasra_number"] = "126/8"
    doc["plot_area"] = "4.25 Acres"
    doc["co_owner"] = "Arjun Deshmuk"
    return doc


# ── Reference data loading ────────────────────────────────────────────────

def test_reference_file_loads(records):
    assert records, "trusted reference records file must be loadable"


def test_nashik_record_present(records):
    ids = {r.get("id") for r in records}
    assert "MH-NAS-DIN-KAR-307" in ids


# ── Record selection ──────────────────────────────────────────────────────

def test_select_nashik_record(records, fraud_doc):
    selected = select_reference_record(fraud_doc, records=records)
    assert selected is not None
    assert selected["id"] == "MH-NAS-DIN-KAR-307"


def test_select_none_for_unknown_village(records, nashik_reference):
    doc = dict(nashik_reference)
    doc["village"] = "Unknownville"
    assert select_reference_record(doc, records=records) is None


# ── Fraud document: MUST flag khasra + area ───────────────────────────────

def test_fraud_doc_detects_khasra_mismatch(records, fraud_doc):
    comp = compare_to_reference(fraud_doc, records=records)
    assert comp.matched
    fields = {d.field: d for d in comp.discrepancies}
    assert "khasra_number" in fields
    k = fields["khasra_number"]
    assert k.reference_value == "126/3"
    assert k.submitted_value == "126/8"
    assert k.severity == "error"


def test_fraud_doc_detects_area_mismatch(records, fraud_doc):
    comp = compare_to_reference(fraud_doc, records=records)
    fields = {d.field: d for d in comp.discrepancies}
    assert "plot_area" in fields
    area = fields["plot_area"]
    assert area.reference_value == "3.25 Acres"
    assert area.submitted_value == "4.25 Acres"


def test_fraud_doc_high_risk(records, fraud_doc):
    comp, risk = full_risk_assessment(fraud_doc, records=records)
    assert risk.score >= 65
    assert risk.level == "HIGH"
    assert risk.applicable is True
    assert risk.mismatch_count >= 2
    assert any("khasra_number" in r and "126/3" in r for r in risk.reasons)
    assert any("plot_area" in r and "3.25" in r for r in risk.reasons)


# ── Co-owner typo: review-level, not fatal ────────────────────────────────

def test_co_owner_typo_matches_at_fuzzy_threshold(records, fraud_doc):
    """Arjun Deshmuk vs Arjun Deshmukh (≈96% fuzzy) is tolerated as a match,
    so a single-character typo does not itself force HIGH risk."""
    comp = compare_to_reference(fraud_doc, records=records)
    co = [d for d in comp.discrepancies if d.field == "co_owner"]
    assert co == [], f"expected fuzzy tolerance, got {co}"


# ── Matching document: NO false positives ─────────────────────────────────

def test_matching_doc_no_mismatches(records, matching_doc):
    comp = compare_to_reference(matching_doc, records=records)
    assert comp.matched
    assert comp.discrepancies == []


def test_matching_doc_low_risk(records, matching_doc):
    comp, risk = full_risk_assessment(matching_doc, records=records)
    assert risk.score == 0
    assert risk.level == "LOW"
    assert risk.mismatch_count == 0
    assert risk.applicable is True


def test_matching_doc_across_units(records, nashik_reference):
    """'0.4047 ha' should be treated as equal to '1 acre' (unit-independent)."""
    doc = dict(nashik_reference)
    doc["plot_area"] = "3.25"
    comp = compare_to_reference(doc, records=records)
    # No unit on the submitted side → token_fuzzy fallback; must NOT crash.
    assert comp.reference is not None


# ── No reference record ───────────────────────────────────────────────────

def test_no_reference_not_silently_valid(records, nashik_reference):
    doc = dict(nashik_reference)
    doc["village"] = "Another Village"
    doc["tehsil"] = "Another Tehsil"
    doc["district"] = "Another District"
    comp, risk = full_risk_assessment(doc, records=records)
    assert comp.matched is False
    # Must be explicitly "not applicable" with a NON-ZERO risk — never a
    # fabricated clean/valid result (missing reference ≠ zero mismatches).
    assert risk.applicable is False
    assert risk.score > 0
    assert risk.level != "LOW"
    assert all("reference" in r.lower() for r in risk.reasons)


# ── compute_risk edge handling ────────────────────────────────────────────

def test_compute_risk_no_reference():
    risk = compute_risk(ComparisonResult(reference=None))
    assert risk.applicable is False
    assert risk.score > 0
    assert risk.level != "LOW"


def test_risk_level_enumeration():
    assert RiskResult(0, "LOW", [], 0, True).level == "LOW"
    assert RiskResult(100, "HIGH", [], 3, True).level == "HIGH"