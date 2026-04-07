---
status: pending
priority: p3
issue_id: "224"
tags: [code-review, performance]
dependencies: []
---

# Performance Micro-Optimizations

## Problem Statement
Several minor performance improvements identified. None are critical but would reduce unnecessary work.

## Findings

1. **JSON re-parsing**: `clinical_note_filter_utils.py:34` — `json.loads(n)` on every note for every `get_clinical_notes_by_type` call. Fabric/FHIR cache notes as JSON strings; parsing happens 400+ times redundantly. Cache parsed dicts instead.

2. **Overlapping tumor marker queries**: `tumor_markers.py:172-176` — `asyncio.gather` runs `get_lab_results` and `get_tumor_markers` concurrently, but both read `lab_results.csv`. If `get_lab_results` succeeds, `get_tumor_markers` was wasted. Make sequential fallback.

3. **Excessive executor calls for file existence**: `caboodle_file_accessor.py:465-468` — two `run_in_executor` for `os.path.exists` (parquet + CSV). `os.path.exists` completes in <1ms on local disk. Combine with read into single executor call.

4. **FHIR token not cached**: `fhir_clinical_note_accessor.py:32-49` — `from_client_secret` acquires new OAuth token per API call. Use Azure SDK's built-in token caching.

## Acceptance Criteria
- [ ] Fabric/FHIR cache parsed dicts, not JSON strings
- [ ] Tumor marker queries use sequential fallback
- [ ] FHIR token provider uses cached credentials
