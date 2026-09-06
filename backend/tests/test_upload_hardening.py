"""
Tests for upload hardening: file size limits and magic bytes verification.
"""
import io
from unittest.mock import patch
import pytest
from httpx import AsyncClient

from app.api.documents import MAX_FILE_SIZE_BYTES


@pytest.mark.asyncio
async def test_upload_rejects_spoofed_extension(client: AsyncClient, admin_token: str):
    """File named .pdf but containing plain text should be rejected by magic bytes guard."""
    fake_pdf = io.BytesIO(b"Hello world, I am not a real PDF file!")

    with patch("app.api.documents.process_document"):
        resp = await client.post(
            "/api/v1/documents/upload",
            headers={"Authorization": f"Bearer {admin_token}"},
            files={"file": ("fake.pdf", fake_pdf, "application/pdf")},
        )
    assert resp.status_code == 415, resp.text
    assert "magic bytes" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_rejects_empty_file(client: AsyncClient, admin_token: str):
    """Empty files should be rejected with 400 Bad Request."""
    empty_file = io.BytesIO(b"")

    with patch("app.api.documents.process_document"):
        resp = await client.post(
            "/api/v1/documents/upload",
            headers={"Authorization": f"Bearer {admin_token}"},
            files={"file": ("empty.pdf", empty_file, "application/pdf")},
        )
    assert resp.status_code == 400, resp.text
    assert "empty" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_accepts_valid_magic_bytes(client: AsyncClient, admin_token: str):
    """File with valid PDF magic bytes (%PDF-) should be accepted."""
    valid_pdf = io.BytesIO(b"%PDF-1.4 official government land record")

    with patch("app.api.documents.process_document"):
        resp = await client.post(
            "/api/v1/documents/upload",
            headers={"Authorization": f"Bearer {admin_token}"},
            files={"file": ("valid.pdf", valid_pdf, "application/pdf")},
        )
    assert resp.status_code == 202, resp.text
    assert resp.json()["status"] == "processing"


@pytest.mark.asyncio
async def test_upload_rejects_oversized_file(client: AsyncClient, admin_token: str):
    """File exceeding MAX_FILE_SIZE_BYTES should be rejected with 413."""
    # Temporarily patch MAX_FILE_SIZE_BYTES to 1024 bytes for quick testing
    tiny_pdf = io.BytesIO(b"%PDF-" + b"0" * 2048)

    with patch("app.api.documents.MAX_FILE_SIZE_BYTES", 100):
        resp = await client.post(
            "/api/v1/documents/upload",
            headers={"Authorization": f"Bearer {admin_token}"},
            files={"file": ("huge.pdf", tiny_pdf, "application/pdf")},
        )
    assert resp.status_code == 413, resp.text
    assert "limit" in resp.json()["detail"].lower()
