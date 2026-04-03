---
status: complete
priority: p3
issue_id: "024"
tags: [code-review, python-quality, style]
dependencies: []
---

## Problem Statement

`_report_date_key` is defined as a nested function inside `MedicalReportExtractorBase._extract()`. While Python allows this, nested function definitions are recreated on every call and make the code harder to test in isolation or reuse.

```python
# Current — nested inside _extract():
def _report_date_key(r: dict) -> str:
    return r.get("OrderDate", r.get("EntryDate", r.get("date", r.get("order_date", ""))))

reports = sorted(reports, key=_report_date_key)
```

## Findings

- **File:** `src/scenarios/default/tools/medical_report_extractor.py` — inside `_extract()` method
- **Reported by:** code-simplicity-reviewer, kieran-python-reviewer (P3)
- **Severity:** P3 — style/quality; no functional impact

## Proposed Solutions

### Option A (Recommended): Move to module level
```python
# At module level (after imports, before class definition):
def _report_date_key(r: dict) -> str:
    """Sort key: prefer OrderDate, then EntryDate, then date, then order_date."""
    return r.get("OrderDate", r.get("EntryDate", r.get("date", r.get("order_date", ""))))
```
- **Pros:** Defined once; testable in isolation; standard Python convention for sort key functions
- **Effort:** Tiny (cut/paste + adjust indentation)
- **Risk:** None

## Recommended Action

Option A — trivial move, apply when touching the file for todo 018 (sort cap fix).

## Technical Details

- **Affected file:** `src/scenarios/default/tools/medical_report_extractor.py`
- **Do together with:** todo 018 (sort-cap-drops-newest fix) since both touch `_extract()`

## Acceptance Criteria

- [ ] `_report_date_key` defined at module level, not inside `_extract()`
- [ ] Existing sort behavior unchanged

## Work Log

- 2026-04-02: Identified by code-simplicity-reviewer during code review
