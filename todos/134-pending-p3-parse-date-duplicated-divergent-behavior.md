---
status: pending
priority: p3
issue_id: "134"
tags: [code-review, simplicity, quality]
dependencies: []
---

# 134 — `_parse_date` duplicated with divergent behavior across two modules

## Problem Statement

`_parse_date` is independently defined in `tumor_markers.py:26-39` and `pretumor_board_checklist.py:107-121` with different implementations. `tumor_markers.py` uses `datetime.fromisoformat()` as the primary strategy (handles ISO 8601 with timezone offsets), while `pretumor_board_checklist.py` uses only explicit format strings and does not call `fromisoformat()`. The date string `"2024-04-11T09:30:00+05:30"` parses successfully in `tumor_markers.py` but fails silently in `pretumor_board_checklist.py`. The `_DATE_FORMATS` list is also duplicated and may drift between the two files over time.

## Findings

- `tumor_markers.py:26-39` — `_parse_date` using `fromisoformat()` as primary
- `pretumor_board_checklist.py:107-121` — `_parse_date` using format strings only, no `fromisoformat()`

## Proposed Solution

Extract a single `parse_date_flexible(s: str) -> date | None` utility in `utils/date_utils.py`:

```python
def parse_date_flexible(s: str) -> date | None:
    try:
        return datetime.fromisoformat(s).date()
    except (ValueError, TypeError):
        pass
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None
```

Remove the local definitions and `_DATE_FORMATS` constants in both files and import from `utils.date_utils`.

## Acceptance Criteria

- [ ] Single `parse_date_flexible` function exists in `utils/date_utils.py`
- [ ] `tumor_markers.py` and `pretumor_board_checklist.py` both import from `utils.date_utils`
- [ ] ISO 8601 date strings with timezone offsets (e.g., `"2024-04-11T09:30:00+05:30"`) parse correctly in both contexts
- [ ] Duplicate `_DATE_FORMATS` lists removed from both modules
