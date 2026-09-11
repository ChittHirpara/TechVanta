"""
Tests for SIH 2026 Demo Mode & Showcase Endpoints.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_demo_seed_and_status(client: AsyncClient):
    # 1. Seed demo data
    res = await client.post("/api/v1/demo/seed")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "success"
    assert data["documents_count"] == 5
    assert len(data["showcase_scenarios"]) == 5

    # 2. Check demo status
    status_res = await client.get("/api/v1/demo/status")
    assert status_res.status_code == 200
    sdata = status_res.json()
    assert sdata["is_ready"] is True
    assert sdata["database_counts"]["documents"] == 5
    assert len(sdata["credentials"]) == 3


@pytest.mark.asyncio
async def test_demo_showcase_duplicate_detection(client: AsyncClient, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}
    # Reset & seed
    await client.post("/api/v1/demo/seed")

    # Fetch document list
    list_res = await client.get("/api/v1/documents", headers=headers)
    assert list_res.status_code == 200
    docs = list_res.json()["items"]
    assert len(docs) == 5

    # Doc #1 is clean Jaipur khasra, Doc #3 is duplicate fraud attempt
    doc_1 = next(d for d in docs if d["filename"] == "jaipur_khasra_451.pdf")
    doc_fraud = next(d for d in docs if d["filename"] == "jaipur_fraud_khasra_451.pdf")

    # Fetch detail of fraudulent duplicate (verification payload is prior-upload free:
    # duplicate tracking is exposed only through the explicit /duplicates endpoint)
    detail_res = await client.get(f"/api/v1/documents/{doc_fraud['id']}", headers=headers)
    assert detail_res.status_code == 200
    fdetail = detail_res.json()
    assert fdetail["has_suspected_duplicates"] is False
    assert fdetail["duplicate_count"] == 0
    assert fdetail["top_duplicate_score"] is None

    # Test explicit duplicates endpoint (dedicated Fraud Shield feature)
    dup_res = await client.get(f"/api/v1/documents/{doc_fraud['id']}/duplicates", headers=headers)
    assert dup_res.status_code == 200
    dup_data = dup_res.json()
    assert dup_data["has_suspected_duplicates"] is True
    assert len(dup_data["matches"]) >= 1
    assert any(m["document_id"] == doc_1["id"] for m in dup_data["matches"])


@pytest.mark.asyncio
async def test_demo_showcase_multilingual_hindi(client: AsyncClient, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}
    await client.post("/api/v1/demo/seed")

    list_res = await client.get("/api/v1/documents", headers=headers)
    docs = list_res.json()["items"]
    hindi_doc = next(d for d in docs if d["filename"] == "varanasi_khasra_hindi.pdf")

    detail_res = await client.get(f"/api/v1/documents/{hindi_doc['id']}", headers=headers)
    assert detail_res.status_code == 200
    hdetail = detail_res.json()

    assert hdetail["status"] == "verified"
    fields = {f["field_name"]: f for f in hdetail["extracted_fields"]}

    # Verify Devanagari values and computed confidence tiers
    assert fields["owner_name"]["value"] == "रामेश्वर प्रसाद शर्मा"
    assert fields["owner_name"]["confidence_tier"] == "high"
    assert fields["owner_name"]["confidence_color"] == "green"
    assert fields["owner_name"]["is_flagged"] is False

    assert fields["district"]["value"] == "वाराणसी"
    assert fields["tehsil"]["value"] == "पिंडरा"
    assert fields["village"]["value"] == "शिवपुर"


@pytest.mark.asyncio
async def test_rich_dashboard_stats_endpoint(client: AsyncClient, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}
    await client.post("/api/v1/demo/seed")

    res = await client.get("/api/v1/dashboard/stats", headers=headers)
    assert res.status_code == 200
    stats = res.json()

    # Core volume & quality
    assert stats["total_documents"] == 5
    assert stats["total_processed"] >= 4
    assert stats["verified"] >= 2
    assert stats["pending_review"] >= 2
    assert stats["total_fields"] > 0

    # Enhanced SIH metrics
    assert "accuracy_rate" in stats
    assert stats["accuracy_rate"] > 70.0
    assert "automation_rate" in stats
    assert "duplicate_alerts_count" in stats
    assert stats["duplicate_alerts_count"] >= 1
    assert "docs_processed_today" in stats
    assert "avg_processing_time_s" in stats
    assert len(stats["district_breakdown"]) >= 2
