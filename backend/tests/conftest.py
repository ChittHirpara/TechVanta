"""
Pytest configuration and shared fixtures.

DB strategy: SQLite in-memory with StaticPool so all connections share the
same in-memory database.  Each test function gets a fresh engine → perfect
isolation without requiring a live Postgres server.

Env vars are injected before any app module is imported so that
pydantic-settings / lru_cache picks them up correctly.
"""
import asyncio
import os

# ── Inject minimal env vars BEFORE any app import ────────────────────────────
os.environ.setdefault("JWT_SECRET",    "pytest-secret-do-not-use-in-prod")
os.environ.setdefault("DB_URL",        "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("LLM_API_KEY",   "sk-test-fake-key")
# Disable rate limiting during tests: set very high limits so the test suite
# can call /auth/login and /documents/upload many times without hitting 429s.
os.environ.setdefault("RATE_LIMIT_LOGIN",  "10000/minute")
os.environ.setdefault("RATE_LIMIT_UPLOAD", "10000/minute")
os.environ.setdefault("RATE_LIMIT_API",    "10000/minute")

# ── Standard imports (after env setup) ───────────────────────────────────────
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 – registers all ORM models with Base.metadata
from app.db.session import Base, get_db
from app.main import app

# ─────────────────────────────────────────────────────────────────────────────
# Rate limiter reset fixture
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_rate_limits():
    """
    Reset the slowapi in-memory counter storage before every test.

    Without this, tests accumulate login/upload calls across the session and
    eventually hit the per-IP rate limits (e.g. 10 logins/minute) causing
    spurious 429 failures in fixture setup.

    MemoryStorage.reset() clears all internal dicts (storage, expirations,
    events, locks) giving each test a fresh slate while keeping rate limiting
    code fully exercised.
    """
    from app.core.limiter import limiter
    try:
        limiter._storage.reset()   # type: ignore[attr-defined]
    except AttributeError:
        # Redis backend — don't flush in tests (shouldn't be configured in CI)
        pass

# ─────────────────────────────────────────────────────────────────────────────
# Engine / session fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
async def engine():
    """
    Fresh SQLite in-memory engine per test function.
    StaticPool ensures every connection shares the same in-memory database.
    """
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
async def db(engine) -> AsyncSession:
    """
    A raw AsyncSession connected to the test engine.
    Use this for direct DB assertions in tests.
    """
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    async with SessionLocal() as session:
        yield session


@pytest.fixture
async def client(engine) -> AsyncClient:
    """
    httpx AsyncClient with the FastAPI app wired to the test engine.

    Overrides the ``get_db`` dependency so every request handler gets a
    session from the same in-memory engine as the test fixtures.
    """
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async def _override_get_db():
        async with SessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)


# ─────────────────────────────────────────────────────────────────────────────
# Auth helper fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
async def admin_token(client: AsyncClient) -> str:
    """Register an admin user and return a valid Bearer token."""
    await client.post("/api/v1/auth/register", json={
        "username": "alice_admin",
        "password": "Admin1234!",
        "role": "admin",
    })
    resp = await client.post("/api/v1/auth/login", json={
        "username": "alice_admin",
        "password": "Admin1234!",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture
async def verifier_token(client: AsyncClient) -> str:
    """Register a verifier user and return a valid Bearer token."""
    await client.post("/api/v1/auth/register", json={
        "username": "bob_verifier",
        "password": "Verif5678!",
        "role": "verifier",
    })
    resp = await client.post("/api/v1/auth/login", json={
        "username": "bob_verifier",
        "password": "Verif5678!",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.fixture
async def field_officer_token(client: AsyncClient) -> str:
    """Register a field officer and return a valid Bearer token."""
    await client.post("/api/v1/auth/register", json={
        "username": "carol_officer",
        "password": "Officer99!",
        "role": "field_officer",
    })
    resp = await client.post("/api/v1/auth/login", json={
        "username": "carol_officer",
        "password": "Officer99!",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


# ─────────────────────────────────────────────────────────────────────────────
# Document / data fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
async def seeded_document(db: AsyncSession, engine) -> dict:
    """
    Insert a Document + 3 ExtractedField rows (one flagged) directly into
    the test DB.  Returns a dict with document metadata for assertion use.
    """
    from app.models.document import Document, DocumentStatus
    from app.models.extracted_field import ExtractedField

    doc = Document(
        filename="test_deed.pdf",
        storage_path="/tmp/test_deed.pdf",
        uploaded_by=None,
        status=DocumentStatus.needs_review,
        district="Jaipur",
        tehsil="Sanganer",
        village="Rampur Kalan",
    )
    db.add(doc)
    await db.flush()

    fields = [
        ExtractedField(document_id=doc.id, field_name="owner_name",
                       value="Ram Kumar Singh", confidence_score=0.92, is_flagged=False),
        ExtractedField(document_id=doc.id, field_name="survey_number",
                       value="78-B", confidence_score=0.88, is_flagged=False),
        ExtractedField(document_id=doc.id, field_name="khasra_number",
                       value="45l/2",  # OCR error – should be 451/2
                       confidence_score=0.41, is_flagged=True),
        ExtractedField(document_id=doc.id, field_name="district",
                       value="Jaipur", confidence_score=0.95, is_flagged=False),
        ExtractedField(document_id=doc.id, field_name="tehsil",
                       value="Sanganer", confidence_score=0.95, is_flagged=False),
        ExtractedField(document_id=doc.id, field_name="village",
                       value="Rampur Kalan", confidence_score=0.90, is_flagged=False),
        ExtractedField(document_id=doc.id, field_name="plot_area",
                       value="2 Bigha 14 Biswa", confidence_score=0.80, is_flagged=False),
    ]
    for f in fields:
        db.add(f)
    await db.commit()
    await db.refresh(doc)

    return {"id": doc.id, "status": doc.status.value, "flagged_field": "khasra_number"}
