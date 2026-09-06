# TechVanta — BhoomiScan AI

> **Smart India Hackathon (SIH) Solution**: Enterprise Land Record Digitization, Real-Time Verification, and Legal Governance Platform.

---

## 🏗️ Repository Architecture

```
TechVanta/
├── backend/                # FastAPI async backend service
│   ├── app/                # Application modules (API, core, DB, models, schemas, services)
│   ├── alembic/            # Database schema migrations
│   ├── scripts/            # Standalone service tests & seed demo data
│   ├── tests/              # Pytest test suite (86/86 passing)
│   ├── Dockerfile          # Production multi-stage Docker container
│   ├── docker-compose.yml  # Compose configuration with PostgreSQL
│   ├── requirements.txt    # Python dependencies
│   └── README.md           # In-depth backend architecture & API reference
│
└── frontend/               # User interface (Patwari / Verifier Workspace)
```

---

## 🚀 Quick Start (Backend)

1. **Navigate to the backend directory:**
   ```bash
   cd backend
   ```

2. **Set up environment:**
   ```bash
   cp .env.example .env
   pip install -r requirements.txt
   ```

3. **Run database migrations & seed demo data:**
   ```bash
   alembic upgrade head
   python scripts/seed.py
   ```

4. **Start the API server:**
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

5. **Access the application:**
   - **Interactive Verifier UI**: [http://localhost:8000/](http://localhost:8000/)
   - **Interactive API Docs (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
   - **System Diagnostics**: [http://localhost:8000/health/diagnostics](http://localhost:8000/health/diagnostics)

---

## 🧪 Automated Tests

Run the test suite across Auth, Upload, Validation, Pipeline, DILRMP, Integrity, and Streaming:
```bash
cd backend
pytest -v
```
*(86 tests passed, 0 failures)*
