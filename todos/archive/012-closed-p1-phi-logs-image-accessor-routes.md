---
status: closed
priority: p1
issue_id: "012"
tags: [code-review, security, hipaa, phi, logging]
dependencies: []
---

## Problem Statement

Two files missed in the original PHI-in-logs sweep have f-string log statements that write patient-identifiable data to Azure Monitor. Same HIPAA severity as todos 001–004 (all fixed).

1. **`image_accessor.py:44`** — logs `patient_id` directly:
   ```python
   logger.info(f"Get image metadata for {patient_id}. Duration: {time() - start}s")
   ```

2. **`image_accessor.py:69`** — logs `blob_path`, which is constructed as `f"{patient_id}/{folder_name}/{filename}"`:
   ```python
   logger.info(f"Read image for {blob_path}. Duration: {time() - start}s")
   ```

3. **`patient_data_routes.py:23`** — logs `blob_path` (starts with `patient_id/...`):
   ```python
   logger.info(f"blob_path: {blob_path}")
   ```

4. **`patient_data_routes.py:40`** — returns `blob_path` in HTTP 404 response body, exposing patient ID to the HTTP client:
   ```python
   return Response(status_code=404, content=f"Blob not found: {blob_path}")
   ```

## Findings

- **Files:** `src/data_models/image_accessor.py:44,69`, `src/routes/patient_data/patient_data_routes.py:23,40`
- **Reported by:** security-sentinel (second review pass)
- **Severity:** P1 — same HIPAA violation class as todos 001–004

## Proposed Solution

**`image_accessor.py`:**
```python
# Line 44 — remove patient_id, keep duration metric:
logger.info("Get image metadata for patient %s. Duration: %.3fs", patient_id, time() - start)

# Line 69 — blob_path contains patient_id; log filename only:
logger.info("Read image for patient. Duration: %.3fs", time() - start)
```

**`patient_data_routes.py`:**
```python
# Line 23 — remove PHI from log:
logger.info("Serving blob request")

# Line 40 — return generic 404, no blob_path in body:
return Response(status_code=404, content="Blob not found.")
```

- **Effort:** Small (4 lines)
- **Risk:** None — log change only; no behavior change for callers

## Acceptance Criteria

- [ ] `image_accessor.py`: `patient_id` and `blob_path` not interpolated in any log statement
- [ ] `patient_data_routes.py`: `blob_path` not interpolated in log or HTTP response
- [ ] All log statements use lazy `%s` formatting, not f-strings
- [ ] No PHI in HTTP error responses

## Work Log

- 2026-04-02: Identified by security-sentinel during re-review of P1 fixes
