---
status: pending
priority: p2
issue_id: "069"
tags: [code-review, architecture, protocol, blob-accessor, missing-methods]
dependencies: []
---

## Problem Statement

`ClinicalNoteAccessor` (the Azure Blob Storage backend at `src/data_models/clinical_note_accessor.py`) is missing 5 stub methods that `ClinicalNoteAccessorProtocol` defines and that both `FhirClinicalNoteAccessor` and `FabricClinicalNoteAccessor` implement:

- `get_pathology_reports(patient_id)`
- `get_radiology_reports(patient_id)`
- `get_cancer_staging(patient_id)`
- `get_medications(patient_id, order_class=None)`
- `get_diagnoses(patient_id)`

Python's structural subtyping (duck-typing Protocol) does not catch missing methods at import time — only at call time with an `AttributeError`. If the tool layer ever calls any of these methods on the Blob backend (currently only Caboodle and potentially FHIR/Fabric backends call them), the Blob backend will raise `AttributeError` instead of returning an empty list, causing a full agent failure.

## Findings

- **File:** `src/data_models/clinical_note_accessor.py` — missing methods
- **File:** `src/data_models/clinical_note_accessor_protocol.py` — defines all 9 methods
- **Reported by:** architecture-strategist
- **Severity:** P2 — `AttributeError` at runtime if these methods are ever called on the Blob backend

## Proposed Solutions

### Option A (Recommended): Add 5 empty stub methods

```python
async def get_pathology_reports(self, patient_id: str) -> list[dict]:
    """Blob backend does not expose dedicated pathology reports. Returns empty list."""
    return []

async def get_radiology_reports(self, patient_id: str) -> list[dict]:
    """Blob backend does not expose dedicated radiology reports. Returns empty list."""
    return []

async def get_cancer_staging(self, patient_id: str) -> list[dict]:
    """Blob backend does not expose structured cancer staging. Returns empty list."""
    return []

async def get_medications(
    self, patient_id: str, order_class: str | None = None
) -> list[dict]:
    """Blob backend does not expose structured medications. Returns empty list."""
    return []

async def get_diagnoses(self, patient_id: str) -> list[dict]:
    """Blob backend does not expose structured diagnoses. Returns empty list."""
    return []
```

### Option B: Add a `runtime_checkable` Protocol and assert at startup

Makes the missing methods fail at startup with a clear error rather than at call time. More complex.

## Technical Details

- **File:** `src/data_models/clinical_note_accessor.py`
- **Protocol:** `src/data_models/clinical_note_accessor_protocol.py`

## Acceptance Criteria

- [ ] `ClinicalNoteAccessor` implements all 9 methods defined in `ClinicalNoteAccessorProtocol`
- [ ] All 5 new stub methods return `[]` and have docstrings matching the Blob context
- [ ] Stale docstrings saying "FHIR backend" updated to "Blob backend" for existing `get_lab_results` and `get_tumor_markers` methods

## Work Log

- 2026-04-02: Identified during architecture review. The Blob backend was the original baseline and predates the protocol; the FHIR and Fabric backends were added later and are complete.
