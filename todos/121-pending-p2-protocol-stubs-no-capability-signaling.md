---
status: pending
priority: p2
issue_id: "121"
tags: [code-review, architecture, reliability]
dependencies: []
---

# 121 — Accessor stub methods return `[]` silently — clinician sees "MISSING" with no backend caveat

## Problem Statement

`FhirClinicalNoteAccessor`, `FabricClinicalNoteAccessor`, and `BlobClinicalNoteAccessor` all implement `get_lab_results`, `get_tumor_markers`, `get_pathology_reports`, `get_radiology_reports`, `get_cancer_staging`, `get_medications`, and `get_diagnoses` as stubs returning `[]`. When `get_pretumor_board_checklist` runs against a FHIR or Fabric backend, it calls these methods, receives `[]`, and reports every item as "MISSING" — with no indication to the clinician that the backend simply does not support structured queries for that data type. There are no capability flags, no warning logs, and no differentiation in checklist output between "genuinely absent from the chart" and "backend cannot retrieve this".

## Findings

- `clinical_note_accessor.py:110-149` — stub method definitions (Blob accessor)
- `fabric_clinical_note_accessor.py:202-232` — identical stubs in Fabric accessor
- `fhir_clinical_note_accessor.py:260-290` — identical stubs in FHIR accessor

## Proposed Solution

1. Add a `supported_methods() -> frozenset[str]` classmethod (or property) to each accessor that returns the set of method names the backend actually implements with real data. Stubs are omitted from this set.
2. Modify the checklist runner and `MedicalReportExtractorBase` to check capabilities before calling each method:

```python
if method_name not in accessor.supported_methods():
    checklist_item.status = "NOT_AVAILABLE_FOR_BACKEND"
    checklist_item.note = f"Structured {method_name} not available for {type(accessor).__name__} — verify manually."
```

3. Emit a single WARNING log when the checklist is run against a non-Caboodle backend listing which methods are unavailable.

## Acceptance Criteria

- [ ] Each accessor class declares its actually-supported methods via `supported_methods()`
- [ ] Checklist output clearly distinguishes "not available for this backend" from "genuinely missing from chart"
- [ ] Clinician sees an explicit caveat when the checklist runs on a FHIR or Fabric backend
- [ ] No change to Caboodle accessor behavior (all methods remain supported)
