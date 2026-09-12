"""
Tests for Jurisdiction-Based Routing, Claiming, Escalations, and Filtered Notifications (SIH26018).
"""
import pytest
from datetime import datetime, timedelta, timezone
from io import BytesIO
from sqlalchemy import select

from app.models.document import Document, DocumentStatus
from app.models.user import User, UserRole
from app.models.verifier_jurisdiction import VerifierJurisdiction
from app.core.security import create_access_token


@pytest.fixture
async def admin_token(db):
    admin = (
        await db.execute(select(User).where(User.username == "admin_test"))
    ).scalar_one_or_none()
    if not admin:
        admin = User(username="admin_test", role=UserRole.admin, password_hash="hash")
        db.add(admin)
        await db.commit()
        await db.refresh(admin)
    return create_access_token(admin.id, {"role": admin.role.value, "username": admin.username}), admin


@pytest.fixture
async def verifier_tokens(db):
    # Verifier 1 (Jaipur)
    v1 = (await db.execute(select(User).where(User.username == "verifier_jaipur"))).scalar_one_or_none()
    if not v1:
        v1 = User(username="verifier_jaipur", role=UserRole.verifier, password_hash="hash")
        db.add(v1)
        await db.commit()
        await db.refresh(v1)
    token1 = create_access_token(v1.id, {"role": v1.role.value, "username": v1.username})

    # Verifier 2 (Jaipur shared)
    v2 = (await db.execute(select(User).where(User.username == "verifier_jaipur_2"))).scalar_one_or_none()
    if not v2:
        v2 = User(username="verifier_jaipur_2", role=UserRole.verifier, password_hash="hash")
        db.add(v2)
        await db.commit()
        await db.refresh(v2)
    token2 = create_access_token(v2.id, {"role": v2.role.value, "username": v2.username})

    # Verifier 3 (Udaipur only)
    v3 = (await db.execute(select(User).where(User.username == "verifier_udaipur"))).scalar_one_or_none()
    if not v3:
        v3 = User(username="verifier_udaipur", role=UserRole.verifier, password_hash="hash")
        db.add(v3)
        await db.commit()
        await db.refresh(v3)
    token3 = create_access_token(v3.id, {"role": v3.role.value, "username": v3.username})

    return {
        "v1": (token1, v1),
        "v2": (token2, v2),
        "v3": (token3, v3),
    }


@pytest.fixture
async def field_officer_token(db):
    fo = (
        await db.execute(select(User).where(User.username == "officer_test"))
    ).scalar_one_or_none()
    if not fo:
        fo = User(username="officer_test", role=UserRole.field_officer, password_hash="hash")
        db.add(fo)
        await db.commit()
        await db.refresh(fo)
    return create_access_token(fo.id, {"role": fo.role.value, "username": fo.username}), fo



# ── Scope 1 & 2: Jurisdiction Assignment & Auto-Assignment vs Shared Pool ──

@pytest.mark.asyncio
async def test_admin_jurisdiction_crud(client, admin_token, verifier_tokens):
    admin_tok, _ = admin_token
    _, v1 = verifier_tokens["v1"]
    headers = {"Authorization": f"Bearer {admin_tok}"}

    # 1. Create mapping
    res = await client.post(
        "/api/v1/jurisdictions",
        headers=headers,
        json={"user_id": v1.id, "district": "Udaipur", "tehsil": "Girwa"},
    )
    assert res.status_code in (201, 409)
    if res.status_code == 201:
        data = res.json()
        assert data["user_id"] == v1.id
        assert data["district"] == "Udaipur"
        assignment_id = data["id"]

        # 2. List mappings
        list_res = await client.get("/api/v1/jurisdictions", headers=headers)
        assert list_res.status_code == 200
        assert any(item["id"] == assignment_id for item in list_res.json())

        # 3. List verifiers summary
        v_list = await client.get("/api/v1/jurisdictions/verifiers", headers=headers)
        assert v_list.status_code == 200
        assert any(u["id"] == v1.id for u in v_list.json())

        # 4. Delete mapping
        del_res = await client.delete(f"/api/v1/jurisdictions/{assignment_id}", headers=headers)
        assert del_res.status_code == 204


@pytest.mark.asyncio
async def test_single_verifier_auto_assignment(client, db, admin_token, verifier_tokens, field_officer_token):
    admin_tok, _ = admin_token
    _, v3 = verifier_tokens["v3"]
    fo_tok, fo = field_officer_token

    # Assign v3 uniquely to Kota
    vj = VerifierJurisdiction(user_id=v3.id, district="Kota", tehsil=None, village=None)
    db.add(vj)
    await db.commit()

    # Upload document in Kota
    pdf_content = b"%PDF-1.4 sample content"
    files = {"file": ("deed_kota.pdf", BytesIO(pdf_content), "application/pdf")}
    data = {"district": "Kota", "tehsil": "Ladpura", "village": "Mandana"}
    headers = {"Authorization": f"Bearer {fo_tok}"}

    res = await client.post("/api/v1/documents/upload", headers=headers, files=files, data=data)
    assert res.status_code == 202
    doc_data = res.json()
    doc_id = doc_data["id"]

    # Verify auto-assignment to v3
    doc = (await db.execute(select(Document).where(Document.id == doc_id))).scalar_one()
    assert doc.assigned_verifier_id == v3.id
    assert doc.claimed_at is not None
    assert doc.is_escalated is False


@pytest.mark.asyncio
async def test_shared_pool_and_claim_action(client, db, admin_token, verifier_tokens, field_officer_token):
    t1, v1 = verifier_tokens["v1"]
    t2, v2 = verifier_tokens["v2"]
    fo_tok, fo = field_officer_token

    # Assign both v1 and v2 to Jodhpur
    db.add(VerifierJurisdiction(user_id=v1.id, district="Jodhpur", tehsil=None, village=None))
    db.add(VerifierJurisdiction(user_id=v2.id, district="Jodhpur", tehsil=None, village=None))
    await db.commit()

    # Upload doc in Jodhpur
    pdf_content = b"%PDF-1.4 sample content"
    files = {"file": ("deed_jodhpur.pdf", BytesIO(pdf_content), "application/pdf")}
    data = {"district": "Jodhpur", "tehsil": "Luni", "village": "Salawas"}
    headers = {"Authorization": f"Bearer {fo_tok}"}

    res = await client.post("/api/v1/documents/upload", headers=headers, files=files, data=data)
    assert res.status_code == 202
    doc_id = res.json()["id"]

    # In shared pool -> assigned_verifier_id is None
    doc = (await db.execute(select(Document).where(Document.id == doc_id))).scalar_one()
    assert doc.assigned_verifier_id is None

    # Both v1 and v2 should see the document in GET /documents
    v1_list = await client.get("/api/v1/documents", headers={"Authorization": f"Bearer {t1}"})
    v2_list = await client.get("/api/v1/documents", headers={"Authorization": f"Bearer {t2}"})
    assert any(d["id"] == doc_id for d in v1_list.json()["items"])
    assert any(d["id"] == doc_id for d in v2_list.json()["items"])

    # Verifier 1 claims the document
    claim_res = await client.post(f"/api/v1/documents/{doc_id}/claim", headers={"Authorization": f"Bearer {t1}"})
    assert claim_res.status_code == 200
    assert claim_res.json()["assigned_verifier_id"] == v1.id

    # Verifier 2 attempting to claim it gets 409 Conflict
    claim_conflict = await client.post(f"/api/v1/documents/{doc_id}/claim", headers={"Authorization": f"Bearer {t2}"})
    assert claim_conflict.status_code == 409

    # Now Verifier 2 does NOT see it in unassigned/shared pool
    v2_list_after = await client.get("/api/v1/documents", headers={"Authorization": f"Bearer {t2}"})
    assert not any(d["id"] == doc_id for d in v2_list_after.json()["items"])


# ── Scope 3: Escalation Logic ──

@pytest.mark.asyncio
async def test_cold_start_and_unassigned_escalation(client, db, admin_token, field_officer_token):
    admin_tok, _ = admin_token
    fo_tok, fo = field_officer_token

    # Upload document with unmapped district "Bikaner"
    pdf_content = b"%PDF-1.4 sample content"
    files = {"file": ("deed_bikaner.pdf", BytesIO(pdf_content), "application/pdf")}
    data = {"district": "Bikaner_Unknown_Region", "tehsil": "Nokha"}

    res = await client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {fo_tok}"},
        files=files,
        data=data,
    )
    assert res.status_code == 202
    doc_id = res.json()["id"]

    doc = (await db.execute(select(Document).where(Document.id == doc_id))).scalar_one()
    assert doc.assigned_verifier_id is None
    assert doc.is_escalated is True
    assert doc.escalation_reason == "UNASSIGNED_JURISDICTION"

    # Admin escalations endpoint surfaces it
    esc_res = await client.get("/api/v1/jurisdictions/escalations", headers={"Authorization": f"Bearer {admin_tok}"})
    assert esc_res.status_code == 200
    esc_data = esc_res.json()
    assert any(d["id"] == doc_id for d in esc_data["unassigned_documents"])


@pytest.mark.asyncio
async def test_sla_breach_escalation(client, db, admin_token):
    admin_tok, _ = admin_token

    # Create document created 60 hours ago
    aged_doc = Document(
        filename="aged_deed.pdf",
        storage_path="/tmp/aged_deed.pdf",
        status=DocumentStatus.needs_review,
        district="Ajmer",
        created_at=datetime.now(timezone.utc) - timedelta(hours=60),
        is_escalated=False,
    )
    db.add(aged_doc)
    await db.commit()
    await db.refresh(aged_doc)

    # Escalations summary with default SLA (48h) should include aged_doc
    esc_res = await client.get("/api/v1/jurisdictions/escalations", headers={"Authorization": f"Bearer {admin_tok}"})
    assert esc_res.status_code == 200
    esc_data = esc_res.json()
    assert any(d["id"] == aged_doc.id for d in esc_data["sla_breached_documents"])


@pytest.mark.asyncio
async def test_admin_zero_routine_notifications(client, db, admin_token, field_officer_token):
    admin_tok, _ = admin_token
    fo_tok, fo = field_officer_token

    # Create normal document that is NOT escalated
    normal_doc = Document(
        filename="routine_on_time.pdf",
        storage_path="/tmp/routine.pdf",
        status=DocumentStatus.needs_review,
        district="Jaipur",
        uploaded_by=fo.id,
        created_at=datetime.now(timezone.utc),
        is_escalated=False,
        escalation_reason=None,
    )
    db.add(normal_doc)
    await db.commit()

    # Admin notifications endpoint should contain ZERO notifications for this normal doc
    notifs = await client.get("/api/v1/documents/notifications", headers={"Authorization": f"Bearer {admin_tok}"})
    assert notifs.status_code == 200
    items = notifs.json()
    assert not any(n.get("document_id") == normal_doc.id for n in items)
