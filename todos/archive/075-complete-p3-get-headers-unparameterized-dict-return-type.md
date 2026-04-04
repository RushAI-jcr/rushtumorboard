---
status: complete
priority: p3
issue_id: "075"
tags: [code-review, typing, python, annotations]
dependencies: []
---

## Problem Statement

Both `FhirClinicalNoteAccessor.get_headers()` and `FabricClinicalNoteAccessor.get_headers()` return `dict` (unparameterized) instead of `dict[str, str]`:

```python
async def get_headers(self) -> dict:  # should be dict[str, str]
```

The actual return value is always `{"Authorization": "Bearer ...", "Content-Type": "application/json"}` — both keys and values are strings. Unparameterized `dict` loses type information and makes callers less clear about expected key/value types.

## Findings

- **File:** `src/data_models/fhir/fhir_clinical_note_accessor.py`, line 66
- **File:** `src/data_models/fabric/fabric_clinical_note_accessor.py`, line 73
- **Reported by:** kieran-python-reviewer
- **Severity:** P3 — missing type annotation precision

## Proposed Solutions

Change `-> dict` to `-> dict[str, str]` in both files.

## Acceptance Criteria

- [ ] `get_headers()` return type is `dict[str, str]` in both FHIR and Fabric accessors

## Work Log

- 2026-04-02: Identified during code review.
