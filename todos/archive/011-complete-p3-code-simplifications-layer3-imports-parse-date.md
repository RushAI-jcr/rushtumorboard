---
status: complete
priority: p3
issue_id: "011"
tags: [code-review, python-quality, simplicity]
dependencies: []
---

## Problem Statement

Several small simplification opportunities across the changed files:

1. **Layer 3 double `hasattr` guard** (`medical_report_extractor.py:77-79`): The layer 3 block has a nested `if hasattr()` inside an outer `if not reports`, making `source_layer = 3` set outside the inner guard. This asymmetry with layer 2 is confusing. Flatten to a single compound condition matching layer 2 style.

2. **`_parse_date` timezone stripping is hand-rolled and fragile** (`tumor_markers.py:27-33`): Python 3.12's `datetime.fromisoformat()` handles timezone-aware ISO 8601 strings natively. The manual character-counting approach can produce wrong results on edge cases. Simplify to try `fromisoformat` first, strip tz, then fall back to format probing.

3. **`Path(self.data_dir).resolve()` recomputed on every `_read_file` call** (`caboodle_file_accessor.py`): Cache `Path(self.data_dir).resolve()` as `self._resolved_data_dir` in `__init__` and reuse in `_read_file` and `_read_legacy_json_sync`.

4. **Redundant `or` in patient ID comparison** (`caboodle_file_accessor.py:298`): `str(row_patient) == str(patient_id) or row_patient == patient_id` — the second branch is unreachable since `str(x) == str(y)` covers the case when both are already strings.

## Findings

- **Files:** `medical_report_extractor.py:77-79`, `tumor_markers.py:27-33`, `caboodle_file_accessor.py:261, 298`
- **Reported by:** code-simplicity-reviewer, kieran-python-reviewer, performance-oracle
- **Severity:** P3 — minor cleanup; no functionality change

## Proposed Solutions

**Layer 3 guard (flatten nested `if`):**
```python
# Replace lines 77-87 with:
if not reports and self.layer3_note_types and self.layer3_keywords and hasattr(accessor, "get_clinical_notes_by_keywords"):
    reports = await accessor.get_clinical_notes_by_keywords(
        patient_id, self.layer3_note_types, self.layer3_keywords
    )
    if reports:
        source_layer = 3
        logger.info("Layer 3 fallback: ...")
```

**`_parse_date` simplification:**
```python
def _parse_date(date_str: str) -> datetime:
    cleaned = date_str.strip()
    try:
        dt = datetime.fromisoformat(cleaned)
        return dt.replace(tzinfo=None)  # strip tz for naive comparison
    except ValueError:
        pass
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    logger.warning("Could not parse date: %r", date_str)
    return datetime.min
```

**Cache resolved data dir:**
```python
# In __init__:
self._resolved_data_dir = Path(self.data_dir).resolve()
# In _read_file:
if not Path(patient_dir).resolve().is_relative_to(self._resolved_data_dir):
```

**Patient ID comparison:**
```python
if str(row.get("PatientID", row.get("patient_id", patient_id))) == str(patient_id):
```

## Acceptance Criteria

- [ ] Layer 3 block uses single compound `if` condition matching layer 2 style
- [ ] `_parse_date` simplified using `fromisoformat` first
- [ ] `self._resolved_data_dir` cached in `__init__`
- [ ] Patient ID comparison has no redundant `or` branch
- [ ] All tests still pass

## Work Log

- 2026-04-02: Identified by code-simplicity-reviewer and kieran-python-reviewer
