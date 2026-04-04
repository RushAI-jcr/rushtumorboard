---
status: complete
priority: p2
issue_id: "022"
tags: [code-review, python-quality, json-parsing, consistency]
dependencies: []
---

## Problem Statement

`oncologic_history_extractor.py` uses a manual string-split approach for JSON fence parsing in its `_extract()` method, while the base class `medical_report_extractor.py` already has a compiled regex `_JSON_FENCE_RE` for this exact purpose. This creates two parsing code paths that can diverge and makes the subclass harder to maintain.

```python
# oncologic_history_extractor.py (current — manual split):
if "```json" in response_text:
    json_str = response_text.split("```json")[1].split("```")[0].strip()
elif "```" in response_text:
    json_str = response_text.split("```")[1].split("```")[0].strip()
else:
    json_str = response_text

# medical_report_extractor.py base class (compiled regex — better):
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)
match = _JSON_FENCE_RE.search(response_text)
json_str = match.group(1).strip() if match else response_text.strip()
```

The manual approach also has an edge case bug: if the response contains multiple code fences, `split("```")[1]` may grab the wrong block.

## Findings

- **File:** `src/scenarios/default/tools/oncologic_history_extractor.py` lines 206–212
- **Base class:** `src/scenarios/default/tools/medical_report_extractor.py` — `_JSON_FENCE_RE` at module level
- **Reported by:** code-simplicity-reviewer, kieran-python-reviewer
- **Severity:** P2 — inconsistency and potential parsing edge case

## Proposed Solutions

### Option A (Recommended): Import and use `_JSON_FENCE_RE` from base module
```python
from .medical_report_extractor import _JSON_FENCE_RE, MedicalReportExtractorBase

# In _extract():
match = _JSON_FENCE_RE.search(response_text)
json_str = match.group(1).strip() if match else response_text.strip()
```
- **Pros:** Single parsing implementation; uses compiled regex (faster); fixes multi-fence edge case; consistent with all other extractor subclasses
- **Cons:** Imports a "private" symbol (`_JSON_FENCE_RE`) — consider making it public (`JSON_FENCE_RE`)
- **Effort:** Small
- **Risk:** None

### Option B: Move `_JSON_FENCE_RE` to a shared utility and import everywhere
Put it in `validation.py` or a new `llm_utils.py` so it's a proper shared utility.
- **Pros:** Clean API; not importing private symbol
- **Cons:** Small refactor across all extractor files
- **Effort:** Small–Medium

## Recommended Action

Option A immediately (one-file fix). Option B as a follow-up when doing the note type constants consolidation (todo 020).

## Technical Details

- **Affected file:** `src/scenarios/default/tools/oncologic_history_extractor.py` lines 206–212
- **Replace:** The `if/elif/else` split block with `_JSON_FENCE_RE.search()` call

## Acceptance Criteria

- [ ] `oncologic_history_extractor.py` uses `_JSON_FENCE_RE` (or equivalent) for JSON fence extraction
- [ ] Manual `split("```json")` pattern removed
- [ ] Both ```` ```json ``` ```` and ```` ``` ```` fences handled by same code path

## Work Log

- 2026-04-02: Identified by code-simplicity-reviewer during code review
