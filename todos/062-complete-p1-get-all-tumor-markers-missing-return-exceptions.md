---
status: pending
priority: p1
issue_id: "062"
tags: [code-review, reliability, asyncio, tumor-markers, error-handling]
dependencies: []
---

## Problem Statement

`get_all_tumor_markers` in `tumor_markers.py` uses `asyncio.gather` without `return_exceptions=True`. The PR correctly added `return_exceptions=True` to `get_tumor_marker_trend`, but the sibling function was missed. If either `get_tumor_markers` or `get_lab_results` raises (network error, FHIR/Fabric unavailability), the exception propagates unhandled out of the `@kernel_function`. Semantic Kernel will surface the raw exception text to the LLM as a tool error, which may include stack traces with internal path or configuration details. Additionally, `return_exceptions=True` should check `isinstance(r, Exception)` not `isinstance(r, BaseException)` — the latter swallows `KeyboardInterrupt` and `SystemExit`.

## Findings

- **File:** `src/scenarios/default/tools/tumor_markers.py`, lines 242–245
- **Reported by:** security-sentinel, kieran-python-reviewer, agent-native-reviewer
- **Severity:** P1 — PatientStatus agent may hard-fail instead of gracefully falling back to clinical notes

```python
# Current — no error handling:
tumor_markers_result, all_labs = await asyncio.gather(
    accessor.get_tumor_markers(patient_id),
    accessor.get_lab_results(patient_id),
)
```

vs. the correct pattern already in `get_tumor_marker_trend` (lines 153–161):
```python
labs_result, all_markers_result = await asyncio.gather(
    accessor.get_lab_results(patient_id, component_name=marker),
    accessor.get_tumor_markers(patient_id),
    return_exceptions=True,
)
if isinstance(labs_result, BaseException):  # should be Exception
    labs_result = []
```

## Proposed Solutions

### Option A (Recommended): Mirror get_tumor_marker_trend pattern with Exception check

```python
tumor_markers_result, all_labs_result = await asyncio.gather(
    accessor.get_tumor_markers(patient_id),
    accessor.get_lab_results(patient_id),
    return_exceptions=True,
)
if isinstance(tumor_markers_result, Exception):
    logger.warning("get_tumor_markers failed for patient: %s", type(tumor_markers_result).__name__)
    tumor_markers_result = []
if isinstance(all_labs_result, Exception):
    logger.warning("get_lab_results failed for patient: %s", type(all_labs_result).__name__)
    all_labs_result = []
all_markers = tumor_markers_result or all_labs_result
```

Note: also fix the existing check in `get_tumor_marker_trend` from `BaseException` to `Exception` (separate line change).

## Technical Details

- **File:** `src/scenarios/default/tools/tumor_markers.py`
- **Method:** `get_all_tumor_markers` (lines 238–255)
- **Related:** `get_tumor_marker_trend` lines 146–160 (correct pattern, but uses `BaseException`)

## Acceptance Criteria

- [ ] `get_all_tumor_markers` gather uses `return_exceptions=True`
- [ ] Each result is checked with `isinstance(r, Exception)` (not `BaseException`)
- [ ] On accessor failure, falls back to empty list + logger.warning (no patient_id in log)
- [ ] `get_tumor_marker_trend`'s existing `BaseException` check updated to `Exception`
- [ ] PatientStatus agent receives a graceful "no data found" rather than a tool error on accessor failure

## Work Log

- 2026-04-02: Identified during code review. `get_tumor_marker_trend` was fixed in this PR; `get_all_tumor_markers` was missed.
