"""
Comprehensive End-to-End Integration Audit Script for SIH 2026.
Tests the live backend at http://localhost:8000 across all 9 audit requirements.
"""
from __future__ import annotations

import json
import mimetypes
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "http://localhost:8000"

def request(method: str, path: str, data: dict | bytes | None = None, headers: dict | None = None):
    url = f"{BASE_URL}{path}"
    req_headers = headers.copy() if headers else {}
    body = None
    if isinstance(data, dict):
        body = json.dumps(data).encode("utf-8")
        req_headers["Content-Type"] = "application/json"
    elif isinstance(data, bytes):
        body = data

    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode("utf-8")
            status = resp.status
            try:
                json_data = json.loads(content)
            except Exception:
                json_data = content
            return status, json_data, resp.headers
    except urllib.error.HTTPError as e:
        content = e.read().decode("utf-8")
        try:
            json_data = json.loads(content)
        except Exception:
            json_data = content
        return e.code, json_data, e.headers
    except Exception as e:
        return 0, str(e), {}


def test_cors():
    print("\n[1/7] Testing CORS & Preflight...")
    # Test 1: Web origin localhost:3000
    status, _, headers = request("OPTIONS", "/api/v1/documents", headers={
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "POST",
    })
    allow_origin = headers.get("Access-Control-Allow-Origin")
    assert status == 200, f"OPTIONS failed with status {status}"
    assert allow_origin == "http://localhost:3000", f"Expected Allow-Origin http://localhost:3000, got {allow_origin}"
    print("  ✔ Web origin http://localhost:3000 allowed")

    # Test 2: Web origin localhost:5173
    status, _, headers = request("OPTIONS", "/api/v1/documents", headers={
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "GET",
    })
    assert status == 200
    assert headers.get("Access-Control-Allow-Origin") == "http://localhost:5173"
    print("  ✔ Web origin http://localhost:5173 allowed")

    # Test 3: Mobile (No Origin header)
    status, body, _ = request("GET", "/health")
    assert status == 200, f"No-origin request failed: {status}"
    print("  ✔ Mobile / non-browser request without Origin header passed")


def test_health():
    print("\n[2/7] Testing Health & Sanity Endpoint...")
    status, data, _ = request("GET", "/health")
    assert status == 200
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert data["llm"]["configured"] is True
    assert data["llm"]["provider"] == "xai-grok"
    assert data["llm"]["model"] == "grok-3-mini"
    print("  ✔ GET /health returns DB connected + xAI Grok provider info:")
    print("   ", json.dumps(data, indent=2))


def test_auth_flow():
    print("\n[3/7] Testing Auth Flow End-to-End...")
    # Reset to known good state
    request("POST", "/api/v1/demo/seed")

    roles = [
        ("alice", "Admin1234!", "admin"),
        ("bob", "Verif5678!", "verifier"),
        ("carol", "FieldOfficer123!", "field_officer"),
    ]
    tokens = {}
    for username, pwd, role in roles:
        # Test login at root /auth/login (legacy) and /api/v1/auth/login
        status_root, data_root, _ = request("POST", "/auth/login", {"username": username, "password": pwd})
        status_v1, data_v1, _ = request("POST", "/api/v1/auth/login", {"username": username, "password": pwd})
        assert status_root == 200, f"Root /auth/login failed: {data_root}"
        assert status_v1 == 200, f"/api/v1/auth/login failed: {data_v1}"
        assert "access_token" in data_v1
        token = data_v1["access_token"]
        tokens[role] = token

        # Test /auth/me
        status_me, me_data, _ = request("GET", "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert status_me == 200
        assert me_data["username"] == username
        assert me_data["role"] == role
        print(f"  ✔ {username} ({role}): Login & /auth/me verified")

    # Test Role Guard: Field Officer Carol attempts to PATCH a field (must be 403 Forbidden, NOT 500)
    status_patch, err_patch, _ = request(
        "PATCH",
        "/api/v1/documents/2/fields/khasra_number",
        {"value": "221/1"},
        headers={"Authorization": f"Bearer {tokens['field_officer']}"}
    )
    assert status_patch == 403, f"Expected 403 for field officer PATCH, got {status_patch}: {err_patch}"
    assert "detail" in err_patch
    print("  ✔ Role Guard: field_officer PATCH correctly rejected with 403 Forbidden")

    # Test Role Guard: Field Officer Carol attempts to Verify a document (must be 403 Forbidden)
    status_verify, err_verify, _ = request(
        "POST",
        "/api/v1/documents/2/verify",
        headers={"Authorization": f"Bearer {tokens['field_officer']}"}
    )
    assert status_verify == 403, f"Expected 403 for field officer verify, got {status_verify}: {err_verify}"
    print("  ✔ Role Guard: field_officer POST /verify correctly rejected with 403 Forbidden")

    return tokens


def test_mobile_pipeline(tokens):
    print("\n[4/7] Simulating Mobile App Capture & Ingest Pipeline...")
    # Mobile app uses Carol (field officer) token
    token = tokens["field_officer"]

    # Prepare multipart upload
    sample_file = Path("demo_assets/01_clean_jaipur_khasra.pdf")
    boundary = "----WebKitFormBoundaryMobile7MA4YWxkTrZu0gW"
    
    file_bytes = sample_file.read_bytes()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="mobile_capture_test.pdf"\r\n'
        f"Content-Type: application/pdf\r\n\r\n"
    ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }

    status, upload_res, _ = request("POST", "/documents/upload", body, headers)
    assert ("document_id" in upload_res or "id" in upload_res), f"Neither document_id nor id in upload_res: {upload_res}"
    doc_id = upload_res.get("document_id") or upload_res.get("id")
    print(f"  ✔ Mobile document uploaded: ID #{doc_id}, initial status: {upload_res.get('status')}")

    # Poll status
    max_poll = 15
    final_doc = None
    for i in range(max_poll):
        time.sleep(1)
        s, doc, _ = request("GET", f"/documents/{doc_id}", headers={"Authorization": f"Bearer {token}"})
        assert s == 200, f"Poll failed: {doc}"
        if doc["status"] in ("needs_review", "verified"):
            final_doc = doc
            break

    assert final_doc is not None, "Document did not finish processing within 15 seconds"
    print(f"  ✔ Document pipeline finished with status: {final_doc['status']}")
    print(f"    Total extracted fields: {len(final_doc['extracted_fields'])}")
    print(f"    Has suspected duplicates: {final_doc['has_suspected_duplicates']}")

    # Confirm field schema structure
    for field in final_doc["extracted_fields"]:
        assert "field_name" in field
        assert "value" in field
        assert "confidence_score" in field
        assert "confidence_tier" in field
        assert "confidence_color" in field
        assert "is_flagged" in field
    print("  ✔ All extracted field response shapes verified against contract")


def test_web_verification_flow(tokens):
    print("\n[5/7] Simulating Web Dashboard Verification Workflow...")
    token = tokens["verifier"]  # Bob
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Fetch documents needing review
    status, docs_res, _ = request("GET", "/api/v1/documents?status=needs_review", headers=headers)
    assert status == 200
    items = docs_res["items"]
    assert len(items) >= 1
    print(f"  ✔ Retrieved {len(items)} documents pending review in verifier queue")

    # Pick Jodhpur plot deed (doc 2)
    status, doc2, _ = request("GET", "/api/v1/documents/2", headers=headers)
    assert status == 200
    flagged = [f for f in doc2["extracted_fields"] if f["is_flagged"]]
    print(f"  ✔ Document #2 has {len(flagged)} flagged fields: {[f['field_name'] for f in flagged]}")

    # 2. Verifier corrects each flagged field
    for f in flagged:
        val = "221/1" if f["field_name"] == "khasra_number" else ("101" if f["field_name"] == "khata_number" else "Entry 12")
        p_status, patched, _ = request(
            "PATCH",
            f"/api/v1/documents/2/fields/{f['field_name']}",
            {"value": val, "note": "Verified against original deed seal"},
            headers=headers
        )
        assert p_status == 200, f"PATCH failed: {patched}"
        assert patched["is_flagged"] is False
        assert patched["confidence_tier"] in ("high", "medium")

    print("  ✔ All flagged fields corrected via PATCH")

    # 3. Verifier signs off on the document
    v_status, v_doc, _ = request("POST", "/api/v1/documents/2/verify", headers=headers)
    assert v_status == 200, f"Verify failed: {v_doc}"
    assert v_doc["status"] == "verified"
    print("  ✔ Document #2 transitioned to 'verified' successfully")

    # 4. Check dashboard stats update
    s_status, stats, _ = request("GET", "/api/v1/dashboard/stats", headers=headers)
    assert s_status == 200
    assert stats["verified"] >= 2
    print(f"  ✔ Dashboard stats confirmed updated: verified docs = {stats['verified']}, accuracy = {stats['accuracy_rate']}%")


def test_error_consistency():
    print("\n[6/7] Testing Error Response Consistency...")
    # Test 1: Missing auth header -> 401
    s, err, _ = request("GET", "/api/v1/documents")
    assert s == 401
    assert "detail" in err
    print("  ✔ Missing auth returned 401 with standard detail JSON")

    # Test 2: Bad document ID -> 404
    s, err, _ = request("GET", "/api/v1/documents/999999", headers={"Authorization": "Bearer fake-token"})
    assert s in (401, 404)
    assert "detail" in err
    print("  ✔ Non-existent ID returned 404/401 with standard detail JSON")

    # Test 3: Invalid field name in PATCH
    # Login first
    _, login_data, _ = request("POST", "/api/v1/auth/login", {"username": "bob", "password": "Verif5678!"})
    token = login_data["access_token"]
    s, err, _ = request(
        "PATCH",
        "/api/v1/documents/1/fields/non_existent_field_xyz",
        {"value": "val"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert s == 404
    assert "detail" in err
    print("  ✔ Invalid field name returned 404 with standard detail JSON")


def test_duplicate_detection(tokens):
    print("\n[7/7] Testing Fraud Shield Duplicate Detection...")
    token = tokens["admin"]
    headers = {"Authorization": f"Bearer {token}"}

    # Doc 3 is jaipur_fraud_khasra_451.pdf
    status, dup_res, _ = request("GET", "/api/v1/documents/3/duplicates", headers=headers)
    assert status == 200
    assert dup_res["has_suspected_duplicates"] is True
    assert dup_res["duplicate_count"] >= 1
    match = dup_res["matches"][0]
    print(f"  ✔ Duplicate caught: Document #{match['document_id']} ({match['filename']})")
    print(f"    Owner similarity: {match['owner_similarity']}%, Survey similarity: {match['survey_similarity']}%, Combined: {match['combined_score']}%")


if __name__ == "__main__":
    print("=================================================================")
    print("  BHOOMISCAN AI — FULL END-TO-END INTEGRATION AUDIT")
    print("=================================================================")
    test_cors()
    test_health()
    tokens = test_auth_flow()
    test_mobile_pipeline(tokens)
    test_web_verification_flow(tokens)
    test_error_consistency()
    test_duplicate_detection(tokens)
    print("\n=================================================================")
    print("  ✔ ALL 7 INTEGRATION SUITES PASSED END-TO-END WITH ZERO ERRORS!")
    print("=================================================================")
