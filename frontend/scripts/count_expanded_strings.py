import json
import os

# Load current en.json
with open('frontend/public/locales/en.json', 'r', encoding='utf-8') as f:
    en_existing = json.load(f)

def get_leaf_keys(d, prefix=''):
    res = {}
    for k, v in d.items():
        full_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            res.update(get_leaf_keys(v, full_key))
        else:
            res[full_key] = v
    return res

existing_leaf = get_leaf_keys(en_existing)
print(f"Current existing leaf keys: {len(existing_leaf)}")

# Define all new strings discovered from the exhaustive scan
# Organized by namespace
new_strings = {
    "app": {
        "document_title": "BhoomiScan AI — Sovereign Land Record Verification Studio",
        "loading_portal": "Initializing BhoomiScan AI Portal...",
        "loading_subtext": "Verifying sovereign security credentials & endpoints",
        "dept_banner_title": "Department of Land Resources & Revenue Administration:",
        "dept_banner_desc": "Authorized departmental access required. Please sign in to access jurisdiction records, verification queues, and GIS push integrations.",
        "dept_access_title": "Official Departmental Access",
        "dept_access_desc": "Access role-governed verification queues for Field Officers (Patwaris), Verifying Officers (Tehsildars), and District Administrators.",
        "sign_in_workspace": "Sign In to Workspace",
        "new_officer_reg": "New Officer Registration",
        "architecture_title": "System Architecture & Standards",
        "ocr_title": "Multimodal OCR:",
        "ocr_desc": "EasyOCR deep learning + Tesseract cascade for Indic scripts.",
        "dilrmp_title": "DILRMP 2.0:",
        "dilrmp_desc": "Automated 14-digit ULPIN allocation & cadastral mapping.",
        "crypto_title": "Cryptographic Verification:",
        "crypto_desc": "SHA-256 tamper-evident integrity hashing.",
        "fraud_title": "Fraud Shield:",
        "fraud_desc": "Token-set approximate duplicate record detection against registry.",
        "footer_line1": "BhoomiScan AI • National Land Record Modernization & AI Verification Engine",
        "footer_line2": "Smart India Hackathon (SIH) Innovation • GIGW & DILRMP 2.0 Compliant"
    },
    "auth_modal": {
        "tab_login": "Existing Officer Sign In",
        "tab_register": "New Officer Registration",
        "label_username_login": "Official Username / Employee ID",
        "label_password": "Security Password",
        "placeholder_password": "Enter authorized password",
        "label_username_register": "Official Username *",
        "label_fullname": "Full Legal Name",
        "label_email": "Official Email Address *",
        "label_password_register": "Password (Minimum 8 Characters) *",
        "label_role": "Departmental Role & Jurisdiction *",
        "btn_cancel": "Cancel",
        "toast_welcome": "Welcome back, Officer {{name}}!",
        "toast_registered": "Officer account '{{username}}' registered successfully! Please sign in."
    },
    "dashboard_extra": {
        "loading_metrics": "Loading jurisdictional metrics...",
        "no_districts": "No district records indexed yet. Upload land records to see jurisdictional progress."
    },
    "ingestion_extra": {
        "field_district": "Revenue District",
        "field_tehsil": "Tehsil / Sub-District",
        "field_village": "Village / Mauza",
        "btn_clear": "Clear",
        "toast_ingested": "Document #{{id}} uploaded successfully. Connecting to real-time workflow...",
        "toast_pipeline_complete": "Workflow complete for Document #{{docId}}! Ready for verification.",
        "toast_pipeline_note": "Workflow note: {{message}}"
    },
    "modals_extra": {
        "audit": {
            "loading": "Loading chronological audit events...",
            "empty": "No audit logs recorded for this document yet.",
            "actor": "Actor:"
        },
        "dilrmp": {
            "schema_line1": "Standardized revenue interchange schema conforming to the",
            "schema_line2": "Digital India Land Records Modernization Technical Specifications",
            "generating": "Generating DILRMP 2.0 standard payload...",
            "btn_copy": "Copy JSON",
            "btn_download": "Download File",
            "toast_copied": "DILRMP 2.0 JSON payload copied to clipboard!",
            "toast_downloaded": "Downloaded DILRMP_Record_{{docId}}.json"
        },
        "duplicate": {
            "title": "Fraud Shield — Dual-Title & Parcel Conflict Comparison",
            "dispute_title": "Potential Revenue Act Title Dispute:",
            "dispute_desc": "Two separate documents reference overlapping parcel or ownership coordinates. Review discrepancies below before verifying.",
            "loading": "Loading conflicting document details...",
            "parcel_attribute": "Parcel Attribute",
            "mismatch_conflict": "Mismatch Conflict",
            "duplicate_overlap": "Duplicate Overlap",
            "audit_note": "Audit log records this conflict review session automatically."
        },
        "field": {
            "btn_cancel": "Cancel",
            "toast_updated": "Field '{{fieldName}}' updated successfully!"
        }
    },
    "registry_extra": {
        "btn_reset": "Reset",
        "loading": "Loading land records registry...",
        "empty": "No land records found matching the active filters.",
        "prev_page": "← Previous",
        "next_page": "Next →"
    },
    "cadastral": {
        "panel_title": "Cadastral GIS & Geolocation Boundary Inspector",
        "survey_prefix": "Survey #",
        "expand_btn": "Expand GIS Map ▼",
        "collapse_btn": "Collapse GIS Panel ▲",
        "cadastral_layer": "Cadastral Layer:",
        "parcel_declared": "DILRMP Geo-referenced Khasra Parcel #{{khasraNumber}} (Declared Area: {{plotArea}})",
        "grid_view": "Cadastral Grid",
        "satellite_view": "Satellite Hybrid",
        "datum_verified": "Survey Scale: 1:1000 • Datum: WGS-84 • DILRMP Geo-tag Verified"
    },
    "workspace_extra": {
        "back_to_registry": "← Back to Registry",
        "download_original": "Download Original",
        "jurisdiction_label": "Jurisdiction:",
        "inspect_guidance": "Inspect extracted survey numbers, owners, and stamp details before verification",
        "no_entities": "No entity fields extracted yet. Document may still be processing.",
        "gateways_title": "State Revenue Gateways (Mock Integrations)",
        "gateways_disclaimer": "*Official gateway for Land Records Modernization System & Cadastral GIS layers.",
        "viewer_title": "Scanned Deed Document Viewer",
        "tooltip_reprocess_blocked": "Field Officers cannot reprocess documents.",
        "tooltip_verify_blocked": "Only Verifying Officers and Admins may verify documents.",
        "tooltip_already_verified": "Document is already verified.",
        "tooltip_edit_blocked": "Field Officers cannot edit extracted fields.",
        "tooltip_push_blocked": "Field Officers cannot transfer integrations.",
        "toast_verified": "Document #{{docId}} verified & digitally signed!",
        "toast_verify_blocked": "Verification blocked: {{err}}",
        "toast_reprocess_triggered": "Reprocessing triggered for Document #{{docId}}.",
        "toast_reprocess_failed": "Reprocess request failed: {{err}}",
        "toast_pushed": "Transferred to {{system}}! Reference: {{reference_id}} ({{status}})",
        "toast_push_failed": "Gateway transfer failed: {{err}}"
    }
}

new_leaf = get_leaf_keys(new_strings)
print(f"New leaf keys discovered: {len(new_leaf)}")
total_expanded_keys = len(existing_leaf) + len(new_leaf)
print(f"Total expanded key count: {total_expanded_keys} (previous: {len(existing_leaf)}, gap: {len(new_leaf)})")
