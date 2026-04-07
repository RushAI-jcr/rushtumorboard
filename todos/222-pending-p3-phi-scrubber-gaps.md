---
status: pending
priority: p3
issue_id: "222"
tags: [code-review, security, phi]
dependencies: []
---

# PHI Scrubber Pattern Gaps

## Problem Statement
The PHI scrubber (`phi_scrubber.py`) handles dates, MRN-like numbers, and labeled names, but has gaps:

1. **Unlabeled names**: "John Smith has ovarian cancer" not scrubbed (only matches "Patient: John Smith")
2. **Single-word names**: "Mrs. Rodriguez" not matched (requires 2+ capitalized words)
3. **Ages**: "72-year-old" not scrubbed
4. **Addresses, phone numbers, emails**: Not covered
5. **FHIR/Fabric `read()` ignores patient_id**: Fetches note by `note_id` only — a caller could read another patient's note

## Findings
- **File**: `src/utils/phi_scrubber.py` — 5 patterns, gaps in coverage
- **File**: `src/data_models/fhir/fhir_clinical_note_accessor.py:252-255` — `read()` ignores patient_id
- **File**: `src/data_models/fabric/fabric_clinical_note_accessor.py:153-156` — same issue
- **Known Pattern**: Prior TODO #200 addressed PHI in blob accessor logs — same category

## Proposed Solutions
1. Evaluate Microsoft Presidio for more comprehensive de-identification
2. Add patterns for ages, addresses, phone numbers
3. In FHIR/Fabric `read()`, validate note's patient reference matches expected patient_id

## Acceptance Criteria
- [ ] Evaluate Presidio feasibility
- [ ] Add age pattern to scrubber
- [ ] FHIR/Fabric `read()` validates patient ownership
