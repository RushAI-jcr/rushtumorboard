---
status: pending
priority: p3
issue_id: "076"
tags: [code-review, style, python, class-design]
dependencies: []
---

## Problem Statement

`_CACHE_MAX_PATIENTS` is defined as an instance attribute in `__init__` in all three fallback accessors:

```python
self._CACHE_MAX_PATIENTS: int = 5
```

The ALL_CAPS naming convention signals a constant. Instance attributes participate in `__dict__`, waste memory (minor), and mislead readers into thinking the value can vary per-instance. It should be a class-level constant:

```python
class FhirClinicalNoteAccessor:
    _CACHE_MAX_PATIENTS: int = 5
```

## Findings

- **File:** `src/data_models/fhir/fhir_clinical_note_accessor.py`, line 64
- **File:** `src/data_models/fabric/fabric_clinical_note_accessor.py`, line 40
- **File:** `src/data_models/clinical_note_accessor.py`, line 28
- **Reported by:** kieran-python-reviewer, code-simplicity-reviewer
- **Severity:** P3 — style inconsistency; constants should be class-level

## Proposed Solutions

Move `_CACHE_MAX_PATIENTS: int = 5` from `__init__` to class body (before `__init__`) in all three accessor classes.

## Acceptance Criteria

- [ ] `_CACHE_MAX_PATIENTS` is a class-level attribute in all three accessors
- [ ] No assignment of `self._CACHE_MAX_PATIENTS` in `__init__`
- [ ] References (`self._CACHE_MAX_PATIENTS` or `ClassName._CACHE_MAX_PATIENTS`) updated consistently

## Work Log

- 2026-04-02: Identified during code review.
