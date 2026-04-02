---
name: ClinicalNoteAccessorProtocol missing extended GYN methods
description: Protocol only declares 4 base methods; extended GYN methods accessed via hasattr() string literals, causing silent degradation for FHIR/Fabric accessors
type: bug
status: complete
priority: p2
issue_id: "015"
tags: [architecture, type-safety, code-review]
---

## Problem Statement

`ClinicalNoteAccessorProtocol` (added in this refactor cycle) declares only the 4 base methods: `get_patients`, `get_metadata_list`, `read`, `read_all`. The extended GYN methods (`get_clinical_notes_by_type`, `get_clinical_notes_by_keywords`, `get_pathology_reports`, `get_radiology_reports`, etc.) are gated everywhere via `hasattr()` string literal checks.

**Why it matters:**
1. Mypy/Pyright cannot type-check the extended surface — errors in method names go undetected until runtime
2. `FhirClinicalNoteAccessor` and `FabricClinicalNoteAccessor` silently fall back to `read_all()` (sends ALL note types to LLM) instead of the filtered subset — increasing unnecessary PHI exposure in the prompt and token costs
3. A future accessor that implements the Protocol but omits a GYN method silently degrades without any warning

**Affected files:**
- `src/data_models/clinical_note_accessor_protocol.py` — only 4 methods declared
- `src/scenarios/default/tools/medical_report_extractor.py` — uses `hasattr(accessor, "get_clinical_notes_by_keywords")`
- `src/scenarios/default/tools/oncologic_history_extractor.py` — uses `hasattr(accessor, "get_clinical_notes_by_type")`
- `src/scenarios/default/tools/patient_data.py` — uses `hasattr(accessor, "get_clinical_notes_by_type")`

## Proposed Solutions

### Option A: Add optional extended methods to Protocol (Recommended)
Define a second `ExtendedClinicalNoteAccessorProtocol(ClinicalNoteAccessorProtocol)` with `@runtime_checkable` that adds the GYN-specific methods. Tools can then use `isinstance(accessor, ExtendedClinicalNoteAccessorProtocol)` instead of `hasattr()` string literals.

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class ExtendedClinicalNoteAccessorProtocol(ClinicalNoteAccessorProtocol, Protocol):
    async def get_clinical_notes_by_type(self, patient_id: str, note_types: Sequence[str]) -> list[dict]: ...
    async def get_clinical_notes_by_keywords(self, patient_id: str, note_types: Sequence[str], keywords: Sequence[str]) -> list[dict]: ...
    async def get_pathology_reports(self, patient_id: str) -> list[dict]: ...
    async def get_radiology_reports(self, patient_id: str) -> list[dict]: ...
    async def get_lab_results(self, patient_id: str, component_name: str | None = None) -> list[dict]: ...
```

Tools replace `hasattr(accessor, "get_clinical_notes_by_type")` with `isinstance(accessor, ExtendedClinicalNoteAccessorProtocol)`.

**Pros:** Type-safe, IDE completion, detects missing methods at import time
**Cons:** Requires updating FhirClinicalNoteAccessor and FabricClinicalNoteAccessor to declare they don't implement the extended protocol (or stub the methods)
**Effort:** Medium (3-4 files)
**Risk:** Low — purely additive

### Option B: Keep hasattr but add comment documenting expected fallback behavior
Add a clear comment in each hasattr guard explaining the expected degradation path.

**Pros:** Zero code change
**Cons:** Type safety not improved; silent degradation remains
**Effort:** Small
**Risk:** None

## Acceptance Criteria
- [ ] `isinstance()` check replaces at least the `get_clinical_notes_by_type` / `get_clinical_notes_by_keywords` hasattr guards
- [ ] FHIR and Fabric accessors are verified to still work (they fall back gracefully via the base interface)
- [ ] No regression in existing tests

## Work Log
- 2026-04-02: Identified by architecture-strategist during code review of 3-layer fallback refactor. New Protocol was added but not extended to cover GYN-specific methods.
- 2026-04-02: Implemented and marked complete.
