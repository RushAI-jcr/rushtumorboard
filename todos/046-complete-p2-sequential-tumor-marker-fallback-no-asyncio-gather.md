---
name: sequential-tumor-marker-fallback-no-asyncio-gather
description: Tumor marker retrieval awaits two data sources sequentially instead of using asyncio.gather, wasting round-trip latency when stubs are replaced with real API calls
type: code-review
status: pending
priority: p2
issue_id: 046
tags: [code-review, performance, async, asyncio]
---

## Problem Statement

`tumor_markers.py:145-153`: `get_tumor_marker_trend` awaits `get_lab_results` then only dispatches `get_tumor_markers` if the first returns empty — sequential. `tumor_markers.py:229-231`: `get_all_tumor_markers` has the same serial pattern in reverse order. On `CaboodleFileAccessor` both calls read `lab_results.csv` and the second hits cache. On FHIR/Fabric both return `[]` (stubs). When stubs are replaced with real API calls, this serial pattern wastes the full round-trip latency of the second call every time the first returns non-empty. Additionally, two kernel functions `get_tumor_marker_trend` and `get_all_tumor_markers` called in the same agent turn on FHIR/Fabric each trigger the full `_get_marker_notes_fallback` → `read_all` chain independently with no shared cache.

## Findings

- `tumor_markers.py:145-153`: `get_tumor_marker_trend` sequential await pattern — dispatches `get_tumor_markers` only if `get_lab_results` returns empty
- `tumor_markers.py:229-231`: `get_all_tumor_markers` same serial pattern in reverse order
- On `CaboodleFileAccessor`: second call hits CSV cache, so latency impact is minimal today
- On FHIR/Fabric: both sources currently return `[]` (stubs), masking the latency issue
- When stubs are replaced with real FHIR/Fabric API calls, serial pattern adds one full network round-trip per invocation (potentially 100-500ms)
- Both kernel functions called in the same agent turn independently trigger `_get_marker_notes_fallback` → `read_all` with no shared result cache

## Proposed Solutions

### Option A
Replace the sequential conditional dispatch with `asyncio.gather(accessor.get_lab_results(...), accessor.get_tumor_markers(...))`, then use whichever result is non-empty. Both data sources are fetched concurrently regardless of whether the first returns data.

**Pros:** Eliminates serial latency when both sources are live API calls; correct behavior for FHIR/Fabric once stubs are implemented; minimal code change
**Cons:** Fetches both sources even when the first returns data (minor over-fetching); requires care to handle the case where both return non-empty
**Effort:** Small (1-2 hours)
**Risk:** Low

### Option B
Add a fallback log message before the `_get_marker_notes_fallback` call to provide operator visibility into when the fallback chain is triggered. This is a separate, easier improvement that can be done independently of the async gather change.

**Pros:** Immediate observability improvement; zero risk; independent of Option A
**Cons:** Does not address the latency issue
**Effort:** Trivial (< 15 minutes)
**Risk:** None

## Recommended Action

## Technical Details

**Affected files:**
- `src/plugins/tumor_markers.py` (lines 145-153, 229-231)

## Acceptance Criteria

- [ ] `get_tumor_marker_trend` uses `asyncio.gather` to fetch `get_lab_results` and `get_tumor_markers` concurrently
- [ ] `get_all_tumor_markers` uses the same concurrent pattern
- [ ] Result selection logic correctly handles the case where both sources return data
- [ ] Log message added before `_get_marker_notes_fallback` indicating fallback is being triggered
- [ ] Existing tumor marker tests pass

## Work Log

- 2026-04-02: Identified in code review

## Resources

- Branch: fix/accessor-protocol-cache-quality-015-022
