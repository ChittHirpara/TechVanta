# Changelog

All notable changes to the **BhoomiScan AI (TechVanta)** platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased] — 2026-09-07

### Fixed
- **Bcrypt 5.x Hashing Break**: Resolved `AttributeError: module 'bcrypt' has no attribute '__about__'` on Python 3.13 by migrating to native `bcrypt.hashpw` and `bcrypt.checkpw` in `security.py`.
- **Multipart Upload Dependency**: Installed and configured `python-multipart` to support document form uploads.
- **Environment CORS Parsing**: Corrected `ALLOWED_ORIGINS` in `.env` to a valid JSON array format for Pydantic Settings v2.

### Added
- **Sovereign Verification Certificate (PDF / HTML)**: Added printable Government of India verification certificate export featuring Ashok Chakra header, 14-char ULPIN badge, tabular land attributes, officer digital sign-off, and SHA-256 seal at `GET /api/v1/documents/{id}/certificate`.
- **Public Tamper-Evident QR Verification Gateway**: Added public verification endpoint `GET /api/v1/documents/public/verify/{ulpin}/{file_hash}` for citizen and bank QR code scans without exposing sensitive personal owner data.
- **Duplicate-Conflict Comparison Modal**: Added `DuplicateCompareModal.jsx` allowing verifiers to compare conflicting deeds side-by-side with red/green attribute diff highlighting upon Fraud Shield alert.
- **Cadastral GIS Map Inspector**: Added collapsible `CadastralMapPanel.jsx` in the Verification Workspace displaying geo-referenced parcel boundary polygons, neighboring plots, and satellite hybrid views.
- **Sample Test Deeds (`demo_assets/`)**: Added 3 standardized evaluation files (`01_clean_jaipur_khasra.pdf`, `02_degraded_jodhpur_plot_deed.jpg`, `03_fraudulent_duplicate_deed.pdf`) and evaluation guide for live judge walkthroughs.

### Changed
- **Dynamic Per-Field Confidence Thresholds**: Implemented stricter threshold overrides for legal parcel numbers (`khasra_number: 0.85`, `survey_number: 0.85`, `khata_number: 0.80`, `plot_area: 0.80`) while retaining 0.75 global fallback.
- **Multi-Region & Bilingual UI Flag**: Added `enable_multilingual_ui: bool = False` configuration flag preserving single-language stability by default.

### Documentation
- **Tesseract Binary Setup**: Added operational setup instructions for Windows (`winget`), Ubuntu (`apt`), macOS (`brew`), and Docker in `backend/README.md` alongside documentation of graceful fallback guarantees.
