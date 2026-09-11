"""
Demo seeder service for Smart India Hackathon (SIH) 2026.

Provides an idempotent reset & seed routine creating 5 curated benchmark land records:
  1. Jaipur Khasra 451/2       – [Verified] Clean scan, high confidence (>90%), DILRMP/ULPIN ready.
  2. Jodhpur Plot Deed        – [Needs Review] Degraded/historic scan, low-confidence flagged fields.
  3. Jaipur Fraud Duplicate   – [Needs Review] Fraud Shield detection! 96% duplicate of Doc #1.
  4. Varanasi Khatauni Hindi  – [Verified] Authentic Hindi Devanagari multilingual sovereign record.
  5. Sanganer Survey Records  – [Processing] Live in-flight queue demonstration.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.audit_trail import AuditTrail
from app.models.document import Document, DocumentStatus
from app.models.extracted_field import ExtractedField
from app.models.user import User, UserRole
from app.models.verification_log import VerificationLog

logger = logging.getLogger("app.services.demo_seeder")

DEMO_USERS = [
    {"username": "alice", "password": "Admin1234!", "role": UserRole.admin},
    {"username": "bob", "password": "Verif5678!", "role": UserRole.verifier},
    {"username": "carol", "password": "FieldOfficer123!", "role": UserRole.field_officer},
]

DEMO_DOCUMENTS: list[dict[str, Any]] = [
    {
        "filename": "jaipur_khasra_451.pdf",
        "scenario_title": "Benchmark Clean Record (DILRMP & ULPIN Compliant)",
        "status": DocumentStatus.verified,
        "district": "Jaipur",
        "tehsil": "Sanganer",
        "village": "Rampur Kalan",
        "fields": {
            "owner_name": ("Ram Kumar Singh", 0.94, False),
            "survey_number": ("78-B", 0.92, False),
            "khasra_number": ("451/2", 0.90, False),
            "khata_number": ("112", 0.88, False),
            "plot_area": ("2 Bigha 14 Biswa", 0.87, False),
            "village": ("Rampur Kalan", 0.95, False),
            "tehsil": ("Sanganer", 0.96, False),
            "district": ("Jaipur", 0.98, False),
            "land_classification": ("Agricultural – Irrigated", 0.85, False),
            "ownership_details": ("Single owner, no mortgage", 0.82, False),
            "mutation_record": ("Entry 23, 15-Mar-2019", 0.84, False),
            "registration_info": ("Deed 4521/2019", 0.91, False),
        },
        "verification_logs": [
            {
                "field_name": "khasra_number",
                "old_value": "45l/2",  # Simulated OCR correction
                "new_value": "451/2",
            }
        ],
        "audit_logs": [
            ("document_uploaded", {"source": "demo_seed", "scan_quality": "300_DPI_Color"}),
            ("pipeline_complete", {"ocr_confidence": 0.92, "model": "xai-grok-vision"}),
            ("document_verified", {"notes": "Approved and sealed under DILRMP guidelines"}),
        ],
    },
    {
        "filename": "jodhpur_plot_deed.jpg",
        "scenario_title": "Degraded Scan with Low-Confidence Flagged Fields",
        "status": DocumentStatus.needs_review,
        "district": "Jodhpur",
        "tehsil": "Phalodi",
        "village": "Bhinmal",
        "fields": {
            "owner_name": ("Priya Sharma Devi", 0.88, False),
            "survey_number": ("12/3A", 0.72, False),
            "khasra_number": ("22l/1", 0.38, True),  # Flagged: ambiguous OCR character
            "khata_number": (None, 0.20, True),  # Flagged: missing from faded deed margin
            "plot_area": ("1.45 acres", 0.81, False),
            "village": ("Bhinmal", 0.90, False),
            "tehsil": ("Phalodi", 0.91, False),
            "district": ("Jodhpur", 0.95, False),
            "land_classification": ("Residential", 0.77, False),
            "ownership_details": ("Joint ownership", 0.65, False),
            "mutation_record": (None, 0.15, True),  # Flagged: smudged seal
            "registration_info": ("Deed 1102/2021", 0.84, False),
        },
        "verification_logs": [],
        "audit_logs": [
            ("document_uploaded", {"source": "demo_seed", "scan_quality": "Degraded_Historic_Scan"}),
            ("pipeline_flagged", {"reason": "3 fields below confidence threshold 0.70"}),
        ],
    },
    {
        "filename": "jaipur_fraud_khasra_451.pdf",
        "scenario_title": "Fraud Shield: 96% Duplicate Parcel Allotment Attempt",
        "status": DocumentStatus.needs_review,
        "district": "Jaipur",
        "tehsil": "Sanganer",
        "village": "Rampur Kalan",
        "fields": {
            "owner_name": ("Ram Kumar Singh", 0.93, False),  # Exact match to Doc #1
            "survey_number": ("78-B", 0.92, False),  # Exact match to Doc #1
            "khasra_number": ("451/2", 0.90, False),
            "khata_number": ("112", 0.86, False),
            "plot_area": ("2 Bigha 14 Biswa", 0.85, False),
            "village": ("Rampur Kalan", 0.94, False),
            "tehsil": ("Sanganer", 0.96, False),
            "district": ("Jaipur", 0.97, False),
            "land_classification": ("Agricultural – Irrigated", 0.83, False),
            "ownership_details": ("Claimed Transfer Deed", 0.72, False),
            "mutation_record": ("Entry 99, Pending", 0.50, True),
            "registration_info": ("Forged Registry Ref 9912/2026", 0.60, True),
        },
        "verification_logs": [],
        "audit_logs": [
            ("document_uploaded", {"source": "demo_seed", "scan_quality": "Suspect_Submission"}),
            ("duplicate_alert", {
                "similarity_score": 96.0,
                "conflicting_doc_filename": "jaipur_khasra_451.pdf",
                "fraud_shield_triggered": True,
            }),
        ],
    },
    {
        "filename": "varanasi_khasra_hindi.pdf",
        "scenario_title": "Multilingual Sovereign Record (Devanagari Hindi)",
        "status": DocumentStatus.verified,
        "district": "वाराणसी",
        "tehsil": "पिंडरा",
        "village": "शिवपुर",
        "fields": {
            "owner_name": ("रामेश्वर प्रसाद शर्मा", 0.96, False),
            "survey_number": ("104-अ", 0.93, False),
            "khasra_number": ("312/1", 0.95, False),
            "khata_number": ("88", 0.92, False),
            "plot_area": ("1.2500 हेक्टेयर (3.08 एकड़)", 0.91, False),
            "village": ("शिवपुर", 0.97, False),
            "tehsil": ("पिंडरा", 0.96, False),
            "district": ("वाराणसी", 0.98, False),
            "land_classification": ("कृषि भूमि (दोफसली सिंचित)", 0.94, False),
            "ownership_details": ("एकल खातेदार - संक्रमणीय भूमिधर", 0.90, False),
            "mutation_record": ("दाखिल खारिज आदेश सं. 142/2022", 0.89, False),
            "registration_info": ("विलेख संख्या 5892/2022, उप निबंधक कार्यालय", 0.93, False),
        },
        "verification_logs": [],
        "audit_logs": [
            ("document_uploaded", {"source": "demo_seed", "script": "Devanagari", "language": "Hindi"}),
            ("pipeline_complete", {"multilingual_ocr": "Devanagari_Pass", "confidence": 0.94}),
            ("document_verified", {"verified_by": "alice", "registry": "UP_Bhulekh_Integrated"}),
        ],
    },
    {
        "filename": "sanganer_survey_records.pdf",
        "scenario_title": "In-Flight Pipeline Stream (SSE Telemetry Demonstration)",
        "status": DocumentStatus.processing,
        "district": "Jaipur",
        "tehsil": "Sanganer",
        "village": "Chaksu",
        "fields": {},  # No fields yet — simulates currently processing pipeline
        "verification_logs": [],
        "audit_logs": [
            ("document_uploaded", {"source": "demo_seed", "scan_quality": "MultiPage_PDF"}),
            ("pipeline_started", {"current_step": "ocr_in_progress", "progress_pct": 35}),
        ],
    },
]


async def reset_and_seed_database(db: AsyncSession) -> dict[str, Any]:
    """
    Wipes the current database and re-seeds it with 5 showcase demo documents.
    Safe to execute at any time during a live presentation.
    """
    # 1. Clean out existing records in reverse dependency order
    await db.execute(delete(VerificationLog))
    await db.execute(delete(AuditTrail))
    await db.execute(delete(ExtractedField))
    await db.execute(delete(Document))
    await db.execute(delete(User))
    await db.commit()

    # 2. Seed Users
    created_users: dict[str, User] = {}
    for u in DEMO_USERS:
        user = User(
            username=u["username"],
            password_hash=hash_password(u["password"]),
            role=u["role"],
        )
        db.add(user)
        await db.flush()
        created_users[u["username"]] = user

    admin_user = created_users["alice"]
    verifier_user = created_users["bob"]

    # 3. Ensure demo storage directory and seed documents
    base_demo_dir = Path(__file__).resolve().parent.parent.parent / "uploads" / "demo"
    base_demo_dir.mkdir(parents=True, exist_ok=True)

    seeded_docs_summary = []

    for item in DEMO_DOCUMENTS:
        filename = item["filename"]
        target_path = base_demo_dir / filename
        if not target_path.exists():
            target_path.write_bytes(f"%PDF-1.4 Mock demo content for {filename}".encode("utf-8"))

        doc = Document(
            filename=filename,
            storage_path=str(target_path.resolve()),
            uploaded_by=admin_user.id,
            status=item["status"],
            district=item["district"],
            tehsil=item["tehsil"],
            village=item["village"],
        )
        db.add(doc)
        await db.flush()

        # Seed Extracted Fields
        fields_dict: dict = item.get("fields", {})
        for field_name, (val, conf, is_flagged) in fields_dict.items():
            ef = ExtractedField(
                document_id=doc.id,
                field_name=field_name,
                value=val,
                confidence_score=conf,
                is_flagged=is_flagged,
            )
            db.add(ef)

        # Seed Verification Logs
        for vl in item.get("verification_logs", []):
            db.add(
                VerificationLog(
                    document_id=doc.id,
                    verifier_id=verifier_user.id,
                    field_name=vl["field_name"],
                    old_value=vl["old_value"],
                    new_value=vl["new_value"],
                )
            )

        # Seed Audit Trail
        for action, details in item.get("audit_logs", []):
            db.add(
                AuditTrail(
                    document_id=doc.id,
                    user_id=admin_user.id,
                    action=action,
                    details=details,
                )
            )

        seeded_docs_summary.append({
            "id": doc.id,
            "filename": doc.filename,
            "scenario": item["scenario_title"],
            "status": doc.status.value,
            "district": doc.district,
            "fields_count": len(fields_dict),
        })

    await db.commit()

    return {
        "status": "success",
        "message": "BhoomiScan AI sovereign demo state successfully initialized.",
        "documents_count": len(seeded_docs_summary),
        "users": [{"username": u["username"], "role": u["role"].value} for u in DEMO_USERS],
        "showcase_scenarios": seeded_docs_summary,
    }
