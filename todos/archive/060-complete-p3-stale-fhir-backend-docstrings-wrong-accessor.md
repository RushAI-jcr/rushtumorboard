---
name: stale-fhir-backend-docstrings-wrong-accessor
description: get_lab_results and get_tumor_markers stub docstrings incorrectly say "FHIR backend" in non-FHIR accessor files
type: code-review
status: complete
priority: p3
issue_id: 060
tags: [code-review, documentation, docstrings]
---

## Problem Statement

The `get_lab_results` and `get_tumor_markers` stub methods in at least three accessor files contain docstrings that reference "FHIR backend" when the file is not the FHIR accessor. These docstrings were copy-pasted from `fhir_clinical_note_accessor.py` without updating the backend name. This misleads developers reading the Azure Blob or Fabric accessor into believing the limitation is FHIR-specific rather than accessor-specific.

## Findings

**`clinical_note_accessor.py:115,120`** (Azure Blob accessor — not FHIR):
```python
def get_lab_results(self, ...) -> list:
    """FHIR backend does not expose structured lab results. Returns empty list."""
    return []

def get_tumor_markers(self, ...) -> list:
    """FHIR backend does not expose structured tumor markers. Returns empty list."""
    return []
```

**`fabric_clinical_note_accessor.py:184-191`** (Fabric accessor — not FHIR):
```python
def get_lab_results(self, ...) -> list:
    """Fabric backend does not expose structured lab results..."""  # line 186: correctly says "Fabric"
    return []

def get_tumor_markers(self, ...) -> list:
    """FHIR backend does not expose structured tumor markers..."""  # line 190: still says "FHIR" — wrong
    return []
```

**`fhir_clinical_note_accessor.py`** (correct — this is the FHIR accessor):
```python
"""FHIR backend does not expose structured lab results. Returns empty list."""
```

Total incorrect docstrings: at least 3 (2 in `clinical_note_accessor.py`, 1 in `fabric_clinical_note_accessor.py`).

## Proposed Solutions

### Option A
Replace all backend-specific references with a backend-agnostic message across all non-FHIR accessor stubs.

**New docstring for all stub methods in all accessor files:**
```python
"""Structured lab results not available via this accessor. Returns empty list."""
```
```python
"""Structured tumor markers not available via this accessor. Returns empty list."""
```

This phrasing is accurate for all accessors (FHIR, Fabric, Azure Blob) and removes the need to track which backend name each file uses.

**Pros:** Single canonical docstring phrasing across all accessors; no future copy-paste errors; accurate for all backends.
**Cons:** Slightly less specific than backend-named docstrings (acceptable trade-off).
**Effort:** Small
**Risk:** Low

## Technical Details

**Affected files:**
- `clinical_note_accessor.py` (lines 115, 120 — 2 docstrings)
- `fabric_clinical_note_accessor.py` (line 190 — 1 docstring; line 186 may also be updated for consistency)
- `fhir_clinical_note_accessor.py` (optional: update for consistency even though currently accurate)

**Total docstrings to update:** 3 minimum (lines 115, 120 in `clinical_note_accessor.py`; line 190 in `fabric_clinical_note_accessor.py`)

## Acceptance Criteria

- [ ] `clinical_note_accessor.py` lines 115 and 120: docstrings no longer reference "FHIR backend"
- [ ] `fabric_clinical_note_accessor.py` line 190: docstring no longer references "FHIR backend"
- [ ] All updated docstrings use a backend-agnostic phrasing (e.g., "not available via this accessor")
- [ ] No functional behavior changed (all stubs still return empty list)
- [ ] Grep for `"FHIR backend"` in non-FHIR accessor files returns zero results

## Work Log

- 2026-04-02: Identified in code review

## Resources

- Branch: fix/accessor-protocol-cache-quality-015-022
