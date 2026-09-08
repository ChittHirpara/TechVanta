import asyncio
import os
import sys
import json
import httpx
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

# Ensure backend directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import get_settings
settings = get_settings()
from app.models.document import Document, DocumentStatus
from app.models.extracted_field import ExtractedField
from app.models.user import User, UserRole
from app.core.security import hash_password, create_access_token
from app.services.dilrmp import compute_file_sha256, generate_ulpin
from app.services.certificate_service import generate_certificate_html
from app.main import app
from app.db.session import AsyncSessionLocal

async def run_public_verify_audit():
    # 1. Setup DB session to ensure we have a verified document with real demo asset
    demo_asset_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../demo_assets/01_clean_jaipur_khasra.pdf"))
    actual_sha256 = compute_file_sha256(demo_asset_path)

    async with AsyncSessionLocal() as db:
        # Create or fetch verifier
        stmt = select(User).where(User.username == "audit_verifier")
        verifier = (await db.execute(stmt)).scalar_one_or_none()
        if not verifier:
            verifier = User(
                username="audit_verifier",
                password_hash=hash_password("VerifierPass123!"),
                role=UserRole.verifier,
            )
            db.add(verifier)
            await db.commit()
            await db.refresh(verifier)

        # Create or fetch verified document
        stmt = select(Document).where(Document.filename == "01_clean_jaipur_khasra.pdf", Document.status == DocumentStatus.verified)
        doc = (await db.execute(stmt)).scalars().first()
        if not doc:
            doc = Document(
                filename="01_clean_jaipur_khasra.pdf",
                storage_path=demo_asset_path,
                uploaded_by=verifier.id,
                status=DocumentStatus.verified,
                district="Jaipur",
                tehsil="Sanganer",
                village="Shyopur"
            )
            db.add(doc)
            await db.commit()
            await db.refresh(doc)
            
            # Add fields
            f1 = ExtractedField(document_id=doc.id, field_name="owner_name", value="Rameshwar Prasad Sharma", confidence_score=0.98)
            f2 = ExtractedField(document_id=doc.id, field_name="khasra_number", value="412/1", confidence_score=0.99)
            f3 = ExtractedField(document_id=doc.id, field_name="survey_number", value="SN-2023-8871", confidence_score=0.95)
            f4 = ExtractedField(document_id=doc.id, field_name="plot_area", value="2.45 Hectares", confidence_score=0.97)
            db.add_all([f1, f2, f3, f4])
            await db.commit()

        # Compute ULPIN
        stmt = select(ExtractedField).where(ExtractedField.document_id == doc.id)
        fields = (await db.execute(stmt)).scalars().all()
        field_map = {f.field_name: f.value for f in fields}
        ulpin = generate_ulpin(
            district=doc.district or field_map.get("district"),
            tehsil=doc.tehsil or field_map.get("tehsil"),
            village=doc.village or field_map.get("village"),
            khasra_number=field_map.get("khasra_number"),
            survey_number=field_map.get("survey_number"),
        )

    # 2. Check QR generation and URL structure in certificate_service
    html_cert = generate_certificate_html(doc, fields)
    
    # 3. Test the public verification endpoint via httpx ASGITransport (no auth headers!)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Test full 64-char hash
        url_full = f"/api/v1/documents/public/verify/{ulpin}/{actual_sha256}"
        resp_full = await client.get(url_full)
        
        # Test 16-char prefix (from certificate default qr_data)
        hash_prefix_16 = actual_sha256[:16]
        url_prefix = f"/api/v1/documents/public/verify/{ulpin}/{hash_prefix_16}"
        resp_prefix = await client.get(url_prefix)
        
        # Test invalid hash
        url_invalid = f"/api/v1/documents/public/verify/{ulpin}/invalidhash123456"
        resp_invalid = await client.get(url_invalid)

    print("=== AUDIT RESULTS FOR PUBLIC VERIFY ENDPOINT ===")
    print(f"Document ID: {doc.id}")
    print(f"Document File: {doc.filename}")
    print(f"Computed Document Full SHA-256: {actual_sha256} (Length: {len(actual_sha256)})")
    print(f"Computed ULPIN: {ulpin}")
    print(f"Default Certificate QR Hash Prefix: {hash_prefix_16} (Length: {len(hash_prefix_16)})")
    print("\n--- 1. Full SHA-256 Request ---")
    print(f"GET {url_full}")
    print(f"Status Code: {resp_full.status_code}")
    print(f"Response Body JSON:")
    print(json.dumps(resp_full.json(), indent=2))
    
    print("\n--- 2. 16-char Prefix Request ---")
    print(f"GET {url_prefix}")
    print(f"Status Code: {resp_prefix.status_code}")
    print(f"Response Body JSON:")
    print(json.dumps(resp_prefix.json(), indent=2))

    print("\n--- 3. Invalid Hash Request ---")
    print(f"GET {url_invalid}")
    print(f"Status Code: {resp_invalid.status_code}")
    print(f"Response Body JSON:")
    print(json.dumps(resp_invalid.json(), indent=2))

if __name__ == "__main__":
    asyncio.run(run_public_verify_audit())
