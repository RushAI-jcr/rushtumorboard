---
status: complete
priority: p2
issue_id: "008"
tags: [code-review, python-quality, type-safety]
dependencies: []
---

## Problem Statement

Several code quality issues in `caboodle_file_accessor.py` and `medical_report_extractor.py`:

1. **Unused imports** (`caboodle_file_accessor.py:11-12`): `from io import StringIO` and `from pathlib import Path` are imported but never used in the 379-line file. Will cause `ruff`/`flake8` failures.

2. **Incomplete `Optional` → `str | None` migration** (`caboodle_file_accessor.py:14, 159, 185`): The PR correctly added `from collections.abc import Sequence` but left `from typing import Optional` for two remaining usages (`get_lab_results`, `get_medications`). Python 3.12 uses `str | None` natively. Mixed import styles signal an incomplete migration.

3. **JSON fence extraction via `.split()` is fragile** (`medical_report_extractor.py:164-169`): The `IndexError` in `except (json.JSONDecodeError, IndexError)` exists specifically because `.split("```")` can produce wrong results when the LLM emits multiple fences, trailing text, or ```` ```json\n ```` with trailing whitespace. Use a compiled regex instead.

## Findings

- **Files:** `src/data_models/epic/caboodle_file_accessor.py`, `src/scenarios/default/tools/medical_report_extractor.py`
- **Lines:** 11-12, 14, 159, 185, 262 (accessor); 164-169 (extractor)
- **Reported by:** kieran-python-reviewer
- **Severity:** P2 — linter failures, incomplete migration, fragile LLM output parsing

## Proposed Solutions

### Option A (All fixes together):

**Remove unused imports:**
```python
# Remove lines 11-12:
# from io import StringIO  ← DELETE
# from pathlib import Path  ← DELETE
```

**Complete Optional migration:**
```python
# Lines 159, 185 — change Optional[str] to str | None:
async def get_lab_results(self, patient_id: str, component_name: str | None = None) -> list[dict]:
async def get_medications(self, patient_id: str, order_class: str | None = None) -> list[dict]:
# Then remove: from typing import Optional
```

**Fix JSON fence extraction:**
```python
import re
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)

# In _extract(), replace the split logic:
match = _JSON_FENCE_RE.search(response_text)
json_str = match.group(1).strip() if match else response_text.strip()
findings = json.loads(json_str)
```
This also removes the `IndexError` from the except clause since it's no longer needed.

- **Effort:** Small
- **Risk:** None

## Recommended Action

Option A — all fixes are mechanical and safe.

## Technical Details

- **Affected files:**
  - `src/data_models/epic/caboodle_file_accessor.py` lines 11-12, 14, 159, 185, 262
  - `src/scenarios/default/tools/medical_report_extractor.py` lines 164-169

## Acceptance Criteria

- [ ] `ruff check` passes with no unused import warnings on `caboodle_file_accessor.py`
- [ ] `from typing import Optional` removed; `str | None` used throughout
- [ ] JSON fence extraction uses compiled regex
- [ ] `IndexError` removed from `except` clause in `_extract`

## Work Log

- 2026-04-02: Identified by kieran-python-reviewer during code review
