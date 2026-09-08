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
from app.services.pipeline import process_document
from app.main import app

async def run_real_data_dashboard_audit():
    async with AsyncSessionLocal() as db:
        # Create or fetch users
        async def get_or_create_user(username: str, role: UserRole) -> User:
            stmt = select(User).where(User.username == username)
            u = (await db.execute(stmt)).scalar_one_or_none()
            if not u:
                u = User(username=username, password_hash=hash_password("Pass123!"), role=role)
                db.add(u)
                await db.commit()
                await db.refresh(u)
            return u

        officer_jaipur = await get_or_create_user("patwari_jaipur", UserRole.field_officer)
        officer_jodhpur = await get_or_create_user("patwari_jodhpur", UserRole.field_officer)
        verifier_state = await get_or_create_user("tehsildar_state", UserRole.verifier)

        # File paths for real demo assets
        asset_1 = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../demo_assets/01_clean_jaipur_khasra.pdf"))
        asset_2 = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../demo_assets/02_degraded_jodhpur_plot_deed.jpg"))

        # Clean old docs for these specific demo runs
        await db.execute(delete(Document).where(Document.uploaded_by.in_([officer_jaipur.id, officer_jodhpur.id])))
        await db.commit()

        # Ingest Document 1 under patwari_jaipur
        doc_1 = Document(
            filename="01_clean_jaipur_khasra.pdf",
            storage_path=asset_1,
            uploaded_by=officer_jaipur.id,
            status=DocumentStatus.uploaded,
            district="Jaipur",
            tehsil="Sanganer",
            village="Shyopur",
        )
        db.add(doc_1)
        await db.commit()
        await db.refresh(doc_1)

        # Ingest Document 2 under patwari_jodhpur
        doc_2 = Document(
            filename="02_degraded_jodhpur_plot_deed.jpg",
            storage_path=asset_2,
            uploaded_by=officer_jodhpur.id,
            status=DocumentStatus.uploaded,
            district="Jodhpur",
            tehsil="Luni",
            village="Mandore",
        )
        db.add(doc_2)
        await db.commit()
        await db.refresh(doc_2)

    # Run real pipeline for both documents (populates ExtractedField rows with actual OCR/heuristic scores)
    print(f"Processing Document 1 (ID: {doc_1.id}) through full pipeline...")
    res_1 = await process_document(doc_1.id, triggered_by_user_id=officer_jaipur.id)
    print(f"Doc 1 pipeline finished: status={res_1.final_status}, fields_saved={res_1.fields_saved}, ocr_conf={res_1.ocr_avg_confidence:.4f}")

    print(f"Processing Document 2 (ID: {doc_2.id}) through full pipeline...")
    res_2 = await process_document(doc_2.id, triggered_by_user_id=officer_jodhpur.id)
    print(f"Doc 2 pipeline finished: status={res_2.final_status}, fields_saved={res_2.fields_saved}, ocr_conf={res_2.ocr_avg_confidence:.4f}")

    # Generate tokens
    token_jaipur = create_access_token(str(officer_jaipur.id))
    token_jodhpur = create_access_token(str(officer_jodhpur.id))
    token_verifier = create_access_token(str(verifier_state.id))

    # Test GET /dashboard/stats with real extracted fields in the database
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        r_jaipur = await client.get("/api/v1/dashboard/stats", headers={"Authorization": f"Bearer {token_jaipur}"})
        r_jodhpur = await client.get("/api/v1/dashboard/stats", headers={"Authorization": f"Bearer {token_jodhpur}"})
        r_state = await client.get("/api/v1/dashboard/stats", headers={"Authorization": f"Bearer {token_verifier}"})

    print("\n=================================================================")
    print("DASHBOARD STATS WITH REAL PIPELINE EXTRACTED FIELDS IN DB")
    print("=================================================================")

    print("\n--- 1. Field Officer Jaipur (patwari_jaipur) ---")
    print(f"HTTP Status: {r_jaipur.status_code}")
    print(json.dumps(r_jaipur.json(), indent=2))

    print("\n--- 2. Field Officer Jodhpur (patwari_jodhpur) ---")
    print(f"HTTP Status: {r_jodhpur.status_code}")
    print(json.dumps(r_jodhpur.json(), indent=2))

    print("\n--- 3. Verifying Officer (State-Wide Global Scope) ---")
    print(f"HTTP Status: {r_state.status_code}")
    print(json.dumps(r_state.json(), indent=2))

if __name__ == "__main__":
    asyncio.run(run_real_data_dashboard_audit())
