---
name: OncologicHistoryExtractorPlugin accessor_method is dead code
description: accessor_method = "get_metadata_list" is acknowledged as unused but retained; creates confusion and future risk
type: quality
status: complete
priority: p3
issue_id: "018"
tags: [code-quality, dead-code, code-review]
---

## Problem Statement

`OncologicHistoryExtractorPlugin` sets:
```python
accessor_method = "get_metadata_list"  # not used directly; overrides _extract
```

The comment acknowledges this is dead code. `OncologicHistoryExtractorPlugin` overrides `_extract()` completely, so `accessor_method` from the base class is never consulted. However, the attribute:
1. Misleads readers into thinking `get_metadata_list` is called somewhere
2. Creates a silent failure risk: if the base class is ever refactored to call `accessor_method` for a new feature, this override will call the wrong method with no error

**Affected file:** `src/scenarios/default/tools/oncologic_history_extractor.py`, line 113

## Proposed Solution

**Option A (Recommended):** Remove the attribute entirely. The base class default (`accessor_method = ""`) is fine for a subclass that fully overrides `_extract()`. Add a class docstring explaining the override instead:

```python
class OncologicHistoryExtractorPlugin(MedicalReportExtractorBase):
    """Oncologic history extractor.

    Overrides _extract() completely to read clinical notes rather than a
    dedicated report CSV. The base class accessor_method/layer2/layer3
    attributes are not used by this subclass.
    """
    report_type = "clinical notes"
    # accessor_method intentionally omitted — _extract() is fully overridden
```

**Option B:** Make `accessor_method = None` in the base class and add a guard:
```python
# In base class _extract():
if self.accessor_method and hasattr(accessor, self.accessor_method):
    reports = await getattr(accessor, self.accessor_method)(patient_id)
```
This safely skips the layer 1 accessor call when `accessor_method` is None.

**Effort:** Small (2 lines)

## Acceptance Criteria
- [ ] `accessor_method = "get_metadata_list"` removed from OncologicHistoryExtractorPlugin
- [ ] Class docstring explains the override pattern

## Work Log
- 2026-04-02: Identified by code-simplicity-reviewer and kieran-python-reviewer during code review.
- 2026-04-02: Implemented and marked complete.
