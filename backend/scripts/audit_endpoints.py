import asyncio
import os
import sys
import json
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.security import create_access_token, hash_password
from app.models.user import User, UserRole
from app.models.document import Document, DocumentStatus
from app.models.extracted_field import ExtractedField
from app.models.audit_trail import AuditTrail
from app.db.session import Base, get_db
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

async def run_audit():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:', echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    async def override_get_db():
        async with async_session() as session:
            yield session
            
    app.dependency_overrides[get_db] = override_get_db
    
    async with async_session() as session:
        admin = User(id=1, username='admin_user', password_hash=hash_password('AdminPass123!'), role=UserRole.admin)
        verifier = User(id=2, username='verifier_user', password_hash=hash_password('VerifierPass123!'), role=UserRole.verifier)
        officer1 = User(id=3, username='officer_1', password_hash=hash_password('OfficerPass123!'), role=UserRole.field_officer)
        officer2 = User(id=4, username='officer_2', password_hash=hash_password('OfficerPass123!'), role=UserRole.field_officer)
        session.add_all([admin, verifier, officer1, officer2])
        await session.flush()
        
        sample_path = str(Path('demo_assets/01_clean_jaipur_khasra.pdf').resolve())
        doc1 = Document(
            id=1, filename='01_clean_jaipur_khasra.pdf', storage_path=sample_path,
            uploaded_by=officer1.id, status=DocumentStatus.verified,
            district='Jaipur', tehsil='Sanganer', village='Rampur Kalan'
        )
        session.add(doc1)
        await session.flush()
        
        ef1 = ExtractedField(document_id=doc1.id, field_name='owner_name', value='Fam Kumar Singh', confidence_score=0.85, is_flagged=False)
        ef2 = ExtractedField(document_id=doc1.id, field_name='survey_number', value='78-B', confidence_score=0.85, is_flagged=False)
        audit1 = AuditTrail(document_id=doc1.id, user_id=officer1.id, action='document_uploaded', details={'filename': doc1.filename})
        session.add_all([ef1, ef2, audit1])
        await session.commit()

    admin_token = create_access_token(1, {'role': 'admin'})
    verifier_token = create_access_token(2, {'role': 'verifier'})
    officer1_token = create_access_token(3, {'role': 'field_officer'})
    officer2_token = create_access_token(4, {'role': 'field_officer'})
    
    headers = {
        'admin': {'Authorization': f'Bearer {admin_token}'},
        'verifier': {'Authorization': f'Bearer {verifier_token}'},
        'officer1': {'Authorization': f'Bearer {officer1_token}'},
        'officer2': {'Authorization': f'Bearer {officer2_token}'},
        'none': {},
        'invalid': {'Authorization': 'Bearer bad_invalid_token_123'},
    }
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as client:
        test_cases = [
            # Auth
            {
                'name': 'POST /api/v1/auth/register',
                'method': 'POST', 'url': '/api/v1/auth/register',
                'valid_role': 'Public',
                'valid_call': lambda: client.post('/api/v1/auth/register', json={'username': 'new_user_1', 'password': 'Password123!', 'role': 'field_officer'}),
                'invalid_call': lambda: client.post('/api/v1/auth/register', json={'username': '', 'password': '123'}),
            },
            {
                'name': 'POST /api/v1/auth/login',
                'method': 'POST', 'url': '/api/v1/auth/login',
                'valid_role': 'Public',
                'valid_call': lambda: client.post('/api/v1/auth/login', data={'username': 'admin_user', 'password': 'AdminPass123!'}),
                'invalid_call': lambda: client.post('/api/v1/auth/login', data={'username': 'admin_user', 'password': 'WrongPassword'}),
            },
            {
                'name': 'GET /api/v1/auth/me',
                'method': 'GET', 'url': '/api/v1/auth/me',
                'valid_role': 'Authenticated (Any role)',
                'valid_call': lambda: client.get('/api/v1/auth/me', headers=headers['officer1']),
                'invalid_call': lambda: client.get('/api/v1/auth/me', headers=headers['invalid']),
            },
            # Dashboard
            {
                'name': 'GET /api/v1/dashboard/stats',
                'method': 'GET', 'url': '/api/v1/dashboard/stats',
                'valid_role': 'Authenticated (Role-Scoped)',
                'valid_call': lambda: client.get('/api/v1/dashboard/stats', headers=headers['officer1']),
                'invalid_call': lambda: client.get('/api/v1/dashboard/stats', headers=headers['none']),
            },
            # Documents CRUD & List
            {
                'name': 'GET /api/v1/documents',
                'method': 'GET', 'url': '/api/v1/documents',
                'valid_role': 'Authenticated (Role-Scoped)',
                'valid_call': lambda: client.get('/api/v1/documents', headers=headers['officer1']),
                'invalid_call': lambda: client.get('/api/v1/documents', headers=headers['none']),
            },
            {
                'name': 'POST /api/v1/documents/upload',
                'method': 'POST', 'url': '/api/v1/documents/upload',
                'valid_role': 'admin | verifier | field_officer',
                'valid_call': lambda: client.post('/api/v1/documents/upload', files={'file': ('test.pdf', b'%PDF-1.4 dummy', 'application/pdf')}, headers=headers['officer1']),
                'invalid_call': lambda: client.post('/api/v1/documents/upload', files={'file': ('test.pdf', b'%PDF-1.4 dummy', 'application/pdf')}, headers=headers['none']),
            },
            {
                'name': 'GET /api/v1/documents/{id}',
                'method': 'GET', 'url': '/api/v1/documents/1',
                'valid_role': 'Owner officer1 | admin | verifier',
                'valid_call': lambda: client.get('/api/v1/documents/1', headers=headers['officer1']),
                'invalid_call': lambda: client.get('/api/v1/documents/1', headers=headers['officer2']),
            },
            {
                'name': 'GET /api/v1/documents/public/verify/{ulpin}/{hash}',
                'method': 'GET', 'url': '/api/v1/documents/public/verify/RJ-JAI-1234/somehash',
                'valid_role': 'Public',
                'valid_call': lambda: client.get('/api/v1/documents/public/verify/RJ-JAI-1234/somehash'),
                'invalid_call': lambda: client.get('/api/v1/documents/public/verify/INVALID/hash'),
            },
            {
                'name': 'PATCH /api/v1/documents/{id}/fields/{field}',
                'method': 'PATCH', 'url': '/api/v1/documents/1/fields/owner_name',
                'valid_role': 'admin | verifier',
                'valid_call': lambda: client.patch('/api/v1/documents/1/fields/owner_name', json={'value': 'Updated Name'}, headers=headers['verifier']),
                'invalid_call': lambda: client.patch('/api/v1/documents/1/fields/owner_name', json={'value': 'Updated Name'}, headers=headers['officer1']),
            },
            {
                'name': 'POST /api/v1/documents/{id}/verify',
                'method': 'POST', 'url': '/api/v1/documents/1/verify',
                'valid_role': 'admin | verifier',
                'valid_call': lambda: client.post('/api/v1/documents/1/verify', json={'remarks': 'Approved'}, headers=headers['verifier']),
                'invalid_call': lambda: client.post('/api/v1/documents/1/verify', json={'remarks': 'Approved'}, headers=headers['officer1']),
            },
            {
                'name': 'POST /api/v1/documents/{id}/reprocess',
                'method': 'POST', 'url': '/api/v1/documents/1/reprocess',
                'valid_role': 'admin | verifier',
                'valid_call': lambda: client.post('/api/v1/documents/1/reprocess', headers=headers['verifier']),
                'invalid_call': lambda: client.post('/api/v1/documents/1/reprocess', headers=headers['officer1']),
            },
            {
                'name': 'GET /api/v1/documents/{id}/file',
                'method': 'GET', 'url': '/api/v1/documents/1/file',
                'valid_role': 'Owner officer1 | admin | verifier',
                'valid_call': lambda: client.get('/api/v1/documents/1/file', headers=headers['officer1']),
                'invalid_call': lambda: client.get('/api/v1/documents/1/file', headers=headers['officer2']),
            },
            {
                'name': 'GET /api/v1/documents/{id}/audit',
                'method': 'GET', 'url': '/api/v1/documents/1/audit',
                'valid_role': 'Owner officer1 | admin | verifier',
                'valid_call': lambda: client.get('/api/v1/documents/1/audit', headers=headers['officer1']),
                'invalid_call': lambda: client.get('/api/v1/documents/1/audit', headers=headers['officer2']),
            },
            {
                'name': 'GET /api/v1/documents/{id}/duplicates',
                'method': 'GET', 'url': '/api/v1/documents/1/duplicates',
                'valid_role': 'Owner officer1 | admin | verifier',
                'valid_call': lambda: client.get('/api/v1/documents/1/duplicates', headers=headers['officer1']),
                'invalid_call': lambda: client.get('/api/v1/documents/1/duplicates', headers=headers['officer2']),
            },
            {
                'name': 'GET /api/v1/documents/{id}/export/dilrmp',
                'method': 'GET', 'url': '/api/v1/documents/1/export/dilrmp',
                'valid_role': 'Owner officer1 | admin | verifier',
                'valid_call': lambda: client.get('/api/v1/documents/1/export/dilrmp', headers=headers['officer1']),
                'invalid_call': lambda: client.get('/api/v1/documents/1/export/dilrmp', headers=headers['officer2']),
            },
            {
                'name': 'GET /api/v1/documents/{id}/integrity',
                'method': 'GET', 'url': '/api/v1/documents/1/integrity',
                'valid_role': 'Owner officer1 | admin | verifier',
                'valid_call': lambda: client.get('/api/v1/documents/1/integrity', headers=headers['officer1']),
                'invalid_call': lambda: client.get('/api/v1/documents/1/integrity', headers=headers['officer2']),
            },
            {
                'name': 'GET /api/v1/documents/{id}/certificate',
                'method': 'GET', 'url': '/api/v1/documents/1/certificate',
                'valid_role': 'Owner officer1 | admin | verifier',
                'valid_call': lambda: client.get('/api/v1/documents/1/certificate', headers=headers['officer1']),
                'invalid_call': lambda: client.get('/api/v1/documents/1/certificate', headers=headers['officer2']),
            },
            # Integrations
            {
                'name': 'POST /api/v1/integrations/lrms/push/{id}',
                'method': 'POST', 'url': '/api/v1/integrations/lrms/push/1',
                'valid_role': 'admin | verifier',
                'valid_call': lambda: client.post('/api/v1/integrations/lrms/push/1', headers=headers['verifier']),
                'invalid_call': lambda: client.post('/api/v1/integrations/lrms/push/1', headers=headers['officer1']),
            },
            {
                'name': 'POST /api/v1/integrations/gis/push/{id}',
                'method': 'POST', 'url': '/api/v1/integrations/gis/push/1',
                'valid_role': 'admin | verifier',
                'valid_call': lambda: client.post('/api/v1/integrations/gis/push/1', headers=headers['verifier']),
                'invalid_call': lambda: client.post('/api/v1/integrations/gis/push/1', headers=headers['officer1']),
            },
            # Health
            {
                'name': 'GET /health',
                'method': 'GET', 'url': '/health',
                'valid_role': 'Public',
                'valid_call': lambda: client.get('/health'),
                'invalid_call': lambda: client.get('/health'),
            },
            {
                'name': 'GET /health/diagnostics',
                'method': 'GET', 'url': '/health/diagnostics',
                'valid_role': 'Public',
                'valid_call': lambda: client.get('/health/diagnostics'),
                'invalid_call': lambda: client.get('/health/diagnostics'),
            },
        ]
        
        print('\n' + '='*80)
        print(f'PHASE 1.1: CALLING ALL {len(test_cases)} ENDPOINTS (AUTHORIZED vs UNAUTHORIZED/FORBIDDEN)')
        print('='*80 + '\n')
        
        for idx, tc in enumerate(test_cases, 1):
            r_val = await tc['valid_call']()
            r_inval = await tc['invalid_call']()
            
            val_summary = r_val.text[:100].replace('\n', ' ')
            inval_summary = r_inval.text[:100].replace('\n', ' ')
            
            print(f'[{idx:02d}] {tc["method"]} {tc["url"]}')
            print(f'     Required Role  : {tc["valid_role"]}')
            print(f'     ✔ Valid Call   -> Status: {r_val.status_code} | Body: {val_summary}')
            print(f'     ✘ Invalid Call -> Status: {r_inval.status_code} | Body: {inval_summary}')
            print('-'*80)

if __name__ == '__main__':
    asyncio.run(run_audit())
