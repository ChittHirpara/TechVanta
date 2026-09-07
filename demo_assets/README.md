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
