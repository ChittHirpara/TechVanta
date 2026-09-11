"""
Upload-record persistence — saves every successfully extracted document
to a separate JSON dataset without touching trusted reference data.

Purpose
───────
After the LLM extraction step succeeds, this module appends the extracted
fields to ``app/data/uploaded_land_records.json`` so that every processed
PDF leaves a persistent, auditable record independent of the SQLite database.

Safety guarantees
─────────────────
• Trusted reference data (``reference_records.json``) is NEVER read or
  written by this module.
• File writes are atomic (write-to-temp → rename) so concurrent uploads
  never corrupt the file.
• Duplicate processing of the same ``document_id`` is detected and skipped.
• Corrupted / invalid JSON in the file is handled gracefully (logged + reset).
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# File location (same ``data/`` directory as reference_records.json)
# ─────────────────────────────────────────────────────────────────────────────

_UPLOADED_FILE = (
    Path(__file__).resolve().parent.parent / "data" / "uploaded_land_records.json"
)


# ─────────────────────────────────────────────────────────────────────────────
# Read helpers
# ─────────────────────────────────────────────────────────────────────────────

def _read_records() -> list[dict[str, Any]]:
    """
    Load existing uploaded records.  Returns ``[]`` on any parse error
    (the file is logged but never silently deleted).
    """
    if not _UPLOADED_FILE.exists():
        return []
    try:
        payload = json.loads(_UPLOADED_FILE.read_text(encoding="utf-8"))
        records = payload.get("records", [])
        if not isinstance(records, list):
            log.warning("[uploaded] 'records' key is not a list – starting fresh")
            return []
        return records
    except (json.JSONDecodeError, OSError) as exc:
        log.error("[uploaded] failed to parse %s: %s — treating as empty", _UPLOADED_FILE, exc)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Atomic write helper
# ─────────────────────────────────────────────────────────────────────────────

def _write_records(records: list[dict[str, Any]]) -> None:
    """
    Atomically write the full records list to the JSON file.

    Uses a temp file in the same directory + ``os.replace`` so the write is
    visible to readers in a single rename and never leaves a half-written file.
    """
    _UPLOADED_FILE.parent.mkdir(parents=True, exist_ok=True)

    fd: int | None = None
    tmp_path: Path | None = None
    try:
        # Create temp file on the SAME filesystem so os.replace is atomic
        fd, tmp_name = tempfile.mkstemp(
            dir=str(_UPLOADED_FILE.parent),
            prefix=".uploaded_records_",
            suffix=".tmp",
        )
        tmp_path = Path(tmp_name)

        payload = {
            "description": "Extracted land records from uploaded PDFs. Separate from trusted reference data.",
            "records": records,
        }
        tmp_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        # Flush to disk before rename
        os.fsync(fd)
        os.close(fd)
        fd = None

        os.replace(str(tmp_path), str(_UPLOADED_FILE))
        tmp_path = None
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def save_uploaded_record(
    document_id: int,
    source_filename: str,
    extracted_data: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Append one extracted record to ``uploaded_land_records.json``.

    Args:
        document_id:      The primary-key ``id`` from the ``Document`` row.
        source_filename:  Original filename of the uploaded PDF.
        extracted_data:   Flat dict of extracted field values
                          (``ExtractionResult.flat_values()``).

    Returns:
        The persisted record dict, or ``None`` if the same document_id
        was already saved (deduplication).
    """
    record_id = f"UPLOAD-{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    records = _read_records()

    # Deduplication: skip if this document_id was already processed
    for existing in records:
        if existing.get("documentId") == document_id:
            log.info(
                "[uploaded] document_id=%d already saved (record=%s) – skipping",
                document_id, existing.get("id"),
            )
            return None

    new_record = {
        "id": record_id,
        "documentId": document_id,
        "uploadedAt": now_iso,
        "sourceFileName": source_filename,
        "extractedData": extracted_data,
    }

    records.append(new_record)
    _write_records(records)

    log.info(
        "[uploaded] saved record %s for document_id=%d (%d total records)",
        record_id, document_id, len(records),
    )
    return new_record
