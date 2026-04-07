---
status: pending
priority: p1
issue_id: "205"
tags: [code-review, architecture, fabric, data-access]
dependencies: []
---

# Stub Mixin Silently Returns Empty Data in Fabric Mode

## Problem Statement
When `CLINICAL_NOTES_SOURCE=fabric`, `FabricClinicalNoteAccessor` inherits `ClinicalNoteAccessorStubMixin` and returns empty lists for all 9 structured data methods (`get_pathology_reports`, `get_radiology_reports`, `get_lab_results`, `get_tumor_markers`, `get_cancer_staging`, `get_medications`, `get_diagnoses`, `get_patient_demographics`). These stubs return `[]` or `None` with **no logging**. The `supported_methods()` classmethod exists but is **never called** (dead code).

**Clinical impact**: Pre-tumor board checklist shows all "MISSING". Tumor marker trending returns no data. Pathology/radiology extractors skip Layer 1 entirely.

## Findings
- **File**: `src/data_models/accessor_stub_mixin.py`, lines 45-82 — stubs return `[]` silently
- **File**: `src/data_models/fabric/fabric_clinical_note_accessor.py`, line 22 — inherits all stubs
- `supported_methods()` (lines 33-43) is never called anywhere in codebase
- `MedicalReportExtractorBase._extract()` Layer 1 silently gets `[]`, falls to Layer 2/3
- `PreTumorBoardChecklist` gets `[]` for all structured data — every item shows "MISSING"

## Proposed Solutions

### Solution A: Add WARNING logging to stub methods + startup capability reporting (Recommended)
1. Add `logger.warning("get_pathology_reports stub: returning empty for patient %s", patient_id)` to each stub method
2. In `create_data_access()`, log `accessor.supported_methods()` at INFO so operators see which methods are real vs stubbed
3. Add `data_source_capabilities` field to `DataAccess` for runtime inspection

- **Pros**: Immediate visibility, prevents silent failures
- **Cons**: Verbose logs until Fabric UDFs are implemented
- **Effort**: Small (30 minutes)
- **Risk**: None

### Solution B: Implement Fabric UDFs (addresses root cause)
Create Fabric User Data Functions for all 7 structured data types and override the stub methods. This was discussed in the prior conversation turn.

- **Pros**: Full data availability in production
- **Cons**: Requires Fabric-side work
- **Effort**: Large (days)
- **Risk**: Low

## Acceptance Criteria
- [ ] Every stub method logs a WARNING with method name and patient_id
- [ ] Startup logs which accessor methods are real vs stubbed
- [ ] `supported_methods()` is actually called (or removed if logging replaces its purpose)

## Work Log
| Date | Action | Learnings |
|------|--------|-----------|
| 2026-04-06 | Created from architecture review | Most visible production gap |
