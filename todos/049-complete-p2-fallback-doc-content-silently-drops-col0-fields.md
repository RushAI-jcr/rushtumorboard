---
name: fallback-doc-content-silently-drops-col0-fields
description: _fallback_doc_content in content_export.py builds TumorBoardDocContent without any of the 9 new Col 0 fields, silently producing blank name/MRN/attending in the rendered document
type: code-review
status: complete
priority: p2
issue_id: 049
tags: [code-review, reliability, logging, fallback]
---

## Problem Statement

`content_export.py:385-411`: `_fallback_doc_content` (called when LLM parsing fails) constructs `TumorBoardDocContent` without any of the 9 new Col 0 fields (`case_number`, `patient_last_name`, `mrn`, `attending_initials`, `is_inpatient`, `rtc`, `main_location`, `path_date`, `ca125_trend_in_col0`). Because all 9 have Pydantic defaults, no `ValidationError` is raised, but the rendered document silently has `case_number=1` and blank name/MRN/attending. No log warning indicates Col 0 is incomplete.

## Findings

- `content_export.py:385-411`: `_fallback_doc_content` constructs `TumorBoardDocContent` omitting all 9 Col 0 fields
- All 9 Col 0 fields have Pydantic defaults — no `ValidationError` is raised, so the failure is silent
- Rendered Word document has `case_number=1`, blank `patient_last_name`, blank `mrn`, blank `attending_initials`
- No `logger.warning` call indicates to operators that the fallback path was used or that Col 0 is incomplete
- Some Col 0 fields (e.g., `patient_last_name`, `ca125_trend_in_col0`) could be partially populated from the raw `data` dict without LLM assistance — but the fallback makes no attempt

## Proposed Solutions

### Option A
Add a `logger.warning` call in `_fallback_doc_content` that lists which Col 0 fields are being defaulted (i.e., all 9). Attempt best-effort population of `patient_last_name` from `data.get("patient_id", "")` and `ca125_trend_in_col0` from tumor marker data available in `data`. Log the specific fields that could not be populated.

**Pros:** Immediate operator visibility when fallback fires; partial Col 0 recovery at no extra LLM cost; minimal code change
**Cons:** `patient_id` is a GUID, not a last name — the best-effort `patient_last_name` population may not be meaningful; adds complexity to the fallback path
**Effort:** Small (1-2 hours)
**Risk:** Low

### Option B
Extract a `_build_fallback_col0(data: dict) -> dict` helper that systematically extracts all Col 0 values that can be derived from the raw data dict without LLM parsing, and logs what it could and could not populate. `_fallback_doc_content` calls this helper.

**Pros:** Cleaner separation of concerns; easier to extend as new Col 0 fields are added; single test target for the Col 0 fallback logic
**Cons:** Slightly more code than Option A
**Effort:** Small (2-3 hours)
**Risk:** Low

## Recommended Action

## Technical Details

**Affected files:**
- `src/plugins/content_export.py` (lines 385-411, `_fallback_doc_content`)

## Acceptance Criteria

- [ ] `_fallback_doc_content` emits a `logger.warning` when called, listing which Col 0 fields are being defaulted
- [ ] `patient_last_name` and `ca125_trend_in_col0` are populated from available data where possible
- [ ] Warning log is visible in Azure Monitor telemetry (not suppressed by log level config)
- [ ] PHI is not included in the warning log (patient_id truncated or omitted per todo 001 pattern)
- [ ] Existing fallback tests updated to assert the warning is emitted

## Work Log

- 2026-04-02: Identified in code review

## Resources

- Branch: fix/accessor-protocol-cache-quality-015-022
