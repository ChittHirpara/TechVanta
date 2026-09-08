import asyncio
import os
import sys
import hashlib
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.security import create_access_token
from app.models.user import User, UserRole
from app.models.document import Document, DocumentStatus
from app.models.extracted_field import ExtractedField
from app.db.session import Base, get_db
from app.services.certificate_service import generate_certificate_html
from app.services.dilrmp import compute_file_sha256
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

async def run_cert_audit():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:', echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    async def override_get_db():
        async with async_session() as session:
            yield session
            
    app.dependency_overrides[get_db] = override_get_db
    
    sample_path = (Path(__file__).resolve().parent.parent.parent / "demo_assets" / "01_clean_jaipur_khasra.pdf").resolve()
    real_file_sha256 = compute_file_sha256(sample_path)
    
    async with async_session() as session:
        officer = User(id=1, username='ramesh_officer', password_hash='hash', role=UserRole.verifier)
        session.add(officer)
        await session.flush()
        
        doc = Document(
            id=1, filename='01_clean_jaipur_khasra.pdf', storage_path=str(sample_path),
            uploaded_by=officer.id, status=DocumentStatus.verified,
            district='Jaipur', tehsil='Sanganer', village='Rampur Kalan'
        )
        session.add(doc)
        await session.flush()
        
        fields = [
            ExtractedField(document_id=doc.id, field_name='owner_name', value='Fam Kumar Singh', confidence_score=0.92, is_flagged=False),
            ExtractedField(document_id=doc.id, field_name='survey_number', value='78-B', confidence_score=0.95, is_flagged=False),
            ExtractedField(document_id=doc.id, field_name='khasra_number', value='451/2', confidence_score=0.94, is_flagged=False),
            ExtractedField(document_id=doc.id, field_name='plot_area', value='2 Bigha 14 Biswa', confidence_score=0.90, is_flagged=False),
        ]
        session.add_all(fields)
        await session.commit()
        
        # 1. Direct Service Call
        cert_html = generate_certificate_html(
            document=doc,
            fields=fields,
            verifier_username='ramesh_officer (Verifier)',
        )
        
        print('======================================================================')
        print('PHASE 1.4: CERTIFICATE GENERATION AUDIT')
        print('======================================================================\n')
        print(f'HTML Length: {len(cert_html)} bytes')
        print(f'Contains <!DOCTYPE html>: {"<!DOCTYPE html>" in cert_html}')
        print(f'Contains SVG QR Matrix (<svg): {"<svg" in cert_html}')
        print(f'Contains window.print() action: {"window.print()" in cert_html}')
        
        # Check embedded SHA-256 vs computed SHA-256
        print(f'\nComputed Source File SHA-256 : {real_file_sha256}')
        print(f'Embedded in Certificate HTML : {real_file_sha256 in cert_html}')
        
        # 2. Endpoint Call: GET /documents/1/certificate
        token = create_access_token(1, {'role': 'verifier'})
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url='http://test') as client:
            resp = await client.get('/api/v1/documents/1/certificate', headers={'Authorization': f'Bearer {token}'})
            print(f'\nEndpoint GET /api/v1/documents/1/certificate:')
            print(f'  • Status Code   : {resp.status_code}')
            print(f'  • Content-Type  : {resp.headers.get("content-type")}')
            print(f'  • Is HTML Body  : {resp.text.startswith("<!DOCTYPE html>")}')
            
            # Preview QR code and Security seal section
            print('\n--- CERTIFICATE HTML SNIPPET (SECURITY & SEAL SECTION) ---')
            for line in cert_html.split('\n')[:35]:
                print(line)

if __name__ == '__main__':
    asyncio.run(run_cert_audit())
