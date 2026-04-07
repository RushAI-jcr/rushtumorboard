---
status: pending
priority: p2
issue_id: "217"
tags: [code-review, quality, dry]
dependencies: []
---

# Repeated Column-Name Fallback Pattern (DRY Violation)

## Problem Statement
The pattern `row.get("CamelCase", row.get("snake_case", row.get("generic", "")))` appears dozens of times across `caboodle_file_accessor.py`, `tumor_markers.py`, `pretumor_board_checklist.py`, and `clinical_note_filter_utils.py`. This is the single largest source of code duplication in the codebase.

## Findings
- `caboodle_file_accessor.py`: lines 178-193, 311-317, and throughout
- `tumor_markers.py`: lines 231-233
- `pretumor_board_checklist.py`: lines 145-149
- `clinical_note_filter_utils.py`: line 65

## Proposed Solution
Extract utility function:
```python
def get_field(row: dict, *keys: str, default: str = "") -> str:
    for key in keys:
        if key in row:
            return row[key]
    return default
```

- **Effort**: Medium (utility + update ~20 call sites)

## Acceptance Criteria
- [ ] Single `get_field()` utility replaces all `row.get("A", row.get("b", ...))` chains
- [ ] All call sites updated
