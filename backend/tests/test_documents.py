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
            "/api/v1/documents/upload",
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
            "/api/v1/documents/upload",
            headers={"Authorization": f"Bearer {admin_token}"},
            files={"file": ("data.csv", io.BytesIO(b"a,b,c"), "text/csv")},
        )
    assert resp.status_code == 415


@pytest.mark.asyncio
async def test_upload_requires_auth(client: AsyncClient):
    resp = await client.post(
        "/api/v1/documents/upload",
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
    """GET /api/v1/documents/{id} must embed extracted_fields."""
    doc_id = seeded_document["id"]
    resp = await client.get(
        f"/api/v1/documents/{doc_id}",
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
        "/api/v1/documents/99999",
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
        "/api/v1/documents?page=1&page_size=10",
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
        "/api/v1/documents?status=needs_review",
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
        "/api/v1/documents?district=Jaipur",
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
    """PATCH /api/v1/documents/{id}/fields/{name} should clear is_flagged."""
    doc_id = seeded_document["id"]
    resp = await client.patch(
        f"/api/v1/documents/{doc_id}/fields/khasra_number",
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
        f"/api/v1/documents/{doc_id}/fields/khasra_number",
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
        f"/api/v1/documents/{doc_id}/fields/khasra_number",
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
        f"/api/v1/documents/{doc_id}/fields/khasra_number",
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
        f"/api/v1/documents/{doc_id}/fields/nonexistent_field",
        headers={"Authorization": f"Bearer {verifier_token}"},
        json={"value": "anything"},
    )
    assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# Verification flow
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_verify_blocked_by_zero_extracted_fields(
    client: AsyncClient, verifier_token: str, db: AsyncSession
):
    """Verify must return 422 if a document has zero extracted fields."""
    from app.models.document import Document, DocumentStatus

    doc = Document(
        filename="empty_doc.pdf",
        storage_path="/tmp/empty_doc.pdf",
        status=DocumentStatus.needs_review,
        district="Jaipur",
        tehsil="Sanganer",
        village="Empty Village",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    resp = await client.post(
        f"/api/v1/documents/{doc.id}/verify",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert resp.status_code == 422
    assert "zero extracted entity fields" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_verify_blocked_by_flagged_fields(
    client: AsyncClient, verifier_token: str, seeded_document: dict
):
    """Verify must return 422 while any field is still flagged."""
    doc_id = seeded_document["id"]
    resp = await client.post(
        f"/api/v1/documents/{doc_id}/verify",
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
        f"/api/v1/documents/{doc_id}/fields/khasra_number",
        headers={"Authorization": f"Bearer {verifier_token}"},
        json={"value": "451/2"},
    )
    assert patch_resp.status_code == 200

    # Now verify
    verify_resp = await client.post(
        f"/api/v1/documents/{doc_id}/verify",
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
        f"/api/v1/documents/{doc_id}/fields/khasra_number",
        headers={"Authorization": f"Bearer {verifier_token}"},
        json={"value": "451/2"},
    )
    await client.post(f"/api/v1/documents/{doc_id}/verify",
                      headers={"Authorization": f"Bearer {verifier_token}"})

    # Second verify attempt
    resp = await client.post(
        f"/api/v1/documents/{doc_id}/verify",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_verify_forbidden_for_officer(
    client: AsyncClient, field_officer_token: str, seeded_document: dict
):
    doc_id = seeded_document["id"]
    resp = await client.post(
        f"/api/v1/documents/{doc_id}/verify",
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
        f"/api/v1/documents/{doc_id}/fields/khasra_number",
        headers={"Authorization": f"Bearer {verifier_token}"},
        json={"value": "451/2"},
    )
    await client.post(f"/api/v1/documents/{doc_id}/verify",
                      headers={"Authorization": f"Bearer {verifier_token}"})
    return doc_id


@pytest.mark.asyncio
async def test_lrms_push_verified_doc(
    client: AsyncClient, verifier_token: str, seeded_document: dict
):
    doc_id = await _make_verified_doc(client, verifier_token, seeded_document)
    resp = await client.post(
        f"/api/v1/integrations/lrms/push/{doc_id}",
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
        f"/api/v1/integrations/gis/push/{doc_id}",
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
        f"/api/v1/integrations/lrms/push/{doc_id}",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert resp.status_code == 422
    assert "verified" in resp.json()["detail"].lower()


# ─────────────────────────────────────────────────────────────────────────────
# Object-Level Authorization (IDOR Protection) Tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_field_officer_cannot_access_other_users_document(
    client: AsyncClient, verifier_token: str, admin_token: str
):
    """
    Test object-level authorization:
    1. Field officer A uploads a document
    2. Field officer B attempts to fetch/list/audit/file it -> 403 Forbidden
    3. Verifier and Admin can access it -> 200 OK
    """
    # Register Field Officer A
    await client.post("/api/v1/auth/register", json={
        "username": "officer_a",
        "password": "Password123!",
        "role": "field_officer",
    })
    resp_a = await client.post("/api/v1/auth/login", json={
        "username": "officer_a",
        "password": "Password123!",
    })
    token_a = resp_a.json()["access_token"]

    # Register Field Officer B
    await client.post("/api/v1/auth/register", json={
        "username": "officer_b",
        "password": "Password123!",
        "role": "field_officer",
    })
    resp_b = await client.post("/api/v1/auth/login", json={
        "username": "officer_b",
        "password": "Password123!",
    })
    token_b = resp_b.json()["access_token"]

    # Officer A uploads document
    pdf_bytes = io.BytesIO(b"%PDF-1.4 mock content for officer a")
    with patch("app.api.documents.process_document"):
        upload_resp = await client.post(
            "/api/v1/documents/upload",
            headers={"Authorization": f"Bearer {token_a}"},
            files={"file": ("deed_a.pdf", pdf_bytes, "application/pdf")},
            data={"district": "Jaipur"},
        )
    assert upload_resp.status_code == 202
    doc_id = upload_resp.json()["id"]

    # 1. Officer A can access own document
    resp = await client.get(f"/api/v1/documents/{doc_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert resp.status_code == 200
    assert resp.json()["id"] == doc_id

    # 2. Officer B attempts to fetch Officer A's document -> 403
    resp = await client.get(f"/api/v1/documents/{doc_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 403
    assert "access denied" in resp.json()["detail"].lower()

    # Officer B attempts to fetch audit trail -> 403
    resp = await client.get(f"/api/v1/documents/{doc_id}/audit", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 403

    # Officer B attempts to fetch duplicates -> 403
    resp = await client.get(f"/api/v1/documents/{doc_id}/duplicates", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 403

    # Officer B attempts to fetch DILRMP export -> 403
    resp = await client.get(f"/api/v1/documents/{doc_id}/export/dilrmp", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 403

    # Officer B attempts to fetch integrity -> 403
    resp = await client.get(f"/api/v1/documents/{doc_id}/integrity", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 403

    # Officer B attempts to download file -> 403
    resp = await client.get(f"/api/v1/documents/{doc_id}/file", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 403

    # Officer B attempts to fetch OCR boxes -> 403
    resp = await client.get(f"/api/v1/documents/{doc_id}/ocr-boxes", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 403

    # Officer B attempts to fetch preview image -> 403
    resp = await client.get(f"/api/v1/documents/{doc_id}/preview-image", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 403

    # Officer B attempts write operations (PATCH field, verify, reprocess) -> 403
    patch_resp = await client.patch(
        f"/api/v1/documents/{doc_id}/fields/owner_name",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"value": "Malicious Modification"},
    )
    assert patch_resp.status_code == 403

    verify_resp = await client.post(
        f"/api/v1/documents/{doc_id}/verify",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert verify_resp.status_code == 403

    reprocess_resp = await client.post(
        f"/api/v1/documents/{doc_id}/reprocess",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert reprocess_resp.status_code == 403

    # Officer B lists documents -> document is filtered out of the list
    list_resp = await client.get("/api/v1/documents", headers={"Authorization": f"Bearer {token_b}"})
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert all(item["id"] != doc_id for item in items)

    # 3. Verifier can access Officer A's document -> 200
    resp = await client.get(f"/api/v1/documents/{doc_id}", headers={"Authorization": f"Bearer {verifier_token}"})
    assert resp.status_code == 200

    resp = await client.get(f"/api/v1/documents/{doc_id}/ocr-boxes", headers={"Authorization": f"Bearer {verifier_token}"})
    assert resp.status_code == 200

    # 4. Admin can access Officer A's document -> 200
    resp = await client.get(f"/api/v1/documents/{doc_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_dashboard_stats_scoped_to_field_officer(
    client: AsyncClient, admin_token: str
):
    """
    Test dashboard scoping:
    - Officer A uploads 1 document
    - Officer B uploads 0 documents
    - Officer B gets total_documents=0 in /dashboard/stats
    - Admin gets system-wide total_documents >= 1 in /dashboard/stats
    """
    # Register Officer A
    await client.post("/api/v1/auth/register", json={
        "username": "dash_officer_a",
        "password": "Password123!",
        "role": "field_officer",
    })
    resp_a = await client.post("/api/v1/auth/login", json={
        "username": "dash_officer_a",
        "password": "Password123!",
    })
    token_a = resp_a.json()["access_token"]

    # Register Officer B
    await client.post("/api/v1/auth/register", json={
        "username": "dash_officer_b",
        "password": "Password123!",
        "role": "field_officer",
    })
    resp_b = await client.post("/api/v1/auth/login", json={
        "username": "dash_officer_b",
        "password": "Password123!",
    })
    token_b = resp_b.json()["access_token"]

    # Officer A uploads document
    with patch("app.api.documents.process_document"):
        await client.post(
            "/api/v1/documents/upload",
            headers={"Authorization": f"Bearer {token_a}"},
            files={"file": ("deed_dash.pdf", io.BytesIO(b"%PDF-1.4 content"), "application/pdf")},
            data={"district": "Jaipur"},
        )

    # Officer A stats: total_documents == 1
    stats_a = (await client.get("/api/v1/dashboard/stats", headers={"Authorization": f"Bearer {token_a}"})).json()
    assert stats_a["total_documents"] == 1

    # Officer B stats: total_documents == 0 (does not see Officer A's docs)
    stats_b = (await client.get("/api/v1/dashboard/stats", headers={"Authorization": f"Bearer {token_b}"})).json()
    assert stats_b["total_documents"] == 0

    # Admin stats: sees system-wide total
    stats_admin = (await client.get("/api/v1/dashboard/stats", headers={"Authorization": f"Bearer {admin_token}"})).json()
    assert stats_admin["total_documents"] >= 1

