---
status: pending
priority: p3
issue_id: "236"
tags: [code-review, architecture]
dependencies: []
---

# COLUMN_ALIASES Duplicated Between Accessor and Validator Script

## Problem Statement

`COLUMN_ALIASES` dict is copy-pasted identically in `validate_patient_csvs.py` and `caboodle_file_accessor.py` with a comment "same mapping as the accessor." When a new alias is added to the accessor, the validator won't pick it up.

## Findings

**Flagged by:** Architecture Strategist (#2C), Kieran Python Reviewer (#12)

**Files:**
- `src/data_models/epic/caboodle_file_accessor.py` — `_COLUMN_ALIASES`
- `scripts/validate_patient_csvs.py` — `COLUMN_ALIASES`

## Proposed Solutions

### Option A: Import from accessor (Recommended)
```python
from data_models.epic.caboodle_file_accessor import CaboodleFileAccessor
COLUMN_ALIASES = CaboodleFileAccessor._COLUMN_ALIASES
```
Or extract to a shared constants module if import path is problematic.
- Effort: Tiny | Risk: None

## Acceptance Criteria

- [ ] Single source of truth for column aliases
- [ ] Validator uses the same mapping as the accessor

## Work Log

- 2026-04-09: Created from code review
