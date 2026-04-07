---
status: pending
priority: p2
issue_id: "209"
tags: [code-review, architecture, data-access]
dependencies: []
---

# Factory Falls Through on Invalid CLINICAL_NOTES_SOURCE

## Problem Statement
`create_data_access()` uses cascading `if/elif/else` on `CLINICAL_NOTES_SOURCE` env var. A misspelled value (e.g., "fabrik") falls through to default `BlobClinicalNoteAccessor` with only a `logger.warning`. In production, this silently uses the wrong accessor with no structured data.

## Findings
- **File**: `src/data_models/data_access.py`, lines 121-141
- No validation of the env var value
- `create_local_dev_data_access()` always uses CaboodleFileAccessor regardless of env var — inconsistency

## Proposed Solution
Raise `ValueError` on unrecognized values. Log selected accessor class at INFO.

```python
else:
    raise ValueError(f"Unknown CLINICAL_NOTES_SOURCE: {clinical_notes_source!r}. "
                     f"Valid values: fhir, fabric, epic, caboodle")
```

- **Effort**: Small (5 lines)

## Acceptance Criteria
- [ ] Unrecognized CLINICAL_NOTES_SOURCE raises ValueError at startup
- [ ] Selected accessor class name logged at INFO
