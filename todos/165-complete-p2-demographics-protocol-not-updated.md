---
status: complete
priority: p2
issue_id: "165"
tags: [code-review, architecture, python]
dependencies: []
---

# get_patient_demographics Not Added to Protocol/Mixin

## Problem Statement

`get_patient_demographics` was added to `CaboodleFileAccessor` but NOT to `ClinicalNoteAccessorProtocol` or `ClinicalNoteAccessorStubMixin`. This forces `patient_data.py:116` to use `hasattr(accessor, "get_patient_demographics")` — a runtime duck-typing check that circumvents the Protocol-based accessor design. Demographics silently degrade to `None` for FHIR, Fabric, and Blob accessors without warning.

This is a known anti-pattern in this codebase — archived TODO 006 documents that the same `hasattr()` pattern was the root cause of similar issues in `medical_report_extractor.py` and `tumor_markers.py`, resolved by expanding the Protocol.

## Findings

- **Source**: Python Reviewer (CRITICAL), Architecture Strategist (MEDIUM), Agent-Native Reviewer (CRITICAL), Code Simplicity (MEDIUM)
- **Files**: `src/scenarios/default/tools/patient_data.py:116`, `src/data_models/clinical_note_accessor_protocol.py`, `src/data_models/accessor_stub_mixin.py`
- **Known Pattern**: `docs/solutions/` — archived TODO 006 documents same hasattr anti-pattern resolved for other methods

## Proposed Solutions

### Option A: Add to Protocol + Mixin (Recommended)
1. Add `async def get_patient_demographics(self, patient_id: str) -> dict | None` to `ClinicalNoteAccessorProtocol`
2. Add stub returning `None` to `ClinicalNoteAccessorStubMixin`
3. Add `"get_patient_demographics"` to `_STUB_METHODS` frozenset
4. Remove `hasattr` guard in `patient_data.py`
- **Pros**: Follows established pattern, type-safe, explicit contract
- **Cons**: Touches 3 files
- **Effort**: Small (~6 lines across 3 files)
- **Risk**: None

## Recommended Action

Option A.

## Technical Details

- **Affected files**: `src/data_models/clinical_note_accessor_protocol.py`, `src/data_models/accessor_stub_mixin.py`, `src/scenarios/default/tools/patient_data.py`

## Acceptance Criteria

- [ ] `get_patient_demographics` exists on Protocol
- [ ] `get_patient_demographics` exists on StubMixin returning `None`
- [ ] No `hasattr` guard in `patient_data.py`
- [ ] FHIR/Fabric/Blob accessors inherit stub and return `None` gracefully

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-04-04 | Code review finding | 4 of 7 reviewers flagged this; matches archived TODO 006 pattern |

## Resources

- `todos/archive/006-complete-p2-protocol-for-clinical-note-accessor.md`
