"""
Document API flow tests.

Covers:
  - Upload → immediate 202 with status=processing
  - GET document with extracted fields embedded
  - Paginated list with status and district filters
  - Field correction (PATCH) by verifier: writes VerificationLog + AuditTrail
  - Verify: blocked when flags remain, succeeds after all cleared
  - Integration push: LRMS and GIS (verified docs only)
  - Role-gating: field_officer cannot PATCH or verify
"""
import io
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.verification_log import VerificationLog
from app.models.audit_trail import AuditTrail


# ─────────────────────────────────────────────────────────────────────────────
# Upload
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_returns_202(client: AsyncClient, admin_token: str):
    """Upload should return 202 immediately with status=processing."""
    pdf_bytes = io.BytesIO(b"%PDF-1.4 mock content")

    with patch("app.api.documents.process_document") as mock_pipeline:
        resp = await client.post(
            "/documents/upload",
            headers={"Authorization": f"Bearer {admin_token}"},
            files={"file": ("deed.pdf", pdf_bytes, "application/pdf")},
            data={"district": "Jaipur", "tehsil": "Sanganer"},
        )

    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["status"] == "processing"
    assert body["filename"] == "deed.pdf"
    assert body["district"] == "Jaipur"
    assert "id" in body
    # Pipeline must be enqueued (not awaited inline)
    mock_pipeline.assert_called_once()


@pytest.mark.asyncio
async def test_upload_unsupported_type(client: AsyncClient, admin_token: str):
    """Non-PDF/image file should be rejected with 415."""
    with patch("app.api.documents.process_document"):
        resp = await client.post(
            "/documents/upload",
            headers={"Authorization": f"Bearer {admin_token}"},
            files={"file": ("data.csv", io.BytesIO(b"a,b,c"), "text/csv")},
        )
    assert resp.status_code == 415


@pytest.mark.asyncio
async def test_upload_requires_auth(client: AsyncClient):
    resp = await client.post(
        "/documents/upload",
        files={"file": ("deed.pdf", io.BytesIO(b"%PDF"), "application/pdf")},
    )
    assert resp.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# GET document detail
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_document_with_fields(
    client: AsyncClient, admin_token: str, seeded_document: dict
):
    """GET /documents/{id} must embed extracted_fields."""
    doc_id = seeded_document["id"]
    resp = await client.get(
        f"/documents/{doc_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == doc_id
    assert body["status"] == "needs_review"
    assert isinstance(body["extracted_fields"], list)
    assert len(body["extracted_fields"]) > 0

    # Flagged field must be present with is_flagged=True
    flagged = [f for f in body["extracted_fields"] if f["is_flagged"]]
    assert len(flagged) == 1
    assert flagged[0]["field_name"] == "khasra_number"

    # Each field must have confidence_score
    for f in body["extracted_fields"]:
        assert "confidence_score" in f
        assert "field_name" in f


@pytest.mark.asyncio
async def test_get_document_not_found(client: AsyncClient, admin_token: str):
    resp = await client.get(
        "/documents/99999",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# Paginated list
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_documents_pagination(
    client: AsyncClient, admin_token: str, seeded_document: dict
):
    resp = await client.get(
        "/documents?page=1&page_size=10",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "total" in body
    assert "items" in body
    assert "page" in body
    assert body["page"] == 1
    assert isinstance(body["items"], list)


@pytest.mark.asyncio
async def test_list_documents_status_filter(
    client: AsyncClient, admin_token: str, seeded_document: dict
):
    resp = await client.get(
        "/documents?status=needs_review",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all(i["status"] == "needs_review" for i in items)


@pytest.mark.asyncio
async def test_list_documents_district_filter(
    client: AsyncClient, admin_token: str, seeded_document: dict
):
    resp = await client.get(
        "/documents?district=Jaipur",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    for item in body["items"]:
        assert "jaipur" in (item["district"] or "").lower()


# ─────────────────────────────────────────────────────────────────────────────
# Field correction (PATCH)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patch_field_clears_flag(
    client: AsyncClient, verifier_token: str,
    seeded_document: dict, db: AsyncSession
):
    """PATCH /documents/{id}/fields/{name} should clear is_flagged."""
    doc_id = seeded_document["id"]
    resp = await client.patch(
        f"/documents/{doc_id}/fields/khasra_number",
        headers={"Authorization": f"Bearer {verifier_token}"},
        json={"value": "451/2", "note": "OCR misread l as 1"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["value"] == "451/2"
    assert body["is_flagged"] is False


@pytest.mark.asyncio
async def test_patch_field_writes_verification_log(
    client: AsyncClient, verifier_token: str,
    seeded_document: dict, db: AsyncSession
):
    """PATCH must write a VerificationLog row with old and new values."""
    doc_id = seeded_document["id"]
    await client.patch(
        f"/documents/{doc_id}/fields/khasra_number",
        headers={"Authorization": f"Bearer {verifier_token}"},
        json={"value": "451/2"},
    )
    log = (
        await db.execute(
            select(VerificationLog)
            .where(VerificationLog.document_id == doc_id)
            .where(VerificationLog.field_name == "khasra_number")
        )
    ).scalar_one_or_none()

    assert log is not None
    assert log.old_value == "45l/2"
    assert log.new_value == "451/2"


@pytest.mark.asyncio
async def test_patch_field_writes_audit_trail(
    client: AsyncClient, verifier_token: str,
    seeded_document: dict, db: AsyncSession
):
    """PATCH must write an AuditTrail row with action='field_corrected'."""
    doc_id = seeded_document["id"]
    await client.patch(
        f"/documents/{doc_id}/fields/khasra_number",
        headers={"Authorization": f"Bearer {verifier_token}"},
        json={"value": "451/2"},
    )
    audit = (
        await db.execute(
            select(AuditTrail)
            .where(AuditTrail.document_id == doc_id)
            .where(AuditTrail.action == "field_corrected")
        )
    ).scalar_one_or_none()
    assert audit is not None
    assert audit.details["field_name"] == "khasra_number"
    assert audit.details["new_value"] == "451/2"


@pytest.mark.asyncio
async def test_patch_field_forbidden_for_officer(
    client: AsyncClient, field_officer_token: str, seeded_document: dict
):
    """field_officer role must receive 403."""
    doc_id = seeded_document["id"]
    resp = await client.patch(
        f"/documents/{doc_id}/fields/khasra_number",
        headers={"Authorization": f"Bearer {field_officer_token}"},
        json={"value": "451/2"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_patch_nonexistent_field(
    client: AsyncClient, verifier_token: str, seeded_document: dict
):
    doc_id = seeded_document["id"]
    resp = await client.patch(
        f"/documents/{doc_id}/fields/nonexistent_field",
        headers={"Authorization": f"Bearer {verifier_token}"},
        json={"value": "anything"},
    )
    assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# Verification flow
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_verify_blocked_by_flagged_fields(
    client: AsyncClient, verifier_token: str, seeded_document: dict
):
    """Verify must return 422 while any field is still flagged."""
    doc_id = seeded_document["id"]
    resp = await client.post(
        f"/documents/{doc_id}/verify",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert resp.status_code == 422
    assert "flagged" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_verify_success_after_clearing_flags(
    client: AsyncClient, verifier_token: str, seeded_document: dict
):
    """Verify succeeds once all flags are cleared via PATCH."""
    doc_id = seeded_document["id"]

    # Clear the one flagged field
    patch_resp = await client.patch(
        f"/documents/{doc_id}/fields/khasra_number",
        headers={"Authorization": f"Bearer {verifier_token}"},
        json={"value": "451/2"},
    )
    assert patch_resp.status_code == 200

    # Now verify
    verify_resp = await client.post(
        f"/documents/{doc_id}/verify",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["status"] == "verified"


@pytest.mark.asyncio
async def test_verify_idempotency_rejected(
    client: AsyncClient, verifier_token: str, seeded_document: dict
):
    """Verifying an already-verified document returns 409."""
    doc_id = seeded_document["id"]

    # Clear flag then verify
    await client.patch(
        f"/documents/{doc_id}/fields/khasra_number",
        headers={"Authorization": f"Bearer {verifier_token}"},
        json={"value": "451/2"},
    )
    await client.post(f"/documents/{doc_id}/verify",
                      headers={"Authorization": f"Bearer {verifier_token}"})

    # Second verify attempt
    resp = await client.post(
        f"/documents/{doc_id}/verify",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_verify_forbidden_for_officer(
    client: AsyncClient, field_officer_token: str, seeded_document: dict
):
    doc_id = seeded_document["id"]
    resp = await client.post(
        f"/documents/{doc_id}/verify",
        headers={"Authorization": f"Bearer {field_officer_token}"},
    )
    assert resp.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# Integration push
# ─────────────────────────────────────────────────────────────────────────────

async def _make_verified_doc(client, verifier_token, seeded_document):
    """Helper: clear flag and verify a seeded document, return doc_id."""
    doc_id = seeded_document["id"]
    await client.patch(
        f"/documents/{doc_id}/fields/khasra_number",
        headers={"Authorization": f"Bearer {verifier_token}"},
        json={"value": "451/2"},
    )
    await client.post(f"/documents/{doc_id}/verify",
                      headers={"Authorization": f"Bearer {verifier_token}"})
    return doc_id


@pytest.mark.asyncio
async def test_lrms_push_verified_doc(
    client: AsyncClient, verifier_token: str, seeded_document: dict
):
    doc_id = await _make_verified_doc(client, verifier_token, seeded_document)
    resp = await client.post(
        f"/integrations/lrms/push/{doc_id}",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["system"] == "lrms"
    assert body["status"] == "accepted"
    assert body["reference_id"].startswith("LRMS-")
    assert body["mock"] is True
    assert body["payload_logged"] is True


@pytest.mark.asyncio
async def test_gis_push_verified_doc(
    client: AsyncClient, verifier_token: str, seeded_document: dict
):
    doc_id = await _make_verified_doc(client, verifier_token, seeded_document)
    resp = await client.post(
        f"/integrations/gis/push/{doc_id}",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["system"] == "gis"
    assert body["status"] == "queued"
    assert body["reference_id"].startswith("GIS-")


@pytest.mark.asyncio
async def test_lrms_push_unverified_doc_rejected(
    client: AsyncClient, verifier_token: str, seeded_document: dict
):
    """Pushing a needs_review document must return 422."""
    doc_id = seeded_document["id"]   # still needs_review
    resp = await client.post(
        f"/integrations/lrms/push/{doc_id}",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert resp.status_code == 422
    assert "verified" in resp.json()["detail"].lower()
