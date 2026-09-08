#!/usr/bin/env python3
"""
Database seed script.

Creates realistic demo data so you can test the full UI/API flow immediately
without running real OCR or LLM calls.

What is created
───────────────
  Users
    alice  (admin)      password: Admin1234!
    bob    (verifier)   password: Verif5678!

  Documents
    1. Jaipur Khasra   – status=verified       (clean, all fields present)
    2. Jodhpur Deed    – status=needs_review    (2 flagged fields)
    3. Sanganer Entry  – status=processing      (pipeline still running)

  ExtractedField rows  for docs 1 and 2
  VerificationLog rows for doc 1 (showing the audit history)
  AuditTrail rows      for all key events

Usage
─────
  # Seed the Docker Postgres (reads .env)
  docker-compose exec app python scripts/seed.py

  # Seed a local SQLite DB (for quick testing without Docker)
  python scripts/seed.py --db-url sqlite+aiosqlite:///./dev.db

  # Wipe and re-seed (drops all rows before inserting)
  python scripts/seed.py --reset

  # Quiet mode (no banner, just errors)
  python scripts/seed.py --quiet
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ── Minimal env defaults for standalone execution ─────────────────────────────
os.environ.setdefault("JWT_SECRET",  "seed-script-local-secret")
os.environ.setdefault("LLM_API_KEY", "sk-seed-fake")

# ── ANSI colour helpers ───────────────────────────────────────────────────────
_TTY = sys.stdout.isatty()
def _c(code: str, t: str) -> str: return f"\033[{code}m{t}\033[0m" if _TTY else t
def bold(t):  return _c("1",  t)
def cyan(t):  return _c("96", t)
def green(t): return _c("92", t)
def yellow(t):return _c("93", t)
def red(t):   return _c("91", t)
def dim(t):   return _c("2",  t)

# ─────────────────────────────────────────────────────────────────────────────
# Seed data definitions
# ─────────────────────────────────────────────────────────────────────────────

USERS = [
    {"username": "alice",  "password": "Admin1234!", "role": "admin"},
    {"username": "bob",    "password": "Verif5678!", "role": "verifier"},
    {"username": "carol",  "password": "FieldOfficer123!", "role": "field_officer"},
]

DOCUMENTS = [
    {
        "filename": "jaipur_khasra_451.pdf",
        "storage_path": "/app/uploads/demo/jaipur_khasra_451.pdf",
        "status": "verified",
        "district": "Jaipur",
        "tehsil": "Sanganer",
        "village": "Rampur Kalan",
        "fields": {
            "owner_name":          ("Ram Kumar Singh",          0.93, False),
            "survey_number":       ("78-B",                     0.91, False),
            "khasra_number":       ("451/2",                    0.89, False),
            "khata_number":        ("112",                      0.87, False),
            "plot_area":           ("2 Bigha 14 Biswa",         0.85, False),
            "village":             ("Rampur Kalan",             0.94, False),
            "tehsil":              ("Sanganer",                 0.96, False),
            "district":            ("Jaipur",                   0.97, False),
            "land_classification": ("Agricultural – Irrigated", 0.82, False),
            "ownership_details":   ("Single owner, no mortgage",0.78, False),
            "mutation_record":     ("Entry 23, 15-Mar-2019",    0.80, False),
            "registration_info":   ("Deed 4521/2019",           0.88, False),
        },
        "verification_logs": [
            # Simulates a verifier correcting a typo before final verification
            {
                "field_name": "khasra_number",
                "old_value":  "45l/2",   # OCR misread 'l' as '1'
                "new_value":  "451/2",
            }
        ],
    },
    {
        "filename": "jodhpur_plot_deed.jpg",
        "storage_path": "/app/uploads/demo/jodhpur_plot_deed.jpg",
        "status": "needs_review",
        "district": "Jodhpur",
        "tehsil": "Phalodi",
        "village": "Bhinmal",
        "fields": {
            "owner_name":          ("Priya Sharma Devi",        0.88, False),
            "survey_number":       ("12/3A",                    0.72, False),
            "khasra_number":       ("22l/1", 0.38, True),   # OCR error
            "khata_number":        (None,                       0.20, True),   # not found
            "plot_area":           ("1.45 acres",               0.81, False),
            "village":             ("Bhinmal",                  0.90, False),
            "tehsil":              ("Phalodi",                  0.91, False),
            "district":            ("Jodhpur",                  0.95, False),
            "land_classification": ("Residential",              0.77, False),
            "ownership_details":   ("Joint ownership",          0.65, False),
            "mutation_record":     (None,                       0.15, True),   # low conf
            "registration_info":   ("Deed 1102/2021",           0.84, False),
        },
        "verification_logs": [],
    },
    {
        "filename": "sanganer_survey_records.pdf",
        "storage_path": "/app/uploads/demo/sanganer_survey_records.pdf",
        "status": "processing",
        "district": "Jaipur",
        "tehsil": "Sanganer",
        "village": "Chaksu",
        "fields": {},           # pipeline still running — no fields yet
        "verification_logs": [],
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# Seeder
# ─────────────────────────────────────────────────────────────────────────────

async def seed(db_url: str, reset: bool, quiet: bool) -> None:
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    import app.models  # noqa: register all models
    from app.db.session import Base
    from app.models.user import User, UserRole
    from app.models.document import Document, DocumentStatus
    from app.models.extracted_field import ExtractedField
    from app.models.verification_log import VerificationLog
    from app.models.audit_trail import AuditTrail
    from app.core.security import hash_password

    def log(msg: str) -> None:
        if not quiet:
            print(msg)

    log(bold("\n═" * 56))
    log(bold("  Land Record Digitizer – Database Seeder"))
    log(bold("═" * 56))
    log(f"  Target: {cyan(db_url)}")

    # ── Connect ───────────────────────────────────────────────────────────────
    extra: dict = {}
    if db_url.startswith("sqlite"):
        from sqlalchemy.pool import StaticPool
        extra = {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}

    engine = create_async_engine(db_url, echo=False, **extra)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    # ── Create tables ─────────────────────────────────────────────────────────
    async with engine.begin() as conn:
        if reset:
            log(f"\n  {yellow('⚠  Dropping all tables …')}")
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    log(f"  {green('✔')} Schema ready")

    async with SessionLocal() as db:

        # ── Users ─────────────────────────────────────────────────────────────
        log(f"\n  {bold('Creating users …')}")
        user_objs: dict[str, User] = {}
        for u in USERS:
            user = User(
                username=u["username"],
                password_hash=hash_password(u["password"]),
                role=UserRole(u["role"]),
            )
            db.add(user)
            await db.flush()
            user_objs[u["username"]] = user
            log(f"    {green('+')} {u['username']:<12} role={u['role']:<14} "
                f"pw={dim(u['password'])}")

        verifier = user_objs.get("bob") or list(user_objs.values())[-1]
        admin    = user_objs.get("alice") or list(user_objs.values())[0]

        # ── Documents + fields ────────────────────────────────────────────────
        log(f"\n  {bold('Creating documents …')}")
        demo_dir = PROJECT_ROOT / "uploads" / "demo"
        demo_dir.mkdir(parents=True, exist_ok=True)

        for i, d in enumerate(DOCUMENTS, start=1):
            demo_file = demo_dir / d["filename"]
            if not demo_file.exists():
                demo_file.write_text(f"%PDF-1.4 Mock demo land deed content for {d['filename']}", encoding="utf-8")
            actual_storage_path = str(demo_file.resolve())

            doc = Document(
                filename=d["filename"],
                storage_path=actual_storage_path,
                uploaded_by=admin.id,
                status=DocumentStatus(d["status"]),
                district=d.get("district"),
                tehsil=d.get("tehsil"),
                village=d.get("village"),
            )
            db.add(doc)
            await db.flush()

            status_col = {
                "verified":     green("verified"),
                "needs_review": yellow("needs_review"),
                "processing":   cyan("processing"),
            }.get(d["status"], d["status"])

            fn = d["filename"]
            log(f"\n  {bold(f'  Doc {i}: {fn}')}  [{status_col}]")

            # Extracted fields
            fields_dict: dict = d.get("fields", {})
            for fname, fdata in fields_dict.items():
                # Handle tuple: (value, confidence, is_flagged)
                if isinstance(fdata, tuple):
                    value, confidence, is_flagged = fdata
                else:
                    value, confidence, is_flagged = fdata, 0.5, False

                ef = ExtractedField(
                    document_id=doc.id,
                    field_name=fname,
                    value=value,
                    confidence_score=confidence,
                    is_flagged=is_flagged,
                )
                db.add(ef)

                flag_marker = f" {red('⚑ FLAGGED')}" if is_flagged else ""
                log(f"      {cyan(fname):<26} = "
                    f"{str(value)[:30]:<32} "
                    f"conf={confidence:.2f}{flag_marker}")

            # Verification logs
            for vl_data in d.get("verification_logs", []):
                vl = VerificationLog(
                    document_id=doc.id,
                    verifier_id=verifier.id,
                    field_name=vl_data["field_name"],
                    old_value=vl_data["old_value"],
                    new_value=vl_data["new_value"],
                )
                db.add(vl)

            # Audit trail entries
            db.add(AuditTrail(
                document_id=doc.id,
                user_id=admin.id,
                action="document_uploaded",
                details={"filename": d["filename"], "seeded": True},
            ))
            if d["status"] in ("verified", "needs_review"):
                db.add(AuditTrail(
                    document_id=doc.id,
                    user_id=admin.id,
                    action="pipeline_complete",
                    details={
                        "final_status": d["status"],
                        "seeded": True,
                        "fields_saved": len(fields_dict),
                    },
                ))
            if d["status"] == "verified":
                db.add(AuditTrail(
                    document_id=doc.id,
                    user_id=verifier.id,
                    action="document_verified",
                    details={"verified_by": verifier.username, "seeded": True},
                ))

        await db.commit()

    # ── Summary ───────────────────────────────────────────────────────────────
    log(f"\n  {bold('═' * 54)}")
    log(f"  {green('✔')} Seed complete!")
    log(f"\n  {bold('Login credentials:')}")
    for u in USERS:
        log(f"    {cyan(u['username']):<14} password={dim(u['password'])}  role={u['role']}")
    log(f"\n  {bold('Quick start:')}")
    log(f"    {dim('# Get a token')}")
    log(f"    TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \\")
    log(f"      -H 'Content-Type: application/json' \\")
    log(f"      -d '{{\"username\":\"alice\",\"password\":\"Admin1234!\"}}' | jq -r .access_token)")
    log(f"    {dim('# View dashboard')}")
    log(f"    curl -s http://localhost:8000/dashboard/stats -H \"Authorization: Bearer $TOKEN\" | jq")
    log(f"    {dim('# List documents pending review')}")
    log(f"    curl -s 'http://localhost:8000/documents?status=needs_review' \\")
    log(f"      -H \"Authorization: Bearer $TOKEN\" | jq .items[].filename")
    log(bold(f"\n  {'═' * 54}\n"))

    await engine.dispose()


# ─────────────────────────────────────────────────────────────────────────────
# Entry-point
# ─────────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Seed the database with demo users and documents.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--db-url",
        metavar="URL",
        default="",
        help=(
            "Database URL (default: reads DB_URL from .env). "
            "Use 'sqlite+aiosqlite:///./dev.db' for local SQLite."
        ),
    )
    p.add_argument(
        "--reset",
        action="store_true",
        help="Drop all tables before seeding (WARNING: destroys existing data).",
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress banner and progress output.",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    # Resolve DB URL: CLI arg > env var
    db_url = args.db_url
    if not db_url:
        from dotenv import load_dotenv
        load_dotenv(PROJECT_ROOT / ".env", override=False)
        db_url = os.environ.get("DB_URL", "sqlite+aiosqlite:///./land_records.db")

    if not db_url:
        print(red("Error: No database URL. Set DB_URL in .env or pass --db-url."))
        sys.exit(1)

    asyncio.run(seed(db_url, reset=args.reset, quiet=args.quiet))
