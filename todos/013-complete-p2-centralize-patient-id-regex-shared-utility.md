---
status: complete
priority: p2
issue_id: "013"
tags: [code-review, python-quality, duplication, maintainability]
dependencies: []
---

## Problem Statement

`_PATIENT_ID_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_\-\.]{0,63}$')` is copied verbatim into 5 separate files. All three review agents flagged this independently: if the regex ever needs to change (e.g., to support GUIDs from a new Epic environment), all 5 copies must be updated in sync or they silently diverge.

**Files with copies:**
- `src/scenarios/default/tools/patient_data.py` (+ `_is_valid()` wrapper function)
- `src/scenarios/default/tools/pathology_extractor.py`
- `src/scenarios/default/tools/radiology_extractor.py`
- `src/scenarios/default/tools/oncologic_history_extractor.py`
- `src/scenarios/default/tools/tumor_markers.py`

Additional inconsistency: `patient_data.py` calls `_is_valid(patient_id)` via a wrapper; the other 4 call `_PATIENT_ID_RE.fullmatch(patient_id)` directly.

## Findings

- **Reported by:** security-sentinel, kieran-python-reviewer, code-simplicity-reviewer (all three)
- **Severity:** P2 — maintenance risk; behavior is correct today but fragile under change

## Proposed Solution

Create `src/scenarios/default/tools/validation.py` (6 lines):
```python
import re

_PATIENT_ID_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_\-\.]{0,63}$')

def validate_patient_id(patient_id: str) -> bool:
    return bool(_PATIENT_ID_RE.fullmatch(patient_id))
```

In each of the 5 files:
- Remove `import re` (if only used for `_PATIENT_ID_RE`)
- Remove the `_PATIENT_ID_RE = re.compile(...)` line
- In `patient_data.py`: remove `_is_valid()` and replace its 3 call sites with `validate_patient_id(patient_id)`
- In the 4 extractor files: replace `_PATIENT_ID_RE.fullmatch(patient_id)` with `validate_patient_id(patient_id)`

**Alternative:** Put `_PATIENT_ID_RE` in `medical_report_extractor.py` (base class already imported by 4 of the 5 files). Slightly less clean since `patient_data.py` does not inherit from it.

- **Effort:** Small (~15 min)
- **Risk:** None — pure extract refactor, behavior identical

## Acceptance Criteria

- [ ] `_PATIENT_ID_RE` defined in exactly one place
- [ ] All 5 files import `validate_patient_id` from the shared module
- [ ] `_is_valid` wrapper removed from `patient_data.py`
- [ ] All call sites use `validate_patient_id(patient_id)` consistently
- [ ] `import re` removed from all 5 tool files (if no other usage)

## Work Log

- 2026-04-02: Identified unanimously by all three review agents in P1 re-review
