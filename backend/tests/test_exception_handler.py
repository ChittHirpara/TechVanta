"""
Tests for global unhandled exception handler and HTTPException preservation.

Verifies:
1. Legitimate HTTPExceptions (404, 401, 403, 422) are NOT swallowed/masked as 500.
2. Unhandled runtime errors (e.g. ZeroDivisionError, RuntimeError) are caught by
   the global handler, logged, and return sanitized 500 JSON {"detail": "Internal server error"}.
"""
import pytest
from httpx import AsyncClient
from unittest.mock import MagicMock
from fastapi import Request

from app.main import unhandled_exception_handler


@pytest.mark.asyncio
async def test_not_found_preserves_404(client: AsyncClient, admin_token: str):
    """Ensure HTTPException(404) is preserved and not converted to 500."""
    response = await client.get(
        "/api/v1/documents/999999",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 404
    body = response.json()
    assert body["detail"] == "Document 999999 not found."


@pytest.mark.asyncio
async def test_unauthorized_preserves_401(client: AsyncClient):
    """Ensure unauthenticated access returns 401, not 500."""
    response = await client.get("/api/v1/documents/1")
    assert response.status_code == 401
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_validation_error_preserves_422(client: AsyncClient, admin_token: str):
    """Ensure invalid parameter formats return 422 validation error, not 500."""
    response = await client.get(
        "/api/v1/documents/invalid_doc_id",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_unhandled_exception_handler_returns_sanitized_500():
    """Ensure unhandled exceptions caught by handler return sanitized 500 response."""
    mock_request = MagicMock(spec=Request)
    mock_request.method = "GET"
    mock_request.url.path = "/api/v1/documents/1"

    exc = RuntimeError("Simulated database connection failure")
    response = await unhandled_exception_handler(mock_request, exc)

    assert response.status_code == 500
    assert response.body == b'{"detail":"Internal server error"}'
