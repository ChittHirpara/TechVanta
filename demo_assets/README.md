# 🏛️ BhoomiScan AI — Sample Demo Assets & Evaluation Test Scenarios

These 3 benchmark test files are provided for live evaluation and judge walkthroughs:

---

### 1. `01_clean_jaipur_khasra.pdf`
- **Scenario**: Standard, high-quality Record of Rights (RoR / Jamabandi).
- **Expected Pipeline Behavior**:
  - Full automated entity extraction with high confidence (>90%).
  - Zero flagged fields.
  - Automatically transitions to ready for verification.

---

### 2. `02_degraded_jodhpur_plot_deed.jpg`
- **Scenario**: Historic, yellowed/noisy deed with smudged stamps and OCR ambiguity on Khasra Number (`22l/1` vs `221/1`).
- **Expected Pipeline Behavior**:
  - Graceful degradation: partial high-confidence fields extracted.
  - Low confidence fields flagged in amber/red (`is_flagged = true`).
  - Document marked as `needs_review` to demonstrate the **Human-in-the-Loop Verifier Workspace**.

---

### 3. `03_fraudulent_duplicate_deed.pdf`
- **Scenario**: Unauthorized attempt to register an already-allotted parcel (matching Survey `#78-B`, Khasra `#451/2` in Rampur Kalan, Jaipur).
- **Expected Pipeline Behavior**:
  - **Fraud Shield** duplicate detection triggers immediately with >85% rapidfuzz similarity match.
  - Alert banner surfaces the conflicting record ID and prevents dual-allotment.

---

### 4. `04_hindi_khasra_khatauni_varanasi.pdf`
- **Scenario**: Authentic Devanagari Hindi Record of Rights (उ.प्र. राजस्व परिषद — खतौनी / अधिकार अभिलेख) from Varanasi.
- **Expected Pipeline Behavior**:
  - Validates multilingual OCR and Devanagari LLM extraction.
  - Correctly extracts Hindi values: owner (`रामेश्वर प्रसाद शर्मा`), area (`1.2500 हेक्टेयर`), classification (`कृषि भूमि - दोफसली सिंचित`), district (`वाराणसी`), tehsil (`पिंडरा`), village (`शिवपुर`).
  - Demonstrates DILRMP 2.0 sovereign multilingual compliance.

---

### 5. `sanganer_survey_records.pdf`
- **Scenario**: Multi-page registry batch upload for testing real-time Server-Sent Events (SSE) telemetry.
- **Expected Pipeline Behavior**:
  - Live progress feedback (`ocr_started` -> `ocr_completed` -> `extraction_started` -> `validation_started` -> `completed`).
  - Non-blocking async background worker execution.
