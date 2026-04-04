---
name: patient-id-in-404-response-bodies
description: 404 error responses include patient_id and other PHI identifiers in response bodies; IndexError produces 500s on out-of-range path parameters
type: code-review
status: complete
priority: p3
issue_id: 059
tags: [code-review, security, phi, hipaa, error-handling]
---

## Problem Statement

Two route files return PHI identifiers in error response bodies: `patient_id`, `entry_index`, and `answer_id` are included as plaintext in 404 JSON responses. Response body PHI disclosure violates HIPAA if these routes are reachable by any unauthenticated or unintended client. Additionally, `entry_index` and `source_index` are path parameters passed directly to `timeline.entries[int(entry_index)]` without bounds checking — out-of-range values raise `IndexError` which produces unhandled 500 responses.

## Findings

`src/routes/views/patient_timeline_routes.py:52` (approximate):
```python
return JSONResponse(
    status_code=404,
    content={"error": "Entry not found", "patient_id": patient_id, "entry_index": entry_index}
)
```

`patient_data_answer_routes.py:48` (approximate):
```python
return JSONResponse(
    status_code=404,
    content={"error": "Answer not found", "patient_id": patient_id, "answer_id": answer_id}
)
```

Separately, `timeline.entries[int(entry_index)]` is accessed without bounds checking:
- If `entry_index` is out of range, Python raises `IndexError`
- No exception handler catches this; FastAPI returns a 500 with a stack trace

PHI identifiers included in response bodies:
- `patient_id` — direct patient identifier (PHI)
- `entry_index` / `answer_id` — indirect identifiers tied to a specific patient record (PHI in context)

## Proposed Solutions

### Option A
Replace error response bodies with generic "Resource not found." and add bounds checking before list indexing.

```python
# Replace PHI-bearing 404 responses:
return JSONResponse(status_code=404, content={"error": "Resource not found."})

# Add bounds checking before indexing:
idx = int(entry_index)
if idx < 0 or idx >= len(timeline.entries):
    return JSONResponse(status_code=404, content={"error": "Resource not found."})
entry = timeline.entries[idx]
```

**Pros:** Eliminates PHI from error responses; converts out-of-range 500s to 404s; no patient-specific data leaked.
**Cons:** Less debugging detail in logs (mitigated by server-side logging with PHI).
**Effort:** Small
**Risk:** Low

### Option B
Add an exception handler for `IndexError` returning 404 instead of 500, while retaining existing 404 response bodies.

```python
try:
    entry = timeline.entries[int(entry_index)]
except (IndexError, ValueError):
    return JSONResponse(status_code=404, content={"error": "Resource not found."})
```

**Pros:** Fixes the 500 issue; minimal code change.
**Cons:** Does not fix PHI in 404 response bodies — PHI disclosure risk remains for non-IndexError 404 paths.
**Effort:** Small
**Risk:** Low (for 500 fix only; PHI issue remains)

## Technical Details

**Affected files:**
- `src/routes/views/patient_timeline_routes.py` (line 52, `entry_index` indexing)
- `src/routes/views/patient_data_answer_routes.py` (line 48, `answer_id` 404 response)

**Related context:**
- PHI handling policy for this project: PHI must not appear in response bodies, only in server-side logs (see todo 001, 004 for prior PHI-in-logs findings).
- The correct pattern is: log PHI server-side at DEBUG level, return generic error to client.

## Acceptance Criteria

- [ ] `patient_timeline_routes.py` 404 response body contains no `patient_id` or `entry_index`
- [ ] `patient_data_answer_routes.py` 404 response body contains no `patient_id` or `answer_id`
- [ ] Out-of-range `entry_index` produces a 404 response, not a 500
- [ ] Out-of-range `source_index` (if applicable) produces a 404 response, not a 500
- [ ] PHI identifiers are still logged server-side at an appropriate log level for debugging
- [ ] No regression in timeline or answer route happy-path behavior

## Work Log

- 2026-04-02: Identified in code review

## Resources

- Branch: fix/accessor-protocol-cache-quality-015-022
