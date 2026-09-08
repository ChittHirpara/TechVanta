# Full-system audit: security, pipeline, and frontend/backend integrity fixes

## Summary of Changes

This pull request consolidates critical security, pipeline, and frontend fixes identified, hardened, and verified across an exhaustive 4-phase audit of **BhoomiScan AI**. The system now features defense-in-depth role-based access control, cryptographic verification integrity, pipeline pre-warming, and live React UI synchronicity.

---

## 1. Security & Cryptographic Integrity Fixes

- **Hardened Public Verification Endpoint (`GET /api/v1/documents/public/verify/{ulpin}/{hash}`)**:
  - Previously accepted arbitrary or partial hash prefixes without strict cross-validation.
  - Hardened to mandate full 64-character SHA-256 cryptographic hashes matched against database records.
  - Enforced strict ULPIN cross-validation ensuring the hash corresponds precisely to the declared land parcel.
  - Audited response payload to guarantee zero PII leakage: unauthenticated citizens receive only cryptographic seal status and issuing authority (`owner_name`, `khasra_number`, `survey_number`, and financial details are strictly redacted).
- **Blocked Zero-Field Verification Bypass (`POST /api/v1/documents/{id}/verify`)**:
  - Prevented a critical flaw where documents with zero extracted fields (e.g. blank PDFs or failed OCR runs) could be verified and issued sovereign certificates.
  - Implemented a strict check in `documents.py`: returns `422 Unprocessable Entity` if `extracted_fields` is empty.
  - Added unit and E2E regression tests (`test_verify_blocked_by_zero_extracted_fields`).
- **Object-Level IDOR Protection**:
  - Enforced document ownership boundaries: `field_officer` can only access and query documents they uploaded.
  - Verifier and Admin roles retain jurisdiction-wide access for audit and verification purposes.
  - Validated via sequential ID enumeration scan.

---

## 2. OCR & Pipeline Engine Enhancements

- **Process Cold-Start Pre-Warming**:
  - Integrated EasyOCR model initialization (`Reader(['en'])`) directly into the FastAPI `lifespan` handler (`backend/app/main.py`).
  - Eliminates first-request timeout spikes; true server startup takes ~15s and all subsequent document uploads execute with zero cold-start delay.
- **Robust Heuristic Regex Extraction Fallback**:
  - Generalized regex extraction across cadastral fields (`khasra_number`, `khata_number`, `survey_number`, `plot_area`, `owner_name`, etc.) in `backend/app/services/extraction.py`.
  - Enables full, robust offline demonstration capability without requiring live third-party LLM API keys (`LLM_API_KEY=mock-dev-key`).
- **Input Validation & Upload Hardening**:
  - Rejects binary garbage and invalid MIME types via magic byte signatures (`HTTP 415`).
  - Enforces 25MB file size limit during upload streaming (`HTTP 413`).

---

## 3. Frontend Fixes & Live Synchronicity (`frontend/`)

- **Fixed Extracted Fields Display Bug**:
  - Corrected data mapping from deprecated `doc.fields` to real backend schema `doc.extracted_fields` across ingestion and review components.
- **Fixed Duplicate Detection Field Mismatch & Removed Fabrication Fallback**:
  - Updated `DuplicateCompareModal.jsx` to consume `combined_score` (matching backend `find_duplicates` response) rather than legacy `similarity_score`.
  - Removed dangerous `?? 85` fallback that silently fabricated 85% confidence scores on missing data.
- **Role-Based UI Defense-in-Depth**:
  - Gated action buttons (Verify, Field Edit, LRMS Push) based on user role (`admin`, `verifier`, `field_officer`).
  - Disabled actions display informative native tooltips explaining privilege requirements.
- **CORS Origin Completeness**:
  - Added `http://127.0.0.1:5173` to `ALLOWED_ORIGINS` in `.env` and `.env.example` alongside `localhost:5173`, `localhost:8000`, and `127.0.0.1:8000`.

---

## 4. Database Seeding & Clean Demo State

- **Updated Seed Script (`backend/scripts/seed.py`)**:
  - Added `carol` (`role=field_officer`, password `FieldOfficer123!`) so all 3 system roles are seeded out of the box.
  - Document #1 (`jaipur_khasra_451.pdf`) seeded as verified benchmark for duplicate/fraud testing.
  - Supports clean reset via `python scripts/seed.py --reset`.

---

## 5. Demo-Day Narrative & Presentation Guide

To avoid narrative confusion during live demonstration:
1. **Beat 1 — The Happy Path (Scan → Extraction → Verification)**:
   - Use `02_degraded_jodhpur_plot_deed.jpg` to demonstrate robust OCR & field extraction on realistic/messy land records without triggering duplicate warnings.
   - Patch flagged fields $\rightarrow$ Verify $\rightarrow$ View sovereign HTML certificate with cryptographic seal.
2. **Beat 2 — Fraud & Duplicate Shield**:
   - Use `03_fraudulent_duplicate_deed.pdf` (or `01_clean_jaipur_khasra.pdf`) to demonstrate the live Duplicate Detection modal.
   - Shows live 90–100% match against baseline Document #1 (`jaipur_khasra_451.pdf`).
3. **Beat 3 — Sovereign Citizen Verification**:
   - Call or scan `GET /api/v1/documents/public/verify/{ulpin}/{hash}` unauthenticated to prove live validity with zero PII exposure.
4. **Beat 4 — Role-Based Access Control**:
   - Log in as `carol` (`field_officer`) to demonstrate UI-disabled verification buttons and backend 403 enforcement.

### Startup Logistics
- **Pre-Demo DB Reset**: Run `python scripts/seed.py --reset` to clear test artifacts and start with 3 clean curated documents.
- **Process Timing**: Launch backend server at least **20 seconds** before demo to allow EasyOCR model weights to load into CPU memory.

---

## 6. Verification & Test Evidence

- **Pytest Suite**: 95/95 passing tests (`pytest tests/`) in 28.45s.
- **E2E Audit Suite**: 44/44 pass across all 10 evaluation steps (`scripts/phase3_e2e_audit.py`).
- **Frontend Build**: Production Vite bundle built cleanly in 476ms with 0 errors.
- **Browser Automation**: End-to-end verifier journey recorded and validated on Chrome/Blink.

---

## 7. Known Limitations (Audit Warnings)

The following 5 non-blocking warnings were identified and documented during the Phase 3 audit:
1. **Duplicate Baseline Reference Target (`[step6]`)**: Fraud document matched seeded Document #1 (`100%`) before newly uploaded document (`90.77%`). Managed via demo sequencing.
2. **EventSource Factory Scope (`[step7]`)**: `client.js` creates and returns the `EventSource` instance for component lifecycle management rather than closing it within helper scope.
3. **Browser Default Reconnect (`[step7]`)**: System relies on HTML5 standard browser EventSource auto-reconnect (3s) rather than custom exponential backoff.
4. **Component Error Callback (`[step7]`)**: `Ingestion.jsx` initializes SSE stream without custom `onError` prop.
5. **Stale Progress Timeout Guard (`[step7]`)**: If backend drops mid-stream, progress bar stays in processing state without a client-side timeout timer.
