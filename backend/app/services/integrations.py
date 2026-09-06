"""
Government system integration service layer.

Provides payload builders and mock push functions for:
  - LRMS  (Land Record Management System)
  - GIS   (Geographic Information System)

When real endpoints are available, replace the _mock_push_* functions with
actual HTTP calls — the routers and audit logic stay identical.
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

# ─────────────────────────────────────────────────────────────────────────────
# Result type
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class IntegrationPushResult:
    """Returned by every mock push function."""
    system: str                      # "lrms" | "gis"
    document_id: int
    reference_id: str                # fake gov-system reference number
    status: str                      # "accepted" | "queued" | "failed"
    payload: dict[str, Any]          # the exact payload that *would* be sent
    pushed_at: str                   # ISO-8601 UTC timestamp
    mock: bool = True                # False when wired to a real endpoint

    def to_dict(self) -> dict:
        return {
            "system":       self.system,
            "document_id":  self.document_id,
            "reference_id": self.reference_id,
            "status":       self.status,
            "payload":      self.payload,
            "pushed_at":    self.pushed_at,
            "mock":         self.mock,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Reference-ID generators
# ─────────────────────────────────────────────────────────────────────────────

def _lrms_ref(document_id: int) -> str:
    """
    Generate a fake LRMS reference number in the format used by many
    Indian state land record departments:
      LRMS-<YYYY>-<DOC_ID:06d>-<4-hex-checksum>
    """
    year = datetime.now(timezone.utc).year
    checksum = hashlib.sha1(
        f"lrms:{document_id}:{uuid.uuid4()}".encode()
    ).hexdigest()[:4].upper()
    return f"LRMS-{year}-{document_id:06d}-{checksum}"


def _gis_ref(document_id: int, district: str | None) -> str:
    """
    Generate a fake GIS reference number:
      GIS-<DISTRICT_CODE>-<6-hex-UUID>
    District code is the first 3 uppercase letters of the district name.
    """
    district_code = (district or "UNK")[:3].upper()
    uid = uuid.uuid4().hex[:6].upper()
    return f"GIS-{district_code}-{uid}"


# ─────────────────────────────────────────────────────────────────────────────
# Payload builders
# ─────────────────────────────────────────────────────────────────────────────

def build_lrms_payload(
    doc_id: int,
    filename: str,
    district: str | None,
    tehsil: str | None,
    village: str | None,
    uploaded_by: int | None,
    verified_at: str,
    fields: dict[str, str | None],
) -> dict[str, Any]:
    """
    Construct the payload structure expected by a typical Indian state LRMS API.

    Real systems commonly use XML or a REST/JSON envelope; this follows
    the JSON envelope pattern used by newer NIC-based portals.
    """
    return {
        "api_version": "1.0",
        "request_type": "LAND_RECORD_PUSH",
        "source_system": "LandRecordDigitizer/v0.1",
        "submission": {
            "document_id":   doc_id,
            "filename":      filename,
            "submitted_at":  verified_at,
            "submitted_by":  uploaded_by,
        },
        "geography": {
            "district": district,
            "tehsil":   tehsil,
            "village":  village,
        },
        "land_record": {
            "owner_name":        fields.get("owner_name"),
            "survey_number":     fields.get("survey_number"),
            "khasra_number":     fields.get("khasra_number"),
            "khata_number":      fields.get("khata_number"),
            "plot_area":         fields.get("plot_area"),
            "land_classification": fields.get("land_classification"),
            "ownership_details": fields.get("ownership_details"),
            "mutation_record":   fields.get("mutation_record"),
            "registration_info": fields.get("registration_info"),
        },
    }


def build_gis_payload(
    doc_id: int,
    district: str | None,
    tehsil: str | None,
    village: str | None,
    verified_at: str,
    fields: dict[str, str | None],
) -> dict[str, Any]:
    """
    Construct the payload for a GIS portal.

    GIS systems primarily care about geographic identifiers and area
    so they can update spatial layers (parcel boundaries, land-use maps).
    """
    return {
        "api_version": "1.0",
        "request_type": "PARCEL_UPDATE",
        "source_system": "LandRecordDigitizer/v0.1",
        "submitted_at": verified_at,
        "parcel": {
            "survey_number":       fields.get("survey_number"),
            "khasra_number":       fields.get("khasra_number"),
            "plot_area":           fields.get("plot_area"),
            "land_classification": fields.get("land_classification"),
            "owner_name":          fields.get("owner_name"),
        },
        "location": {
            "district": district,
            "tehsil":   tehsil,
            "village":  village,
        },
        "metadata": {
            "source_document_id": doc_id,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Mock push functions  (swap these for real HTTP calls when ready)
# ─────────────────────────────────────────────────────────────────────────────

def mock_push_lrms(
    document_id: int,
    district: str | None,
    payload: dict[str, Any],
) -> IntegrationPushResult:
    """
    Simulate an LRMS push.  Returns a realistic-looking acceptance response.

    To go live, replace this function body with:
        response = httpx.post(settings.lrms_endpoint, json=payload, ...)
        return IntegrationPushResult(mock=False, ...)
    """
    return IntegrationPushResult(
        system="lrms",
        document_id=document_id,
        reference_id=_lrms_ref(document_id),
        status="accepted",
        payload=payload,
        pushed_at=datetime.now(timezone.utc).isoformat(),
        mock=True,
    )


def mock_push_gis(
    document_id: int,
    district: str | None,
    payload: dict[str, Any],
) -> IntegrationPushResult:
    """
    Simulate a GIS push.  Returns a realistic-looking queued response
    (GIS updates are typically asynchronous in real portals).
    """
    return IntegrationPushResult(
        system="gis",
        document_id=document_id,
        reference_id=_gis_ref(document_id, district),
        status="queued",
        payload=payload,
        pushed_at=datetime.now(timezone.utc).isoformat(),
        mock=True,
    )
