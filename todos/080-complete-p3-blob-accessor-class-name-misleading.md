---
status: pending
priority: p3
issue_id: "080"
tags: [code-review, naming, architecture, blob-accessor]
dependencies: []
---

## Problem Statement

`ClinicalNoteAccessor` (in `src/data_models/clinical_note_accessor.py`) is the Azure Blob Storage backend. Its name implies it is a base class or generic accessor, but it is a concrete peer backend alongside `FhirClinicalNoteAccessor` and `FabricClinicalNoteAccessor`. The name is misleading for developers new to the codebase who may not recognize it as the Blob backend in `data_access.py`.

A better name: `BlobClinicalNoteAccessor` — parallel to `FhirClinicalNoteAccessor` and `FabricClinicalNoteAccessor`.

## Findings

- **File:** `src/data_models/clinical_note_accessor.py`
- **Reported by:** architecture-strategist
- **Severity:** P3 — naming clarity; no functional impact

## Proposed Solutions

Rename class from `ClinicalNoteAccessor` to `BlobClinicalNoteAccessor` and update all usages.

Affected files:
- `src/data_models/clinical_note_accessor.py` (class definition)
- `src/data_models/data_access.py` (factory import and instantiation)
- Any tests that import `ClinicalNoteAccessor`

## Acceptance Criteria

- [ ] Class renamed to `BlobClinicalNoteAccessor`
- [ ] All imports and usages updated
- [ ] `data_access.py` factory reflects the new name

## Work Log

- 2026-04-02: Identified during architecture review.
