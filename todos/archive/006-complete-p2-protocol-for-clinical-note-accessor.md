---
status: complete
priority: p2
issue_id: "006"
tags: [code-review, architecture, python-quality, type-safety]
dependencies: []
---

## Problem Statement

`DataAccess.clinical_note_accessor` is declared as `ClinicalNoteAccessor` (the Azure Blob-backed class) but at runtime receives a `CaboodleFileAccessor`, `FhirClinicalNoteAccessor`, or `FabricClinicalNoteAccessor` — none of which inherit from `ClinicalNoteAccessor`. The type annotation is false for 3 of 4 production paths. This is the root cause of every `hasattr()` guard in `medical_report_extractor.py` and `tumor_markers.py`.

All four concrete accessors already implement the same minimal interface: `get_patients`, `get_metadata_list`, `read`, `read_all`. The formal contract just needs to be declared.

## Findings

- **Files:** `src/data_models/data_access.py:89`, `src/data_models/epic/caboodle_file_accessor.py`
- **Reported by:** architecture-strategist, kieran-python-reviewer (P1 in both)
- **Severity:** P2 — type system is lying; all `hasattr` guards are symptoms of this

## Proposed Solutions

### Option A (Recommended): Define a Protocol

```python
# New file: src/data_models/clinical_note_accessor_protocol.py
from typing import Protocol
from collections.abc import Sequence

class ClinicalNoteAccessorProtocol(Protocol):
    async def get_patients(self) -> list[str]: ...
    async def get_metadata_list(self, patient_id: str) -> list[dict[str, str]]: ...
    async def read(self, patient_id: str, note_id: str) -> str: ...
    async def read_all(self, patient_id: str) -> list[str]: ...
```

Update `DataAccess`:
```python
from data_models.clinical_note_accessor_protocol import ClinicalNoteAccessorProtocol

@dataclass
class DataAccess:
    clinical_note_accessor: ClinicalNoteAccessorProtocol
    # ...
```

The optional extended methods (`get_clinical_notes_by_type`, `get_lab_results`, etc.) remain capability-checked via `hasattr()` since they are not present on all implementations.

### Option B: Convert ClinicalNoteAccessor to ABC
Make `ClinicalNoteAccessor` an abstract base class and have all four concrete classes inherit from it. More invasive but provides stronger guarantees.

- **Effort:** Medium (Protocol: new file + 1 import change; ABC: 4 class changes)
- **Risk:** Low — structural subtyping via Protocol requires no changes to concrete classes

## Recommended Action

Option A — Protocol is non-invasive and sufficient.

## Technical Details

- **Affected files:**
  - `src/data_models/data_access.py` line 89
  - `src/data_models/clinical_note_accessor.py` (existing blob accessor)
  - New file: `src/data_models/clinical_note_accessor_protocol.py`

## Acceptance Criteria

- [ ] `ClinicalNoteAccessorProtocol` declared with the 4 shared methods
- [ ] `DataAccess.clinical_note_accessor` typed as `ClinicalNoteAccessorProtocol`
- [ ] All 4 concrete accessor classes structurally satisfy the protocol (verified via pyright)
- [ ] Existing `hasattr()` guards for extended methods remain (they are still correct for capability detection)

## Work Log

- 2026-04-02: Identified by architecture-strategist and kieran-python-reviewer
