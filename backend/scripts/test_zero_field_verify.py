import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from sqlalchemy import select
from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.models.document import Document, DocumentStatus
from app.models.user import User, UserRole

async def main():
    async with AsyncSessionLocal() as db:
        # Find a verifier user
        result = await db.execute(select(User).where(User.role == UserRole.verifier))
        verifier = result.scalars().first()
        if not verifier:
            print("No verifier found!")
            return
        
        token = create_access_token(subject=verifier.id, extra_claims={"role": verifier.role.value, "username": verifier.username})

        # 1. Insert a test document with 0 ExtractedField rows
        test_doc = Document(
            filename="empty_ocr_record.pdf",
            storage_path="/tmp/empty_ocr_record.pdf",
            status=DocumentStatus.needs_review,
            district="Jaipur",
            tehsil="Sanganer",
            village="Zero Field Village",
        )
        db.add(test_doc)
        await db.commit()
        await db.refresh(test_doc)
        doc_id = test_doc.id
        print(f"[SETUP] Created document ID {doc_id} with status='{test_doc.status.value}' and 0 ExtractedField rows.")

    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        # Check extracted fields
        fields_res = await client.get(f"/api/v1/documents/{doc_id}", headers=headers)
        extracted_fields = fields_res.json().get("extracted_fields", [])
        print(f"[STATUS] Document {doc_id} has {len(extracted_fields)} extracted fields.")

        # Attempt to verify
        print(f"[TEST] Calling POST /api/v1/documents/{doc_id}/verify ...")
        verify_res = await client.post(f"/api/v1/documents/{doc_id}/verify", headers=headers)
        print(f"[RESULT] Status Code: {verify_res.status_code}")
        print(f"[RESULT] Response Body: {verify_res.json()}")

        # Cleanup
        async with AsyncSessionLocal() as db:
            doc_to_del = await db.get(Document, doc_id)
            if doc_to_del:
                await db.delete(doc_to_del)
                await db.commit()
                print(f"[CLEANUP] Deleted test document {doc_id}.")

if __name__ == "__main__":
    asyncio.run(main())
