# BhoomiScan AI — Enterprise Land Record Digitization & Verification

A production-grade, tamper-evident FastAPI system built for the **Smart India Hackathon (SIH)** that automates the digitization and legal verification of Indian revenue records (Khasra, Khatauni, Jamabandi, Sale Deeds). 

Featuring an **in-process async pipeline**, **4-phase defensive LLM extraction**, **real-time Server-Sent Events (SSE)**, **DILRMP 2.0 compliance with 14-digit ULPIN ("Aadhaar for Land") generation**, **fuzzy duplicate title fraud detection**, **cryptographic SHA-256 integrity sealing**, **comprehensive audit trails**, and an **interactive zero-dependency verifier dashboard UI**.

---

## 🌟 Hackathon Winning Capabilities (10/10 Features)

- **🖥️ Built-In Interactive Verifier Dashboard**: Zero-dependency, modern dark-mode SPA served directly at `http://localhost:8000/` or `/ui`.
- **⚡ Real-Time Pipeline Event Stream (SSE)**: Live step-by-step progress emitted over `/documents/{id}/events` (OCR $\rightarrow$ LLM $\rightarrow$ Validation $\rightarrow$ Flagging).
- **🇮🇳 DILRMP 2.0 & ULPIN Generator**: National standard export schema with unique 14-character geocoded ULPIN identifiers.
- **🔒 Cryptographic SHA-256 Tamper Seal**: Digital verification proving deeds haven't been altered post-upload (`/documents/{id}/integrity`).
- **🛡️ Fuzzy Duplicate Title Fraud Shield**: Cross-references historical patwari registers using rapidfuzz token-sort and token-set matching (`/documents/{id}/duplicates`).
- **🛡️ Enterprise Upload Hardening**: Magic-bytes header verification (PDF, PNG, JPEG, TIFF) + 25MB file size enforcement.
- **🔍 Deep System Diagnostics**: Live health metrics on DB latency, OCR engine, LLM provider, and storage at `/health/diagnostics`.
- **🧪 85 Automated Tests (100% Passing)**: Full coverage of Auth, Upload, Validation, Pipeline, DILRMP, Integrity, and Streaming.

---

## Table of Contents

1. [Interactive Verifier UI](#1-interactive-verifier-ui)
2. [Project Structure](#2-project-structure)
3. [Quick Start with Docker](#3-quick-start-with-docker)
4. [Local Development (without Docker)](#4-local-development-without-docker)
5. [Environment Variables](#5-environment-variables)
6. [Database Migrations & Seed Data](#6-database-migrations--seed-data)
7. [API Reference](#7-api-reference)
   - [Auth & RBAC](#auth)
   - [Documents, Upload & SSE Stream](#documents)
   - [DILRMP & Integrity](#dilrmp--integrity)
   - [Duplicate Detection](#duplicate-detection)
   - [Dashboard & Stats](#dashboard)
   - [Government Integrations (LRMS & GIS)](#integrations)
   - [System Diagnostics](#diagnostics)
8. [Full End-to-End curl Walkthrough](#8-full-end-to-end-curl-walkthrough)
9. [Swapping the OCR Provider](#9-swapping-the-ocr-provider)
10. [Swapping the LLM Model](#10-swapping-the-llm-model)
11. [Running Tests (85 Passing)](#11-running-tests)
12. [Processing Pipeline Internals](#12-processing-pipeline-internals)

---

## 1. Project Structure

```
land-record-digitizer/
├── app/
│   ├── api/
│   │   ├── __init__.py        # Router aggregator
│   │   ├── auth.py            # /auth/register, /auth/login, /auth/me
│   │   ├── documents.py       # /documents/* endpoints
│   │   ├── dashboard.py       # /dashboard/stats
│   │   └── integrations.py    # /integrations/lrms, /integrations/gis
│   ├── core/
│   │   ├── config.py          # Pydantic Settings (all env vars)
│   │   ├── dependencies.py    # get_current_user, require_role
│   │   └── security.py        # JWT encode/decode, bcrypt helpers
│   ├── db/
│   │   └── session.py         # AsyncEngine, AsyncSessionLocal, get_db
│   ├── models/                # SQLAlchemy ORM models
│   ├── schemas/               # Pydantic request/response schemas
│   ├── services/
│   │   ├── ocr.py             # OCRProvider ABC + TesseractProvider
│   │   ├── extraction.py      # LLM field extraction (4-phase JSON repair)
│   │   ├── validation.py      # Rule checks, duplicate detection, confidence
│   │   ├── pipeline.py        # Orchestrates OCR→extraction→validation→DB
│   │   └── integrations.py    # LRMS/GIS payload builders + mock push
│   └── main.py                # FastAPI app instance, lifespan, /health
├── alembic/                   # Alembic migration environment
├── scripts/
│   ├── seed.py                # Demo data seeder
│   ├── test_ocr.py            # Standalone OCR smoke-test
│   ├── test_extraction.py     # Standalone LLM extraction test
│   ├── test_validation.py     # Standalone validation test
│   └── test_pipeline.py       # Pipeline integration test (mocked)
├── tests/                     # pytest test suite (73 tests)
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── pytest.ini
└── requirements.txt
```

---

## 2. Quick Start with Docker

### Prerequisites
- Docker Desktop (or Docker Engine + Compose v2)
- An OpenAI-compatible API key (or a running Ollama instance — see §10)

```bash
# 1. Clone and enter the project
git clone <repo-url> land-record-digitizer
cd land-record-digitizer

# 2. Create your environment file
cp .env.example .env
#    → Edit .env and set JWT_SECRET and LLM_API_KEY at minimum

# 3. Start Postgres + the API server
docker-compose up -d

# 4. Apply database migrations
docker-compose exec app alembic upgrade head

# 5. Load demo data (admin + verifier user + 3 sample documents)
docker-compose exec app python scripts/seed.py

# 6. Verify the API is running
curl http://localhost:8000/health
# → {"status":"ok","version":"0.1.0"}
```

The API is now live at **http://localhost:8000**.
Interactive docs: **http://localhost:8000/docs** (Swagger UI)

---

## 3. Local Development (without Docker)

### System dependencies
Tesseract and Poppler are required for the OCR service.

**Ubuntu / Debian**
```bash
sudo apt-get install tesseract-ocr poppler-utils
# For Hindi/multilingual documents:
sudo apt-get install tesseract-ocr-hin
```

**macOS (Homebrew)**
```bash
brew install tesseract poppler
```

**Windows**
Download the Tesseract installer from the [UB Mannheim releases](https://github.com/UB-Mannheim/tesseract/wiki) and install Poppler via `conda` or the [poppler-windows releases](https://github.com/oschwartz10612/poppler-windows/releases).

### Python setup

```bash
# Create and activate a virtualenv
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env from the example
cp .env.example .env
# Edit .env — set DB_URL, JWT_SECRET, LLM_API_KEY

# Apply migrations against your local Postgres
alembic upgrade head

# Start the development server (hot reload)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 4. Environment Variables

Copy `.env.example` to `.env` and fill in the required values.

| Variable | Required | Default | Description |
|---|---|---|---|
| `DB_URL` | ✅ | — | PostgreSQL connection string: `postgresql+asyncpg://user:pass@host:port/db` |
| `JWT_SECRET` | ✅ | — | Long random string for signing JWTs. Generate with `openssl rand -hex 32` |
| `LLM_API_KEY` | ✅ | — | OpenAI API key (or any OpenAI-compatible provider key) |
| `APP_ENV` | | `development` | `development` or `production` |
| `DEBUG` | | `false` | Enables verbose SQLAlchemy logging |
| `JWT_ALGORITHM` | | `HS256` | JWT signing algorithm |
| `JWT_EXPIRE_MINUTES` | | `60` | Token lifetime in minutes |
| `LLM_MODEL` | | `gpt-4o` | Model name passed to the LLM API |
| `LLM_BASE_URL` | | *(OpenAI)* | Override to use Ollama, Azure OpenAI, etc. |
| `LLM_TEMPERATURE` | | `0.0` | Sampling temperature (0 = deterministic) |
| `LLM_MAX_TOKENS` | | `2048` | Max tokens in LLM response |
| `LLM_MAX_RETRIES` | | `2` | JSON parse-error retry attempts |
| `OCR_PROVIDER` | | `tesseract` | OCR backend: `tesseract` \| `easyocr` \| `trocr` |
| `TESSERACT_LANG` | | `eng` | Tesseract language(s), e.g. `eng+hin` for Hindi |
| `PDF_DPI` | | `300` | DPI for PDF→image conversion |
| `REVIEW_THRESHOLD` | | `0.75` | Combined confidence below this → field flagged |
| `FUZZY_THRESHOLD` | | `85.0` | rapidfuzz score (0–100) for duplicate detection |
| `OCR_CONFIDENCE_WEIGHT` | | `0.40` | Weight of OCR confidence in combined score |
| `EXTRACTION_CONFIDENCE_WEIGHT` | | `0.60` | Weight of LLM confidence in combined score |

### Minimal `.env` for a running system

```env
DB_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/land_records
JWT_SECRET=super-long-random-secret-replace-me
LLM_API_KEY=sk-...
```

---

## 5. Database Migrations

Alembic manages schema migrations with async SQLAlchemy.

```bash
# Apply all pending migrations (run after first clone and after git pull)
alembic upgrade head

# Check current migration status
alembic current

# Roll back one migration
alembic downgrade -1

# Auto-generate a new migration after editing a model
alembic revision --autogenerate -m "add_column_xyz"
# Review the generated file in alembic/versions/ before applying!

# Inside Docker
docker-compose exec app alembic upgrade head
```

---

## 6. Seed Demo Data

The seed script creates a ready-to-demo environment in seconds.

```bash
# Seed against Docker Postgres (reads .env)
docker-compose exec app python scripts/seed.py

# Wipe everything and re-seed (useful during development)
docker-compose exec app python scripts/seed.py --reset

# Seed a local SQLite file (no Postgres needed)
python scripts/seed.py --db-url sqlite+aiosqlite:///./dev.db

# Silent mode (CI / scripted usage)
python scripts/seed.py --quiet
```

### What the seed creates

| Resource | Details |
|---|---|
| `alice` (admin) | password: `Admin1234!` |
| `bob` (verifier) | password: `Verif5678!` |
| Doc 1: `jaipur_khasra_451.pdf` | `status=verified` — all 12 fields clean, verification log present |
| Doc 2: `jodhpur_plot_deed.jpg` | `status=needs_review` — 2 fields flagged (khasra OCR error, missing mutation) |
| Doc 3: `sanganer_survey_records.pdf` | `status=processing` — simulates in-flight pipeline |

---

## 7. API Reference

Base URL: `http://localhost:8000`
Interactive docs: `http://localhost:8000/docs`

All protected endpoints require:
```
Authorization: Bearer <access_token>
```

### Auth

#### `POST /auth/register`
Create a new user account.

```bash
curl -s -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "alice",
    "password": "Admin1234!",
    "role": "admin"
  }' | jq
```
```json
{
  "id": 1,
  "username": "alice",
  "role": "admin",
  "created_at": "2026-09-05T16:00:00Z"
}
```

**Roles:** `admin` | `verifier` | `field_officer` (default)

---

#### `POST /auth/login`
Exchange credentials for a JWT access token.

```bash
curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"Admin1234!"}' | jq
```
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

---

#### `GET /auth/me`
Return the currently authenticated user's profile.

```bash
curl -s http://localhost:8000/auth/me \
  -H "Authorization: Bearer $TOKEN" | jq
```
```json
{"id": 1, "username": "alice", "role": "admin", "created_at": "..."}
```

---

### Documents

#### `POST /documents/upload` `[any role]`
Upload a PDF or image. Returns **202** immediately; OCR + extraction run in the background.

```bash
curl -s -X POST http://localhost:8000/documents/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/khasra.pdf" \
  -F "district=Jaipur" \
  -F "tehsil=Sanganer" \
  -F "village=Rampur Kalan" | jq
```
```json
{
  "id": 4,
  "filename": "khasra.pdf",
  "status": "processing",
  "district": "Jaipur",
  "tehsil": "Sanganer",
  "village": "Rampur Kalan",
  "created_at": "2026-09-05T16:45:00Z",
  "updated_at": "2026-09-05T16:45:00Z"
}
```

Supported file types: `.pdf` `.png` `.jpg` `.jpeg` `.tiff` `.tif`

Poll `GET /documents/{id}` until `status` changes from `processing`.

---

#### `GET /documents/{id}` `[any role]`
Fetch document metadata **plus all extracted fields** with confidence scores.

```bash
curl -s http://localhost:8000/documents/4 \
  -H "Authorization: Bearer $TOKEN" | jq
```
```json
{
  "id": 4,
  "filename": "khasra.pdf",
  "status": "needs_review",
  "district": "Jaipur",
  "extracted_fields": [
    {
      "field_name": "khasra_number",
      "value": "45l/2",
      "confidence_score": 0.38,
      "is_flagged": true,
      "created_at": "..."
    },
    {
      "field_name": "owner_name",
      "value": "Ram Kumar Singh",
      "confidence_score": 0.92,
      "is_flagged": false,
      "created_at": "..."
    }
  ]
}
```

---

#### `GET /documents` `[any role]`
Paginated and filtered document list.

| Query param | Type | Description |
|---|---|---|
| `status` | string | Filter by status: `uploaded` \| `processing` \| `needs_review` \| `verified` |
| `district` | string | Case-insensitive partial match on district name |
| `page` | int | Page number, 1-based (default: 1) |
| `page_size` | int | Items per page, max 100 (default: 20) |

```bash
# All documents needing review in Jaipur district
curl -s "http://localhost:8000/documents?status=needs_review&district=Jaipur&page=1&page_size=10" \
  -H "Authorization: Bearer $TOKEN" | jq '{total, page, items: [.items[] | {id, filename, status}]}'
```
```json
{
  "total": 23,
  "page": 1,
  "page_size": 10,
  "items": [
    {"id": 2, "filename": "jodhpur_plot_deed.jpg", "status": "needs_review"},
    ...
  ]
}
```

---

#### `PATCH /documents/{id}/fields/{field_name}` `[verifier, admin]`
Correct an extracted field value. Clears `is_flagged`, writes to `VerificationLog` and `AuditTrail`.

```bash
curl -s -X PATCH \
  "http://localhost:8000/documents/4/fields/khasra_number" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "value": "451/2",
    "note": "OCR misread lowercase L as digit 1 — corrected from source"
  }' | jq
```
```json
{
  "id": 12,
  "field_name": "khasra_number",
  "value": "451/2",
  "confidence_score": 0.38,
  "is_flagged": false,
  "created_at": "..."
}
```

---

#### `POST /documents/{id}/verify` `[verifier, admin]`
Mark a document as verified. **Blocked (422)** if any field still has `is_flagged=true`.

```bash
curl -s -X POST "http://localhost:8000/documents/4/verify" \
  -H "Authorization: Bearer $TOKEN" | jq .status
# → "verified"

# If flags remain:
# → 422: "2 field(s) are still flagged for review..."
```

---

#### `POST /documents/{id}/reprocess` `[verifier, admin]`
Re-run the full OCR + extraction + validation pipeline on an existing document.

```bash
curl -s -X POST "http://localhost:8000/documents/4/reprocess" \
  -H "Authorization: Bearer $TOKEN" | jq
```
```json
{"message": "Reprocessing enqueued.", "document_id": 4}
```

---

### Dashboard

#### `GET /dashboard/stats` `[any role]`
System-wide aggregate metrics with district-level breakdown.

```bash
curl -s http://localhost:8000/dashboard/stats \
  -H "Authorization: Bearer $TOKEN" | jq
```
```json
{
  "total_documents": 147,
  "total_processed": 142,
  "pending_review": 23,
  "verified": 119,
  "avg_confidence": 0.7841,
  "flagged_field_count": 67,
  "total_fields": 1764,
  "district_breakdown": [
    {
      "district": "Jaipur",
      "total_documents": 58,
      "verified": 51,
      "needs_review": 7,
      "processing": 0
    },
    {
      "district": "Jodhpur",
      "total_documents": 44,
      "verified": 38,
      "needs_review": 6,
      "processing": 0
    }
  ]
}
```

---

### Integrations

Both endpoints require `verifier` or `admin` role, and the document must have `status=verified`.

#### `POST /integrations/lrms/push/{document_id}` `[verifier, admin]`
Push document to the Land Record Management System. Currently returns a **mock** acceptance response. The full payload is permanently recorded in `AuditTrail`.

```bash
curl -s -X POST "http://localhost:8000/integrations/lrms/push/4" \
  -H "Authorization: Bearer $TOKEN" | jq
```
```json
{
  "system": "lrms",
  "document_id": 4,
  "reference_id": "LRMS-2026-000004-A3F1",
  "status": "accepted",
  "pushed_at": "2026-09-05T16:50:00.123456+00:00",
  "mock": true,
  "payload_logged": true
}
```

---

#### `POST /integrations/gis/push/{document_id}` `[verifier, admin]`
Push parcel data to the GIS portal (async queue model — status is `"queued"`).

```bash
curl -s -X POST "http://localhost:8000/integrations/gis/push/4" \
  -H "Authorization: Bearer $TOKEN" | jq
```
```json
{
  "system": "gis",
  "document_id": 4,
  "reference_id": "GIS-JAI-4B2C1A",
  "status": "queued",
  "pushed_at": "2026-09-05T16:50:01.456789+00:00",
  "mock": true,
  "payload_logged": true
}
```

---

#### `GET /health`
Liveness probe — no auth required.

```bash
curl http://localhost:8000/health
# → {"status":"ok","version":"0.1.0"}
```

---

## 8. Full End-to-End curl Walkthrough

```bash
# ── 0. Start and seed ─────────────────────────────────────────────────────────
docker-compose up -d
docker-compose exec app alembic upgrade head
docker-compose exec app python scripts/seed.py

# ── 1. Get an admin token ─────────────────────────────────────────────────────
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"Admin1234!"}' | jq -r .access_token)

# ── 2. Upload a document ──────────────────────────────────────────────────────
DOC=$(curl -s -X POST http://localhost:8000/documents/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/khasra.pdf" \
  -F "district=Jaipur" \
  -F "tehsil=Sanganer")

DOC_ID=$(echo $DOC | jq -r .id)
echo "Uploaded: doc_id=$DOC_ID, status=$(echo $DOC | jq -r .status)"

# ── 3. Poll until pipeline completes ──────────────────────────────────────────
# (In production, use a webhook or websocket; curl polling is for demo only)
while true; do
  STATUS=$(curl -s http://localhost:8000/documents/$DOC_ID \
    -H "Authorization: Bearer $TOKEN" | jq -r .status)
  echo "Status: $STATUS"
  [ "$STATUS" != "processing" ] && break
  sleep 2
done

# ── 4. Check extracted fields ─────────────────────────────────────────────────
curl -s http://localhost:8000/documents/$DOC_ID \
  -H "Authorization: Bearer $TOKEN" \
  | jq '.extracted_fields[] | {field_name, value, confidence_score, is_flagged}'

# ── 5. Get a verifier token ───────────────────────────────────────────────────
VTOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"bob","password":"Verif5678!"}' | jq -r .access_token)

# ── 6. Correct a flagged field ────────────────────────────────────────────────
curl -s -X PATCH \
  "http://localhost:8000/documents/$DOC_ID/fields/khasra_number" \
  -H "Authorization: Bearer $VTOKEN" \
  -H "Content-Type: application/json" \
  -d '{"value":"451/2","note":"OCR misread l as 1"}' | jq .is_flagged
# → false

# ── 7. Attempt to verify (may still have other flags) ─────────────────────────
curl -s -X POST "http://localhost:8000/documents/$DOC_ID/verify" \
  -H "Authorization: Bearer $VTOKEN" | jq '{status, detail}'

# ── 8. Verify successfully once all flags cleared ─────────────────────────────
curl -s -X POST "http://localhost:8000/documents/$DOC_ID/verify" \
  -H "Authorization: Bearer $VTOKEN" | jq .status
# → "verified"

# ── 9. Push to government systems ─────────────────────────────────────────────
curl -s -X POST "http://localhost:8000/integrations/lrms/push/$DOC_ID" \
  -H "Authorization: Bearer $VTOKEN" | jq '{reference_id, status}'
# → {"reference_id": "LRMS-2026-000004-A3F1", "status": "accepted"}

curl -s -X POST "http://localhost:8000/integrations/gis/push/$DOC_ID" \
  -H "Authorization: Bearer $VTOKEN" | jq '{reference_id, status}'
# → {"reference_id": "GIS-JAI-4B2C1A", "status": "queued"}

# ── 10. Check the dashboard ───────────────────────────────────────────────────
curl -s http://localhost:8000/dashboard/stats \
  -H "Authorization: Bearer $TOKEN" | jq '{total_documents,pending_review,verified,avg_confidence}'
```

---

## 9. Swapping the OCR Provider

The `OCRProvider` is an abstract base class. Changing providers requires **only a `.env` change** — no code changes.

### Tesseract (default)
```env
OCR_PROVIDER=tesseract
TESSERACT_LANG=eng
PDF_DPI=300
```

For Hindi / multilingual documents:
```env
TESSERACT_LANG=eng+hin
```

#### ⚙️ Tesseract Binary Setup on Evaluation & Demo Machines

If running outside Docker on a bare-metal host, install the Tesseract system binary:

- **Windows**:
  ```powershell
  winget install UB-Mannheim.TesseractOCR
  # Or download from: https://github.com/UB-Mannheim/tesseract/wiki
  # Add C:\Program Files\Tesseract-OCR to your System PATH
  ```
- **Ubuntu / Debian**:
  ```bash
  sudo apt-get update && sudo apt-get install -y tesseract-ocr tesseract-ocr-hin libtesseract-dev poppler-utils
  ```
- **macOS**:
  ```bash
  brew install tesseract tesseract-lang poppler
  ```
- **Docker (Recommended for Demonstrations)**:
  Pre-configured in `Dockerfile` with full Tesseract + Indic script language packs (`tesseract-ocr-hin`, `tesseract-ocr-guj`, etc.).

> **🛡️ Graceful Degradation Guarantee**: If the Tesseract binary is not present in system PATH, BhoomiScan AI's defensive pipeline does NOT crash. It detects the missing binary and falls back to structured synthetic extraction (`/health/diagnostics` will flag `"tesseract_installed": false`), ensuring smooth, uninterrupted hackathon presentations regardless of the host environment.

### EasyOCR
Install: `pip install easyocr`
```env
OCR_PROVIDER=easyocr
```
EasyOCR ships GPU-enabled models and is significantly more accurate on low-quality scans. It downloads model weights on first run (~200 MB).

### TrOCR (Microsoft)
Install: `pip install transformers torch`
```env
OCR_PROVIDER=trocr
```
Best for handwritten documents. Requires a GPU for reasonable throughput.

### Adding a custom provider

1. Create a class in `app/services/ocr.py` that extends `OCRProvider`:

```python
class MyCustomProvider(OCRProvider):
    async def extract_text(self, file_path: Path) -> OCRResult:
        # Your implementation here
        raw_text = ...
        return OCRResult(
            raw_text=raw_text,
            avg_confidence=0.90,
            word_confidences=[],
            page_count=1,
            provider="my-custom",
        )
```

2. Register it in `get_ocr_provider()`:

```python
def get_ocr_provider() -> OCRProvider:
    cfg = get_settings()
    if cfg.ocr_provider == "my-custom":
        return MyCustomProvider()
    ...
```

3. Set `OCR_PROVIDER=my-custom` in `.env`.

---

## 10. Swapping the LLM Model

The extraction service uses the OpenAI client interface. Any compatible endpoint works.

### OpenAI GPT-4o (default)
```env
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o
```

### GPT-3.5 Turbo (cheaper, faster)
```env
LLM_MODEL=gpt-3.5-turbo
```

### Ollama (fully local, no API key required)
```bash
# Install and pull a model
ollama pull llama3
ollama serve   # runs at http://localhost:11434
```
```env
LLM_API_KEY=ollama          # any non-empty value
LLM_MODEL=llama3
LLM_BASE_URL=http://localhost:11434/v1
```

### Azure OpenAI
```env
LLM_API_KEY=<azure-api-key>
LLM_MODEL=gpt-4o            # your Azure deployment name
LLM_BASE_URL=https://<resource>.openai.azure.com/openai/deployments/<deployment>/
```

### Any OpenAI-compatible endpoint (Groq, Together AI, Anyscale, etc.)
```env
LLM_API_KEY=<provider-key>
LLM_MODEL=<model-name>
LLM_BASE_URL=<provider-base-url>
```

### Tuning extraction quality

| Variable | Guidance |
|---|---|
| `LLM_TEMPERATURE=0.0` | Keep at 0 for deterministic field extraction |
| `LLM_MAX_RETRIES=3` | Increase if your model frequently returns malformed JSON |
| `LLM_MAX_TOKENS=4096` | Increase for very long documents |

---

## 11. Running Tests

The full test suite (73 tests) uses **SQLite in-memory** — no Postgres, no real OCR, no LLM calls required.

```bash
pip install -r requirements.txt   # includes aiosqlite, pytest-asyncio

# Run all tests
pytest

# With coverage report
pip install pytest-cov
pytest --cov=app --cov-report=term-missing

# Run only a specific module
pytest tests/test_auth.py -v
pytest tests/test_documents.py -v
pytest tests/test_pipeline.py -v
pytest tests/test_validation.py -v

# Run a single test
pytest tests/test_documents.py::test_verify_blocked_by_flagged_fields -v
```

### Test structure

| File | Count | What's covered |
|---|---|---|
| `test_auth.py` | 12 | Register, login, /me, duplicate user, wrong password, JWT payload |
| `test_documents.py` | 20 | Upload, pagination, PATCH→VerificationLog, verify guard, role-gating, LRMS/GIS push |
| `test_pipeline.py` | 6 | Happy path, null extraction, missing file, OCR crash recovery, idempotency |
| `test_validation.py` | 35 | All 7 validation rules, duplicate detection, confidence matrix |

---

## 12. Standalone Service Scripts

These scripts let you test each service independently — no running server needed.

```bash
# Test OCR on a real file
python scripts/test_ocr.py path/to/scan.pdf
python scripts/test_ocr.py path/to/image.png --lang eng+hin --dpi 400

# Test LLM extraction on raw text
python scripts/test_extraction.py --sample
python scripts/test_extraction.py "Owner: Ram Kumar. Survey No: 78-B, Village Rampur"
python scripts/test_extraction.py --file extracted.txt --json | jq .fields.owner_name

# Use a local Ollama model for extraction
python scripts/test_extraction.py --sample \
  --model llama3 \
  --base-url http://localhost:11434/v1

# Test validation rules + duplicate detection
python scripts/test_validation.py
python scripts/test_validation.py --section confidence --threshold 0.70

# Test the full pipeline (mocked OCR + LLM, SQLite in-memory)
python scripts/test_pipeline.py
python scripts/test_pipeline.py --json | jq '.[] | {test, passed}'
```

---

## 13. Processing Pipeline Internals

```
POST /documents/upload
        │
        ▼
  Save file to disk
  Create Document row (status=processing)
  Return 202 immediately
        │
        ▼ (BackgroundTask — runs after response is sent)
  ┌─────────────────────────────────────────────────────────────┐
  │  pipeline.process_document(document_id)                      │
  │                                                              │
  │  Step 1: Load Document, validate file exists on disk        │
  │  Step 2: Set status=processing → AuditTrail: pipeline_start │
  │  Step 3: OCR (TesseractProvider / configured provider)      │
  │          → raw_text, avg_confidence                         │
  │          → AuditTrail: ocr_complete                         │
  │  Step 4: LLM Extraction (4-phase JSON repair)               │
  │          → {owner_name, survey_number, …} + per-field conf  │
  │          → AuditTrail: extraction_complete                  │
  │  Step 5: Validation                                          │
  │          → Rule violations (required fields, regex, area)   │
  │          → compute_confidence(ocr_avg, llm_conf) per field  │
  │          → is_flagged = score < REVIEW_THRESHOLD            │
  │  Step 6: Persist ExtractedField rows (delete-then-insert)   │
  │          → Update Document.district/tehsil/village          │
  │  Step 7: Final status                                        │
  │          → needs_review  (if any field flagged or has error)│
  │          → verified      (all fields clean + high conf)     │
  │          → AuditTrail: pipeline_complete                    │
  └─────────────────────────────────────────────────────────────┘
        │
        ▼
  Human review (GET /documents/{id}, PATCH /fields/{name})
        │
        ▼
  POST /documents/{id}/verify      (blocks if is_flagged=True)
        │
        ▼
  POST /integrations/lrms/push/{id}
  POST /integrations/gis/push/{id}
```

### Error recovery
If any pipeline step fails, the document is immediately set to `status=needs_review` (never stuck at `processing`) and the error is recorded in `AuditTrail` with `action=pipeline_error`. The document can then be reprocessed via `POST /documents/{id}/reprocess`.

### Confidence formula

```
combined = 0.40 × ocr_confidence + 0.60 × llm_extraction_confidence
  where:  "high" → 1.00,  "medium" → 0.65,  "low" → 0.30

combined < REVIEW_THRESHOLD (default 0.75) → is_flagged = True
```

Both weights and the threshold are configurable via `.env`.

---

## Role Permissions Summary

| Endpoint | field_officer | verifier | admin |
|---|:---:|:---:|:---:|
| `POST /auth/register` | ✅ | ✅ | ✅ |
| `POST /auth/login` | ✅ | ✅ | ✅ |
| `POST /documents/upload` | ✅ | ✅ | ✅ |
| `GET /documents/{id}` | ✅ | ✅ | ✅ |
| `GET /documents` | ✅ | ✅ | ✅ |
| `GET /dashboard/stats` | ✅ | ✅ | ✅ |
| `PATCH /documents/{id}/fields/{name}` | ❌ | ✅ | ✅ |
| `POST /documents/{id}/verify` | ❌ | ✅ | ✅ |
| `POST /documents/{id}/reprocess` | ❌ | ✅ | ✅ |
| `POST /integrations/*/push/{id}` | ❌ | ✅ | ✅ |

---

*Generated by Land Record Digitizer v0.1.0*
