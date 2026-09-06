"""
Tests for SSE event streaming, duplicate endpoint, and diagnostics.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_stream_events_requires_auth(client: AsyncClient):
    """GET /documents/{id}/events must require authentication."""
    resp = await client.get("/documents/1/events")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_stream_events_completed_document(
    client: AsyncClient, admin_token: str, seeded_document: dict
):
    """GET /documents/{id}/events on existing document returns SSE stream."""
    doc_id = seeded_document["id"]
    resp = await client.get(
        f"/documents/{doc_id}/events",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    assert "data:" in resp.text


@pytest.mark.asyncio
async def test_get_document_duplicates_endpoint(
    client: AsyncClient, admin_token: str, seeded_document: dict
):
    """GET /documents/{id}/duplicates returns candidate matches."""
    doc_id = seeded_document["id"]
    resp = await client.get(
        f"/documents/{doc_id}/duplicates",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "duplicate_count" in data
    assert "has_suspected_duplicates" in data
    assert isinstance(data["matches"], list)


@pytest.mark.asyncio
async def test_system_diagnostics_endpoint(client: AsyncClient):
    """GET /health/diagnostics returns operational metrics for DB, OCR, and LLM."""
    resp = await client.get("/health/diagnostics")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["app_status"] == "ONLINE"
    assert "database" in data
    assert "ocr_engine" in data
    assert "llm_engine" in data
    assert "storage" in data


@pytest.mark.asyncio
async def test_get_document_file_and_audit(
    client: AsyncClient, admin_token: str, seeded_document: dict, db: AsyncSession
):
    """GET /documents/{id}/file and /audit must work for frontend rendering."""
    import tempfile
    from pathlib import Path
    from sqlalchemy import update
    from app.models.document import Document

    doc_id = seeded_document["id"]

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
        tf.write(b"%PDF-1.4 test preview content")
        temp_path = tf.name

    try:
        await db.execute(
            update(Document).where(Document.id == doc_id).values(storage_path=temp_path)
        )
        await db.commit()

        # Test file endpoint with query token (iframe simulation)
        file_resp = await client.get(f"/documents/{doc_id}/file?token={admin_token}")
        assert file_resp.status_code == 200
        assert file_resp.content == b"%PDF-1.4 test preview content"

        # Test audit endpoint
        audit_resp = await client.get(
            f"/documents/{doc_id}/audit",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert audit_resp.status_code == 200
        assert isinstance(audit_resp.json(), list)
    finally:
        Path(temp_path).unlink(missing_ok=True)


