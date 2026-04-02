---
status: complete
priority: p1
issue_id: "017"
tags: [code-review, architecture, type-safety, protocol, fhir, fabric]
dependencies: []
---

## Problem Statement

`get_clinical_notes_by_type()` and `get_clinical_notes_by_keywords()` were added to `CaboodleFileAccessor` in Phase 2, but were NOT added to `ClinicalNoteAccessorProtocol` (or whatever the shared protocol/base class is). All callers use `hasattr()` duck-typing as a guard:

```python
if hasattr(accessor, "get_clinical_notes_by_type"):
    notes = await accessor.get_clinical_notes_by_type(...)
else:
    # falls back to read_all + manual filter
```

This means:
- FHIR, Fabric, and Blob accessors **silently degrade** to the slower, less accurate `read_all` fallback — no warning, no error, no indication to the operator
- The type checker cannot catch calls to the new methods on a typed accessor reference
- New accessors written by other developers will not know these methods should exist

## Findings

- **Files:** `src/data_models/clinical_note_accessor_protocol.py`, `src/scenarios/default/tools/medical_report_extractor.py:70,80`, `src/scenarios/default/tools/oncologic_history_extractor.py:136`
- **Reported by:** architecture-strategist (P1), kieran-python-reviewer (P1)
- **Severity:** P1 — silent fallback degrades agent quality on non-Caboodle backends with no indication

## Proposed Solutions

### Option A (Recommended): Add methods to protocol, implement stubs on other accessors
```python
# In clinical_note_accessor_protocol.py
class ClinicalNoteAccessorProtocol(Protocol):
    async def get_patients(self) -> list[str]: ...
    async def get_metadata_list(self, patient_id: str) -> list[dict[str, str]]: ...
    async def read(self, patient_id: str, note_id: str) -> str: ...
    async def read_all(self, patient_id: str) -> list[str]: ...
    # New methods:
    async def get_clinical_notes_by_type(self, patient_id: str, note_types: Sequence[str]) -> list[dict]: ...
    async def get_clinical_notes_by_keywords(self, patient_id: str, note_types: Sequence[str], keywords: Sequence[str]) -> list[dict]: ...
```
Add default implementations to FHIR/Fabric/Blob accessors (can delegate to `read_all` + filter — same as current fallback, but explicit).
- **Pros:** Eliminates hasattr; type-safe; new accessors get compile-time enforcement; fallback is still available but explicit
- **Effort:** Medium (need to update 3+ other accessor classes)
- **Risk:** Low

### Option B: Abstract base class with default fallback implementations
Replace Protocol with ABC, provide default `get_clinical_notes_by_type` that calls `read_all` + filters. Subclasses override for efficiency.
- **Pros:** DRY — fallback logic in one place
- **Cons:** Requires changing inheritance on all accessors; more invasive
- **Effort:** Medium–Large

## Recommended Action

Option A. The protocol extension is the minimal correct fix; default implementations on non-Caboodle accessors delegate to `read_all` + filter (same as current hasattr fallback, just explicit).

## Technical Details

- **Affected files:** `src/data_models/clinical_note_accessor_protocol.py`, `src/data_models/epic/caboodle_file_accessor.py`, any FHIR/Fabric/Blob accessor classes
- **Pattern to eliminate:** `if hasattr(accessor, "get_clinical_notes_by_type"):` in extractor tools

## Acceptance Criteria

- [ ] `ClinicalNoteAccessorProtocol` declares `get_clinical_notes_by_type` and `get_clinical_notes_by_keywords`
- [ ] All concrete accessor classes implement these methods (even if just as `read_all` + filter fallback)
- [ ] All `hasattr()` guards in extractor tools removed
- [ ] Pyright reports no type errors on accessor method calls

## Work Log

- 2026-04-02: Identified by architecture-strategist and kieran-python-reviewer during code review
- 2026-04-02: Resolved — Protocol extended (todo 015); FabricClinicalNoteAccessor and FhirClinicalNoteAccessor now implement all 5 remaining Caboodle-only stubs.
