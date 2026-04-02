---
name: tumor-markers-imports-atomics-not-composite
description: tumor_markers.py imports 5 atomic note-type constants instead of the composite GENERAL_CLINICAL_TYPES
type: code-review
status: pending
priority: p3
issue_id: 054
tags: [code-review, dry, maintainability]
---

## Problem Statement

`tumor_markers.py` imports five individual atomic constants from `note_type_constants.py` and manually concatenates them into a list. A composite constant (`GENERAL_CLINICAL_TYPES`) already exists in that same module that is the exact concatenation of those five atomics. This violates the single-source-of-truth intent of `note_type_constants.py` and means that any future change to `GENERAL_CLINICAL_TYPES` would not automatically propagate to `tumor_markers.py`.

## Findings

`tumor_markers.py:16` imports:
```python
from .note_type_constants import (
    CONSULT_NOTE_TYPES,
    DISCHARGE_TYPES,
    ED_NOTE_TYPES,
    HP_TYPES,
    PROGRESS_NOTE_TYPES,
)
```

Then manually concatenates them (approximately line 30+):
```python
_MARKER_NOTE_TYPES = list(PROGRESS_NOTE_TYPES + CONSULT_NOTE_TYPES + ED_NOTE_TYPES + DISCHARGE_TYPES + HP_TYPES)
```

`note_type_constants.py` already defines:
```python
GENERAL_CLINICAL_TYPES = PROGRESS_NOTE_TYPES + CONSULT_NOTE_TYPES + ED_NOTE_TYPES + DISCHARGE_TYPES + HP_TYPES
```

Importing 5 atomics and re-concatenating them is redundant and fragile. If a new note type is added to `GENERAL_CLINICAL_TYPES`, `tumor_markers.py` will silently miss it.

## Proposed Solutions

### Option A
Replace the 5-name import with the composite constant.

**Change import:**
```python
from .note_type_constants import GENERAL_CLINICAL_TYPES
```

**Change usage:**
```python
_MARKER_NOTE_TYPES = list(GENERAL_CLINICAL_TYPES)
```

**Pros:** Eliminates redundancy; future changes to `GENERAL_CLINICAL_TYPES` automatically apply; reduces import surface.
**Cons:** None meaningful.
**Effort:** Small
**Risk:** Low

## Technical Details

**Affected files:**
- `tumor_markers.py` (line 16 import block, line ~30 `_MARKER_NOTE_TYPES` definition)
- `note_type_constants.py` (read-only reference — `GENERAL_CLINICAL_TYPES` definition)

## Acceptance Criteria

- [ ] `tumor_markers.py` imports only `GENERAL_CLINICAL_TYPES` from `note_type_constants.py` (no individual atomic constants)
- [ ] `_MARKER_NOTE_TYPES` is assigned as `list(GENERAL_CLINICAL_TYPES)` without manual concatenation
- [ ] All 5 previously-imported atomic constants are removed from the import block
- [ ] Existing tumor marker trend tests pass unchanged

## Work Log

- 2026-04-02: Identified in code review

## Resources

- Branch: fix/accessor-protocol-cache-quality-015-022
