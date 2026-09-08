import asyncio
import os
import sys
import json
import httpx
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import AsyncSessionLocal
from app.models.document import Document, DocumentStatus
from app.models.user import User, UserRole
from app.models.extracted_field import ExtractedField
from app.core.security import hash_password, create_access_token
from app.main import app

async def run_scoping_audit():
    async with AsyncSessionLocal() as db:
        # Create users
        async def get_or_create_user(username: str, role: UserRole) -> User:
            stmt = select(User).where(User.username == username)
            u = (await db.execute(stmt)).scalar_one_or_none()
            if not u:
                u = User(username=username, password_hash=hash_password("Pass123!"), role=role)
                db.add(u)
                await db.commit()
                await db.refresh(u)
            return u

        officer_1 = await get_or_create_user("scoping_officer_jaipur", UserRole.field_officer)
        officer_2 = await get_or_create_user("scoping_officer_jodhpur", UserRole.field_officer)
        verifier_1 = await get_or_create_user("scoping_verifier_state", UserRole.verifier)
        admin_1 = await get_or_create_user("scoping_admin_state", UserRole.admin)

        # Clear existing docs for these test users
        await db.execute(delete(Document).where(Document.uploaded_by.in_([officer_1.id, officer_2.id])))
        await db.commit()

        # Seed docs for officer 1 (Jaipur)
        doc_1a = Document(filename="jaipur_deed_1.pdf", storage_path="/dummy/1.pdf", uploaded_by=officer_1.id, status=DocumentStatus.verified, district="Jaipur", tehsil="Sanganer")
        doc_1b = Document(filename="jaipur_deed_2.pdf", storage_path="/dummy/2.pdf", uploaded_by=officer_1.id, status=DocumentStatus.needs_review, district="Jaipur", tehsil="Amer")
        db.add_all([doc_1a, doc_1b])
        await db.flush()

        # Seed docs for officer 2 (Jodhpur)
        doc_2a = Document(filename="jodhpur_deed_1.pdf", storage_path="/dummy/3.pdf", uploaded_by=officer_2.id, status=DocumentStatus.verified, district="Jodhpur", tehsil="Luni")
        doc_2b = Document(filename="jodhpur_deed_2.pdf", storage_path="/dummy/4.pdf", uploaded_by=officer_2.id, status=DocumentStatus.verified, district="Jodhpur", tehsil="Luni")
        doc_2c = Document(filename="jodhpur_deed_3.pdf", storage_path="/dummy/5.pdf", uploaded_by=officer_2.id, status=DocumentStatus.needs_review, district="Jodhpur", tehsil="Phalodi")
        db.add_all([doc_2a, doc_2b, doc_2c])
        await db.commit()

    # Generate tokens
    token_officer_1 = create_access_token(str(officer_1.id))
    token_officer_2 = create_access_token(str(officer_2.id))
    token_verifier_1 = create_access_token(str(verifier_1.id))
    token_admin_1 = create_access_token(str(admin_1.id))

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Call as officer 1
        r1 = await client.get("/api/v1/dashboard/stats", headers={"Authorization": f"Bearer {token_officer_1}"})
        # Call as officer 2
        r2 = await client.get("/api/v1/dashboard/stats", headers={"Authorization": f"Bearer {token_officer_2}"})
        # Call as verifier
        r_ver = await client.get("/api/v1/dashboard/stats", headers={"Authorization": f"Bearer {token_verifier_1}"})
        # Call as admin
        r_adm = await client.get("/api/v1/dashboard/stats", headers={"Authorization": f"Bearer {token_admin_1}"})

    print("=== DASHBOARD SCOPING AUDIT LIVE RESULTS ===")
    print("\n--- 1. Field Officer 1 (Jaipur) Response ---")
    print(f"Status: {r1.status_code}")
    print(json.dumps(r1.json(), indent=2))

    print("\n--- 2. Field Officer 2 (Jodhpur) Response ---")
    print(f"Status: {r2.status_code}")
    print(json.dumps(r2.json(), indent=2))

    print("\n--- 3. Verifier (State Level) Response ---")
    print(f"Status: {r_ver.status_code}")
    print(json.dumps(r_ver.json(), indent=2))

    print("\n--- 4. Admin (State Level) Response ---")
    print(f"Status: {r_adm.status_code}")
    print(json.dumps(r_adm.json(), indent=2))

if __name__ == "__main__":
    asyncio.run(run_scoping_audit())
