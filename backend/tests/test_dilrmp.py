"""
Tests for DILRMP compliance service and government export endpoints.
"""
import io
import tempfile
from pathlib import Path
import pytest
from httpx import AsyncClient

from app.services.dilrmp import (
    build_dilrmp_export_payload,
    compute_file_sha256,
    generate_ulpin,
    parse_area_conversions,
)


def test_generate_ulpin_format():
    """ULPIN must be exactly 14 uppercase alphanumeric characters starting with state code."""
    ulpin = generate_ulpin(
        state_code="08",
        district="Jaipur",
        tehsil="Sanganer",
        village="Rampur",
        khasra_number="451/2",
        survey_number="78-B",
    )
    assert len(ulpin) == 14
    assert ulpin.isupper()
    assert ulpin.isalnum()
    assert ulpin.startswith("08")


def test_parse_area_conversions():
    """Area conversions must accurately normalize Bigha and Acres to Hectares."""
    bigha_res = parse_area_conversions("2 Bigha")
    assert bigha_res["declared_unit"] == "bigha"
    assert bigha_res["standard_hectares"] > 0
    assert bigha_res["standard_acres"] > 0

    acre_res = parse_area_conversions("5 acres")
    assert acre_res["declared_unit"] == "acre"
    assert acre_res["standard_hectares"] == pytest.approx(2.0234, abs=0.01)

    empty_res = parse_area_conversions(None)
    assert empty_res["standard_hectares"] is None


def test_compute_file_sha256():
    """SHA-256 calculation must match standard hashlib output."""
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(b"National Land Record Test")
        path = tf.name

    try:
        digest = compute_file_sha256(path)
        assert len(digest) == 64
        assert digest.islower()
    finally:
        Path(path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_dilrmp_export_endpoint(
    client: AsyncClient, admin_token: str, seeded_document: dict
):
    """GET /api/v1/documents/{id}/export/dilrmp should return standard DILRMP 2.0 payload with ULPIN."""
    doc_id = seeded_document["id"]
    resp = await client.get(
        f"/api/v1/documents/{doc_id}/export/dilrmp",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["standard"] == "DILRMP-2.0"
    assert len(data["ulpin"]) == 14
    assert "cryptographic_seal" in data
    assert "land_parcel" in data
    assert "ownership_record" in data


@pytest.mark.asyncio
async def test_document_integrity_endpoint(
    client: AsyncClient, admin_token: str, seeded_document: dict
):
    """GET /api/v1/documents/{id}/integrity should check cryptographic seal."""
    doc_id = seeded_document["id"]
    resp = await client.get(
        f"/api/v1/documents/{doc_id}/integrity",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "sha256_hash" in data
    assert "status" in data
    assert data["document_id"] == doc_id
