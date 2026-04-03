---
status: pending
priority: p2
issue_id: "126"
tags: [code-review, simplicity, architecture]
dependencies: []
---

# 126 — Identical stub methods copy-pasted across three accessor classes (~56 LOC)

## Problem Statement

`BlobClinicalNoteAccessor`, `FabricClinicalNoteAccessor`, and `FhirClinicalNoteAccessor` each contain 7-8 identical stub methods returning `[]` with identical one-line docstrings: `get_cancer_staging`, `get_medications`, `get_diagnoses`, `get_lab_results`, `get_tumor_markers`, `get_pathology_reports`, and `get_radiology_reports`. That is approximately 56 lines of copy-pasted stubs across three files. If the interface signature changes — parameter names, return type, or docstring — all three files must be updated in lockstep, creating a maintenance hazard in a PHI-handling codebase. This also overlaps with issue 121 (capability signaling) and amplifies that problem.

## Findings

- `clinical_note_accessor.py:110-149` — stub method block in Blob accessor
- `fabric_clinical_note_accessor.py:202-232` — identical stubs in Fabric accessor
- `fhir_clinical_note_accessor.py:260-290` — identical stubs in FHIR accessor

## Proposed Solution

Define a `ClinicalNoteAccessorStubMixin` class (in `clinical_note_accessor.py` or a new `_accessor_mixin.py`) that provides the default stub implementations once:

```python
class ClinicalNoteAccessorStubMixin:
    async def get_lab_results(self, ...) -> list[...]: return []
    async def get_tumor_markers(self, ...) -> list[...]: return []
    # ... remaining stubs
```

Each of the three accessor classes inherits `ClinicalNoteAccessorStubMixin` and overrides only the methods it actually supports with real data. This removes ~40 LOC of duplication, satisfies the duck-type protocol, and gives a single place to update if the interface changes.

## Acceptance Criteria

- [ ] Stub method implementations exist in exactly one place (the mixin)
- [ ] `BlobClinicalNoteAccessor`, `FabricClinicalNoteAccessor`, and `FhirClinicalNoteAccessor` each inherit the mixin rather than re-implementing stubs
- [ ] All three accessors continue to satisfy the `ClinicalNoteAccessor` duck-type protocol
- [ ] Net reduction of at least 35 LOC across the three accessor files
