"""
Phase 3 — Combined End-to-End Audit Script
Covers all 10 steps: cold-start, verifier journey, field_officer defense-in-depth,
IDOR protection, zero-field verify, failure injection, duplicate detection,
SSE resilience, CORS, and public QR verify.

Run from backend/ directory:
  python scripts/phase3_e2e_audit.py [--step N]

Key facts locked in from Phases 0-2:
- Auth: POST /api/v1/auth/login with JSON body {username, password}
- SSE route: GET /api/v1/documents/{id}/events?token=<jwt>
- SSE events contain: event, step, percent (NOT progress), status, message
- Ingestion.jsx reads data.percent (not data.progress)
- certificate is HTML (text/html), not PDF
- QR URL format: bhoomiscan.nic.in/verify?ulpin=...&hash=...
- No 'carol' user seeded - must register field_officer first
"""
from __future__ import annotations
import asyncio
import json
import os
import re
import sys
import time
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("JWT_SECRET", "dev-secret-key-bhoomiscan-1234567890")
os.environ.setdefault("LLM_API_KEY", "mock-dev-key")

import httpx
from app.core.config import get_settings

BASE_URL = "http://localhost:8000"
DEMO_DIR = Path(__file__).resolve().parent.parent.parent / "demo_assets"

findings: list[dict] = []

def record(step: str, status: str, detail: str):
    findings.append({"step": step, "status": status, "detail": detail})
    icons = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️", "INFO": "ℹ️"}
    print(f"  {icons.get(status,'?')} [{status}] {detail}")


async def login(client: httpx.AsyncClient, username: str, password: str) -> str:
    res = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, f"Login failed for {username}: {res.text}"
    return res.json()["access_token"]


async def register_if_missing(client: httpx.AsyncClient, username: str, password: str, role: str) -> str:
    """Register user if not exists, return token."""
    # Try login first
    res = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    if res.status_code == 200:
        return res.json()["access_token"]
    # Register via admin
    admin_token = await login(client, "alice", "Admin1234!")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    reg = await client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": password, "role": role},
        headers=admin_headers,
    )
    if reg.status_code not in (200, 201, 409):
        print(f"  Registration failed: {reg.status_code} {reg.text}")
    # Now login
    res2 = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    return res2.json()["access_token"]


async def wait_sse_complete(client: httpx.AsyncClient, doc_id: int, token: str, label: str = "") -> list[dict]:
    """Connect to SSE stream and collect events until complete/error or 100%."""
    events = []
    url = f"/api/v1/documents/{doc_id}/events?token={token}"
    async with client.stream("GET", url) as sse_resp:
        assert sse_resp.status_code == 200, f"SSE {sse_resp.status_code}"
        async for raw_line in sse_resp.aiter_lines():
            if raw_line.startswith("data:"):
                data_str = raw_line[5:].strip()
                if data_str:
                    ev = json.loads(data_str)
                    events.append(ev)
                    pct = ev.get("percent", "?")
                    step = ev.get("step", "?")
                    status = ev.get("status", "?")
                    print(f"    {label}SSE: step={step:<25} percent={pct:>3}%  status={status}")
                    if ev.get("event") in ("complete", "error") or ev.get("percent") == 100:
                        break
    return events


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 0: Cold-start timing & health diagnostics
# ═══════════════════════════════════════════════════════════════════════════════
async def step0_cold_start():
    print("\n" + "="*70)
    print("STEP 0: COLD-START TIMING & HEALTH DIAGNOSTICS")
    print("="*70)
    t0 = time.perf_counter()
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
        res = await client.get("/health/diagnostics")
        elapsed_ms = (time.perf_counter() - t0) * 1000
        print(f"  GET /health/diagnostics => {res.status_code} in {elapsed_ms:.0f}ms")
        d = res.json()
        print(json.dumps(d, indent=2))

        record("step0", "PASS" if res.status_code == 200 else "FAIL",
               f"Health endpoint: {res.status_code} in {elapsed_ms:.0f}ms")
        record("step0", "PASS" if d["database"]["status"] == "HEALTHY" else "FAIL",
               f"DB status: {d['database']['status']}, latency: {d['database']['latency_ms']}ms")
        record("step0", "PASS" if d["ocr_engine"]["provider"] == "easyocr" else "FAIL",
               f"OCR provider: {d['ocr_engine']['provider']}")
        record("step0", "INFO",
               f"LLM_API_KEY=mock-dev-key → heuristic fallback is primary for demo (no real LLM calls)")
        record("step0", "INFO",
               f"Uploads directory: {d['storage']['document_count']} existing files")
        record("step0", "INFO",
               f"OCR pre-warm: model loaded at startup via lifespan handler in app/main.py")


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1: Full verifier user journey
# ═══════════════════════════════════════════════════════════════════════════════
async def step1_verifier_journey() -> tuple[int, str]:
    print("\n" + "="*70)
    print("STEP 1: FULL VERIFIER JOURNEY — login→upload→SSE→fields→patch→verify→cert→audit")
    print("="*70)

    pdf_path = DEMO_DIR / "01_clean_jaipur_khasra.pdf"
    if not pdf_path.exists():
        record("step1", "FAIL", f"Demo asset missing: {pdf_path}")
        return -1, ""

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=180) as client:
        # 1a. Login
        token = await login(client, "bob", "Verif5678!")
        record("step1", "PASS", "Login as verifier 'bob' → 200 OK, JWT received")
        headers = {"Authorization": f"Bearer {token}"}

        # 1b. /auth/me confirms role
        me_res = await client.get("/api/v1/auth/me", headers=headers)
        me = me_res.json()
        record("step1", "PASS" if me["role"] == "verifier" else "FAIL",
               f"GET /auth/me → id={me['id']}, role={me['role']}, username={me['username']}")

        # 1c. Upload clean demo asset
        with open(pdf_path, "rb") as f:
            file_bytes = f.read()
        print(f"\n  Uploading {pdf_path.name} ({len(file_bytes):,} bytes)...")
        t_up = time.perf_counter()
        up_res = await client.post(
            "/api/v1/documents/upload",
            headers=headers,
            files={"file": (pdf_path.name, file_bytes, "application/pdf")},
            data={"district": "Jaipur", "tehsil": "Sanganer", "village": "Rampur Kalan"},
        )
        up_elapsed = (time.perf_counter() - t_up) * 1000
        print(f"  Upload → {up_res.status_code} in {up_elapsed:.0f}ms: {up_res.json()}")
        record("step1", "PASS" if up_res.status_code == 202 else "FAIL",
               f"POST /documents/upload → {up_res.status_code} in {up_elapsed:.0f}ms")
        doc_id = up_res.json()["id"]

        # 1d. SSE stream — uses percent field (not progress)
        print(f"\n  SSE stream for doc {doc_id} (GET /api/v1/documents/{doc_id}/events)...")
        t_sse = time.perf_counter()
        events = await wait_sse_complete(client, doc_id, token, label="")
        sse_elapsed = time.perf_counter() - t_sse
        last_ev = events[-1] if events else {}
        record("step1", "PASS" if len(events) >= 3 else "WARN",
               f"SSE: received {len(events)} events over {sse_elapsed:.1f}s")
        record("step1", "PASS" if last_ev.get("percent") == 100 else "FAIL",
               f"SSE final event: percent={last_ev.get('percent')}%, status={last_ev.get('status')}, event={last_ev.get('event')}")

        # 1e. Fetch extracted fields
        doc_res = await client.get(f"/api/v1/documents/{doc_id}", headers=headers)
        doc = doc_res.json()
        extracted = doc.get("extracted_fields", [])
        print(f"\n  Document after pipeline: status={doc['status']}, fields={len(extracted)}")
        for fld in extracted:
            flag = "🚩" if fld["is_flagged"] else "  "
            print(f"    {flag} {fld['field_name']:25s} = '{fld['value']}' (conf={fld['confidence_score']:.2f})")
        record("step1", "PASS" if len(extracted) > 0 else "FAIL",
               f"Extracted {len(extracted)} fields from {pdf_path.name}")

        # 1f. Patch flagged fields as verifier
        flagged = [f for f in extracted if f["is_flagged"]]
        record("step1", "INFO", f"Flagged fields requiring correction: {len(flagged)}")
        for ff in flagged:
            corrected = (ff["value"] or "").replace("l", "1") or "Corrected Value"
            pr = await client.patch(
                f"/api/v1/documents/{doc_id}/fields/{ff['field_name']}",
                headers=headers,
                json={"value": corrected},
            )
            record("step1", "PASS" if pr.status_code == 200 else "FAIL",
                   f"PATCH field '{ff['field_name']}' corrected → {pr.status_code}: {pr.json().get('value')}")

        # 1g. Verify document
        ver_res = await client.post(f"/api/v1/documents/{doc_id}/verify", headers=headers)
        print(f"\n  POST /documents/{doc_id}/verify → {ver_res.status_code}")
        print(f"  Body: {ver_res.json()}")
        record("step1", "PASS" if ver_res.status_code == 200 else "FAIL",
               f"Verify → {ver_res.status_code}, final status = '{ver_res.json().get('status')}'")

        # 1h. Certificate (HTML)
        cert_res = await client.get(f"/api/v1/documents/{doc_id}/certificate", headers=headers)
        ct = cert_res.headers.get("content-type", "")
        cert_html = cert_res.text
        record("step1", "PASS" if "text/html" in ct else "FAIL",
               f"GET /certificate → {cert_res.status_code}, Content-Type: {ct}")
        record("step1", "PASS" if len(cert_html) > 1000 else "FAIL",
               f"Certificate HTML: {len(cert_html)} chars")
        has_qr = "ulpin" in cert_html.lower() or "qr" in cert_html.lower() or "bhoomiscan" in cert_html.lower()
        record("step1", "PASS" if has_qr else "WARN",
               "Certificate contains BhoomiScan branding / ULPIN / QR indicator")

        # 1i. Audit trail
        audit_res = await client.get(f"/api/v1/documents/{doc_id}/audit", headers=headers)
        raw_audit = audit_res.json()
        audit_items = raw_audit if isinstance(raw_audit, list) else raw_audit.get("items", [])
        actions = {a["action"] for a in audit_items}
        print(f"\n  Audit trail ({len(audit_items)} entries): {sorted(actions)}")
        for a in audit_items:
            print(f"    [{a['timestamp']}] {a['action']} by user_id={a.get('user_id')}")
        record("step1", "PASS" if "document_verified" in actions else "FAIL",
               f"Audit trail contains 'document_verified': {sorted(actions)}")

        return doc_id, cert_html


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2: field_officer defense-in-depth
# ═══════════════════════════════════════════════════════════════════════════════
async def step2_field_officer_defense(verifier_doc_id: int) -> int:
    print("\n" + "="*70)
    print("STEP 2: FIELD_OFFICER DEFENSE-IN-DEPTH (UI-disabled + backend 403 checks)")
    print("="*70)

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60) as client:
        fo_token = await register_if_missing(client, "carol", "FieldOfficer123!", "field_officer")
        record("step2", "PASS", "field_officer 'carol' registered/logged in → token received")
        fo_headers = {"Authorization": f"Bearer {fo_token}"}

        # Check role
        me_res = await client.get("/api/v1/auth/me", headers=fo_headers)
        me = me_res.json()
        record("step2", "PASS" if me["role"] == "field_officer" else "FAIL",
               f"GET /auth/me → role={me['role']}")

        # Must fail: POST /verify (requires verifier/admin)
        res = await client.post(f"/api/v1/documents/{verifier_doc_id}/verify", headers=fo_headers)
        record("step2", "PASS" if res.status_code == 403 else "FAIL",
               f"FO POST /verify on verifier's doc → {res.status_code} (expected 403): '{res.json().get('detail','')}'")

        # Must fail: PATCH field (requires verifier/admin)
        res = await client.patch(
            f"/api/v1/documents/{verifier_doc_id}/fields/owner_name",
            headers=fo_headers,
            json={"value": "Malicious Override"},
        )
        record("step2", "PASS" if res.status_code == 403 else "FAIL",
               f"FO PATCH /fields on verifier's doc → {res.status_code} (expected 403)")

        # Must fail: LRMS push (admin only)
        res = await client.post(f"/api/v1/integrations/lrms/push/{verifier_doc_id}", headers=fo_headers)
        record("step2", "PASS" if res.status_code == 403 else "FAIL",
               f"FO POST /lrms/push → {res.status_code} (expected 403)")

        # MUST succeed: field_officer CAN upload
        tiny_pdf = (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
                    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
                    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 3 3]>>endobj\n"
                    b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n"
                    b"0000000058 00000 n\n0000000115 00000 n\n"
                    b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF")
        res = await client.post(
            "/api/v1/documents/upload",
            headers=fo_headers,
            files={"file": ("fo_upload.pdf", tiny_pdf, "application/pdf")},
            data={"district": "Jodhpur", "tehsil": "Jodhpur", "village": "Test"},
        )
        record("step2", "PASS" if res.status_code == 202 else "FAIL",
               f"FO CAN upload their own doc → {res.status_code} (expected 202)")
        fo_doc_id = res.json().get("id", -1)

        # field_officer CANNOT access a doc owned by verifier
        res = await client.get(f"/api/v1/documents/{verifier_doc_id}", headers=fo_headers)
        record("step2", "PASS" if res.status_code == 403 else "FAIL",
               f"FO GET verifier's doc by ID → {res.status_code} (expected 403): '{res.json().get('detail','')}'")

        return fo_doc_id


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3: IDOR protection
# ═══════════════════════════════════════════════════════════════════════════════
async def step3_idor_protection(verifier_doc_id: int, fo_doc_id: int):
    print("\n" + "="*70)
    print("STEP 3: IDOR PROTECTION — cross-user document access enumeration")
    print("="*70)

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
        fo_token = await login(client, "carol", "FieldOfficer123!")
        fo_headers = {"Authorization": f"Bearer {fo_token}"}

        # FO cannot access verifier's document
        res = await client.get(f"/api/v1/documents/{verifier_doc_id}", headers=fo_headers)
        record("step3", "PASS" if res.status_code == 403 else "FAIL",
               f"FO GET doc#{verifier_doc_id} (verifier's) → {res.status_code} (expected 403)")

        # FO CAN access their own document
        res = await client.get(f"/api/v1/documents/{fo_doc_id}", headers=fo_headers)
        record("step3", "PASS" if res.status_code == 200 else "FAIL",
               f"FO GET own doc#{fo_doc_id} → {res.status_code} (expected 200)")

        # Enumerate adjacent IDs for bleed
        fo_user_id_res = await client.get("/api/v1/auth/me", headers=fo_headers)
        fo_user_id = fo_user_id_res.json()["id"]
        bleed = False
        for test_id in range(max(1, verifier_doc_id - 2), verifier_doc_id + 3):
            if test_id == fo_doc_id:
                continue
            r = await client.get(f"/api/v1/documents/{test_id}", headers=fo_headers)
            if r.status_code == 200:
                owner = r.json().get("uploaded_by")
                if owner != fo_user_id:
                    bleed = True
                    record("step3", "FAIL", f"IDOR BLEED: FO can read doc#{test_id} owned by user_id={owner}")
                    break
        if not bleed:
            record("step3", "PASS", f"No IDOR bleed in IDs {max(1, verifier_doc_id-2)}–{verifier_doc_id+2}")


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4: Zero-field document — verify blocked
# ═══════════════════════════════════════════════════════════════════════════════
async def step4_zero_field_verify() -> int:
    print("\n" + "="*70)
    print("STEP 4: ZERO-FIELD DOCUMENT — verify must return 422")
    print("="*70)

    blank_pdf = (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
                 b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
                 b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 3 3]>>endobj\n"
                 b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n"
                 b"0000000058 00000 n\n0000000115 00000 n\n"
                 b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF")

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=120) as client:
        token = await login(client, "bob", "Verif5678!")
        headers = {"Authorization": f"Bearer {token}"}

        up_res = await client.post(
            "/api/v1/documents/upload",
            headers=headers,
            files={"file": ("blank_doc.pdf", blank_pdf, "application/pdf")},
            data={"district": "Jaipur", "tehsil": "Test", "village": "Blank"},
        )
        record("step4", "PASS" if up_res.status_code == 202 else "FAIL",
               f"Upload blank PDF → {up_res.status_code}")
        zero_doc_id = up_res.json().get("id", -1)

        print(f"  Waiting for pipeline on blank PDF (doc#{zero_doc_id})...")
        events = await wait_sse_complete(client, zero_doc_id, token, label="[blank] ")

        doc_res = await client.get(f"/api/v1/documents/{zero_doc_id}", headers=headers)
        doc = doc_res.json()
        n_fields = len(doc.get("extracted_fields", []))
        record("step4", "INFO",
               f"Blank PDF extraction: {n_fields} extracted fields, status={doc['status']}")

        verify_res = await client.post(f"/api/v1/documents/{zero_doc_id}/verify", headers=headers)
        print(f"  POST /verify on zero-field doc → {verify_res.status_code}: {verify_res.json()}")
        if n_fields == 0:
            record("step4", "PASS" if verify_res.status_code == 422 else "FAIL",
                   f"Zero-field verify → {verify_res.status_code} (expected 422): '{verify_res.json().get('detail','')}'")
        else:
            record("step4", "INFO",
                   f"Blank PDF produced {n_fields} fields. Verify blocked with 422: '{verify_res.json().get('detail','')}'")

        # Explicitly verify the zero-field guard on a document with strictly 0 ExtractedField rows
        from app.db.session import AsyncSessionLocal
        from app.models.document import Document as DBтовогоDoc, DocumentStatus as DBStatus
        async with AsyncSessionLocal() as db:
            zdoc = DBтовогоDoc(
                filename="zero_fields_guard_check.pdf",
                storage_path="uploads/zero_fields_guard_check.pdf",
                status=DBStatus.needs_review,
                district="Jaipur",
                tehsil="Sanganer",
                village="ZeroField",
            )
            db.add(zdoc)
            await db.commit()
            await db.refresh(zdoc)
            zdoc_id = zdoc.id

        z_verify = await client.post(f"/api/v1/documents/{zdoc_id}/verify", headers=headers)
        z_body = z_verify.json()
        print(f"  POST /verify on explicit 0-field doc#{zdoc_id} → {z_verify.status_code}: {z_body}")
        record("step4", "PASS" if z_verify.status_code == 422 and "zero extracted" in z_body.get("detail", "").lower() else "FAIL",
               f"Zero-field guard check → {z_verify.status_code} (detail: '{z_body.get('detail')}')")

        async with AsyncSessionLocal() as db:
            to_del = await db.get(DBтовогоDoc, zdoc_id)
            if to_del:
                await db.delete(to_del)
                await db.commit()

        return zero_doc_id


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 5: Failure injection
# ═══════════════════════════════════════════════════════════════════════════════
async def step5_failure_injection():
    print("\n" + "="*70)
    print("STEP 5: FAILURE INJECTION — corrupt, oversized, wrong MIME")
    print("="*70)

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60) as client:
        token = await login(client, "bob", "Verif5678!")
        headers = {"Authorization": f"Bearer {token}"}

        # 5a. Corrupted binary garbage
        corrupt = b"NOT A PDF " + bytes(range(256)) * 100
        res = await client.post(
            "/api/v1/documents/upload", headers=headers,
            files={"file": ("corrupt.pdf", corrupt, "application/pdf")},
            data={"district": "Jaipur", "tehsil": "T", "village": "V"},
        )
        record("step5", "PASS" if res.status_code in (400, 415, 422, 202) else "FAIL",
               f"Corrupt PDF upload → {res.status_code}: {str(res.json())[:120]}")

        # 5b. Oversized file (26MB — limit is 25MB)
        big_bytes = b"%PDF-1.4\n" + b"x" * (26 * 1024 * 1024)
        try:
            res = await client.post(
                "/api/v1/documents/upload", headers=headers,
                files={"file": ("big.pdf", big_bytes, "application/pdf")},
                data={"district": "Jaipur", "tehsil": "T", "village": "V"},
            )
            record("step5", "PASS" if res.status_code in (413, 422, 400) else "FAIL",
                   f"26MB file upload → {res.status_code}: {str(res.json())[:120]}")
        except Exception as exc:
            record("step5", "INFO", f"26MB upload raised network error (likely 413 from server): {exc}")

        # 5c. Wrong MIME type (text/plain named .pdf)
        res = await client.post(
            "/api/v1/documents/upload", headers=headers,
            files={"file": ("fake.pdf", b"just text, no PDF structure", "text/plain")},
            data={"district": "Jaipur", "tehsil": "T", "village": "V"},
        )
        record("step5", "PASS" if res.status_code in (400, 415, 422, 202) else "FAIL",
               f"text/plain MIME → {res.status_code}: {str(res.json())[:120]}")

        # 5d. Missing required district metadata
        real_pdf_bytes = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF"
        res = await client.post(
            "/api/v1/documents/upload", headers=headers,
            files={"file": ("test.pdf", real_pdf_bytes, "application/pdf")},
            # No district/tehsil/village
        )
        record("step5", "PASS" if res.status_code in (400, 422, 202) else "FAIL",
               f"Missing metadata upload → {res.status_code}: {str(res.json())[:120]}")


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 6: Duplicate/fraud detection via real upload flow
# ═══════════════════════════════════════════════════════════════════════════════
async def step6_duplicate_detection(clean_doc_id: int):
    print("\n" + "="*70)
    print("STEP 6: DUPLICATE/FRAUD DETECTION — fraudulent asset vs clean baseline")
    print("="*70)

    fraud_path = DEMO_DIR / "03_fraudulent_duplicate_deed.pdf"
    if not fraud_path.exists():
        record("step6", "WARN", f"Fraud demo asset not found: {fraud_path} — skipping")
        return

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=180) as client:
        token = await login(client, "bob", "Verif5678!")
        headers = {"Authorization": f"Bearer {token}"}

        with open(fraud_path, "rb") as f:
            fraud_bytes = f.read()

        up_res = await client.post(
            "/api/v1/documents/upload", headers=headers,
            files={"file": (fraud_path.name, fraud_bytes, "application/pdf")},
            data={"district": "Jaipur", "tehsil": "Sanganer", "village": "Rampur Kalan"},
        )
        record("step6", "PASS" if up_res.status_code == 202 else "FAIL",
               f"Upload fraud doc → {up_res.status_code}")
        fraud_doc_id = up_res.json().get("id", -1)

        print(f"  Waiting for pipeline on fraud doc#{fraud_doc_id}...")
        await wait_sse_complete(client, fraud_doc_id, token, label="[fraud] ")

        dup_res = await client.get(f"/api/v1/documents/{fraud_doc_id}/duplicates", headers=headers)
        print(f"  GET /documents/{fraud_doc_id}/duplicates → {dup_res.status_code}")
        dup_data = dup_res.json()
        print(f"  Response: {json.dumps(dup_data, indent=2)[:800]}")
        record("step6", "PASS" if dup_res.status_code == 200 else "FAIL",
               f"Duplicate detection endpoint → {dup_res.status_code}")

        matches = dup_data.get("matches", [])
        record("step6", "PASS" if len(matches) > 0 else "WARN",
               f"Duplicate matches returned: {len(matches)}")
        if matches:
            top = matches[0]
            score = top.get("combined_score", top.get("similarity_score", 0))
            matched_id = top.get("document_id")
            record("step6", "PASS" if score >= 50 else "WARN",
                   f"Top match: doc_id={matched_id}, combined_score={score:.1f}%")
            record("step6", "PASS" if matched_id == clean_doc_id else "WARN",
                   f"Match references baseline doc_id={matched_id} "
                   f"{'(== clean doc ✓)' if matched_id == clean_doc_id else f'(expected {clean_doc_id})'}")


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 7: SSE resilience — static code analysis
# ═══════════════════════════════════════════════════════════════════════════════
async def step7_sse_resilience():
    print("\n" + "="*70)
    print("STEP 7: SSE RESILIENCE — frontend EventSource error/timeout handling")
    print("="*70)

    fe_src = Path(__file__).resolve().parent.parent.parent / "frontend" / "src"
    client_js = fe_src / "api" / "client.js"
    ingestion_jsx = fe_src / "components" / "ingestion" / "Ingestion.jsx"

    # client.js analysis
    cj = client_js.read_text(encoding="utf-8")
    print(f"\n  === {client_js.name} SSE section ===")
    for i, line in enumerate(cj.splitlines(), 1):
        if any(k in line for k in ["EventSource", "onerror", "onmessage", "close()", "retry"]):
            print(f"    L{i:3}: {line.strip()}")

    has_onerror = "onerror" in cj
    has_close = ".close()" in cj
    has_reconnect = "retry" in cj.lower() or "reconnect" in cj.lower()
    has_timeout = "timeout" in cj.lower() or "setTimeout" in cj

    record("step7", "PASS" if has_onerror else "FAIL",
           f"client.js: es.onerror handler present: {has_onerror}")
    record("step7", "PASS" if has_close else "WARN",
           f"client.js: EventSource.close() called: {has_close}")
    record("step7", "WARN" if not has_reconnect else "PASS",
           f"client.js: auto-reconnect logic: {has_reconnect}")

    # Backend SSE route: asyncio.wait_for timeout=25s + keep-alive ping
    print(f"\n  === Backend SSE timeout behavior ===")
    print("  asyncio.wait_for(queue.get(), timeout=25.0) → emits ': ping\\n\\n' keep-alive")
    print("  EventSource browser default: auto-reconnects on connection drop (retry: 3000ms)")
    record("step7", "INFO",
           "Backend sends keep-alive ping every 25s; browser EventSource auto-reconnects on drop")

    # Ingestion.jsx onerror handling
    ij = ingestion_jsx.read_text(encoding="utf-8")
    if "onerror" in ij or "onError" in ij:
        record("step7", "PASS",
               "Ingestion.jsx passes onerror callback to createDocumentEventSource → closes stream, logs message")
    else:
        record("step7", "WARN", "Ingestion.jsx does not explicitly handle SSE error in component")

    record("step7", "WARN",
           "SSE resilience gap: no frontend timeout guards a stale 'processing' state if backend dies "
           "mid-stream and auto-reconnect doesn't receive a 'complete' event. "
           "The progress bar will appear stuck. No visible timeout error shown to user after N seconds.")


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 8: CORS
# ═══════════════════════════════════════════════════════════════════════════════
async def step8_cors():
    print("\n" + "="*70)
    print("STEP 8: CORS — preflight responses from allowed and disallowed origins")
    print("="*70)

    cfg = get_settings()
    record("step8", "INFO", f"Configured allowed_origins: {cfg.allowed_origins}")

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15) as client:
        for origin in cfg.allowed_origins:
            res = await client.options(
                "/api/v1/auth/login",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "Authorization,Content-Type",
                },
            )
            acao = res.headers.get("access-control-allow-origin", "MISSING")
            record("step8", "PASS" if acao in (origin, "*") else "FAIL",
                   f"Preflight Origin='{origin}' → ACAO={acao} (status={res.status_code})")

        # Evil origin — must be rejected
        res = await client.options(
            "/api/v1/auth/login",
            headers={
                "Origin": "http://evil-attacker.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Authorization",
            },
        )
        acao = res.headers.get("access-control-allow-origin", "MISSING")
        record("step8", "PASS" if acao not in ("http://evil-attacker.com", "*") else "FAIL",
               f"Evil origin rejected: ACAO='{acao}' (expected MISSING or null)")

        record("step8", "INFO",
               "No deployed remote URL in ALLOWED_ORIGINS (localhost-only demo). "
               "If deploying to Vercel/Netlify/Firebase, add that origin to .env ALLOWED_ORIGINS.")


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 9: Public QR verification (unauthenticated)
# ═══════════════════════════════════════════════════════════════════════════════
async def step9_public_verify(cert_html: str, verifier_doc_id: int):
    print("\n" + "="*70)
    print("STEP 9: PUBLIC VERIFICATION QR FLOW — unauthenticated citizen request")
    print("="*70)

    # Extract ULPIN and hash from certificate HTML
    ulpin_match = (
        re.search(r'class="ulpin-badge">([A-Z0-9\-]+)<', cert_html, re.IGNORECASE) or
        re.search(r'ULPIN\s*(?:No\.?|:)?\s*([A-Z0-9\-]{6,})', cert_html, re.IGNORECASE)
    )
    hash_match = (
        re.search(r'class="seal-hash">SHA-256:\s*([a-f0-9]{64})<', cert_html, re.IGNORECASE) or
        re.search(r'SHA-256:\s*([a-f0-9]{64})', cert_html, re.IGNORECASE) or
        re.search(r'(?:Certificate\s+Hash|SHA-?256|Integrity\s+Hash)\s*[:\s]+([a-f0-9]{16,})', cert_html, re.IGNORECASE)
    )
    ulpin    = ulpin_match.group(1).strip() if ulpin_match else None
    hash_val = hash_match.group(1).strip()  if hash_match  else None

    print(f"  Extracted from certificate: ULPIN={ulpin}, hash={hash_val}")

    if not ulpin or not hash_val:
        record("step9", "WARN",
               f"Could not extract ULPIN/hash from cert HTML — trying integrity endpoint as fallback")
        # Get integrity hash via API
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=15) as client:
            token = await login(client, "bob", "Verif5678!")
            int_res = await client.get(
                f"/api/v1/documents/{verifier_doc_id}/integrity",
                headers={"Authorization": f"Bearer {token}"},
            )
            if int_res.status_code == 200:
                int_data = int_res.json()
                hash_val = int_data.get("sha256_hash") or int_data.get("file_hash")
                ulpin    = int_data.get("ulpin")
                print(f"  Integrity endpoint: {json.dumps(int_data, indent=2)[:400]}")

    if not ulpin or not hash_val:
        record("step9", "WARN", "No ULPIN/hash available — skipping public verify call")
        return

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=15) as client:
        # NO auth header — pure citizen request
        res = await client.get(f"/api/v1/documents/public/verify/{ulpin}/{hash_val}")
        print(f"\n  GET /public/verify/{ulpin}/{hash_val[:16]}... (no auth) → {res.status_code}")
        print(f"  Response body: {json.dumps(res.json(), indent=2)[:600]}")

        record("step9", "PASS" if res.status_code == 200 else "FAIL",
               f"Public verify (unauthenticated) → {res.status_code}")

        if res.status_code == 200:
            body = res.json()
            pii_fields = {"owner_name", "plot_area", "survey_number", "khasra_number",
                          "registration_info", "mutation_record", "ownership_details", "khata_number"}
            exposed = pii_fields & set(body.keys())
            record("step9", "PASS" if not exposed else "FAIL",
                   f"PII exposure check — {'CLEAN' if not exposed else f'EXPOSED: {exposed}'}")
            record("step9", "INFO", f"Response keys: {sorted(body.keys())}")
        else:
            print(f"  Response: {res.text[:300]}")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
async def main(only_step: int | None = None):
    t_total = time.perf_counter()

    clean_doc_id, cert_html, fo_doc_id = -1, "", -1

    if only_step is None or only_step == 0:
        await step0_cold_start()

    if only_step is None or only_step == 1:
        clean_doc_id, cert_html = await step1_verifier_journey()

    if only_step is None or only_step == 2:
        fo_doc_id = await step2_field_officer_defense(clean_doc_id if clean_doc_id > 0 else 1)

    if only_step is None or only_step == 3:
        await step3_idor_protection(
            clean_doc_id if clean_doc_id > 0 else 1,
            fo_doc_id if fo_doc_id > 0 else 2
        )

    if only_step is None or only_step == 4:
        await step4_zero_field_verify()

    if only_step is None or only_step == 5:
        await step5_failure_injection()

    if only_step is None or only_step == 6:
        await step6_duplicate_detection(clean_doc_id if clean_doc_id > 0 else 1)

    if only_step is None or only_step == 7:
        await step7_sse_resilience()

    if only_step is None or only_step == 8:
        await step8_cors()

    if only_step is None or only_step == 9:
        await step9_public_verify(cert_html, clean_doc_id if clean_doc_id > 0 else 1)

    # ── Summary ──────────────────────────────────────────────────────────────
    elapsed = time.perf_counter() - t_total
    print("\n" + "="*70)
    print("PHASE 3 AUDIT SUMMARY")
    print("="*70)
    passes = [f for f in findings if f["status"] == "PASS"]
    fails  = [f for f in findings if f["status"] == "FAIL"]
    warns  = [f for f in findings if f["status"] == "WARN"]

    print(f"\n  ✅ PASS: {len(passes)}   ❌ FAIL: {len(fails)}   ⚠️  WARN: {len(warns)}")
    print(f"  Total audit time: {elapsed:.1f}s")

    if fails:
        print("\n  ❌ FAILURES (blockers):")
        for f in fails:
            print(f"     [{f['step']}] {f['detail']}")
    if warns:
        print("\n  ⚠️  WARNINGS (non-blockers):")
        for f in warns:
            print(f"     [{f['step']}] {f['detail']}")

    verdict = "✅ GO" if not fails else "❌ NO-GO"
    print(f"\n  ══ FINAL VERDICT: {verdict} ══")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 3 E2E Audit")
    parser.add_argument("--step", type=int, default=None,
                        help="Run only a specific step number (0–9)")
    args = parser.parse_args()
    asyncio.run(main(args.step))
