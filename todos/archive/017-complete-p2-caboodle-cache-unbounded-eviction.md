---
name: CaboodleFileAccessor session cache has no eviction bound
description: _cache grows unbounded for the process lifetime — in production with many concurrent sessions this will cause OOM kills
type: performance
status: complete
priority: p2
issue_id: "017"
tags: [performance, memory, code-review]
---

## Problem Statement

`CaboodleFileAccessor._cache: dict[tuple[str, str], list[dict]] = {}` accumulates entries for every `(patient_id, file_type)` pair accessed during the process lifetime, with no eviction.

**Scale math:**
- 15 real patients × 7 file types × ~50 rows average × ~2 KB/row ≈ **10 MB** in the current dataset (fine)
- 100 patients/day × 7 file types × 2 KB = **1.4 MB/day**, or **42 MB/month** of accumulated cache that never flushes
- At production scale with gunicorn workers serving 20–30 concurrent tumor board sessions, each worker accumulates its own copy: 4 workers × 42 MB/month = **168 MB/month growth rate**

The comment "Safe in asyncio (single-threaded); benign double-read race acceptable" is correct for concurrency but doesn't address memory growth.

**Additional issue found by performance review:**
`CaboodleFileAccessor.read()` (single-note lookup) does a linear scan through all file types calling `_read_file` for each, then iterates all rows to find the matching `note_id`. This is O(n) per call. If the `PatientHistory` agent reads N notes individually (e.g., to resolve source citations), the total cost is O(n²). An ID index built during `_read_file` would make lookups O(1).

**Affected file:** `src/data_models/epic/caboodle_file_accessor.py`

## Proposed Solutions

### Option A: functools.lru_cache on _read_file_sync with maxsize (Recommended for now)
Replace the manual dict cache with `@functools.lru_cache(maxsize=210)` (30 patients × 7 file types) on the sync helper. LRU evicts least-recently-used entries automatically.

```python
import functools

@functools.lru_cache(maxsize=210)
def _read_csv_sync_cached(self, filepath: str, patient_id: str) -> tuple[dict, ...]:
    # returns tuple (hashable) for lru_cache compatibility
    ...
```

**Note:** `lru_cache` requires hashable arguments and doesn't work directly on methods (use `functools.lru_cache` on a module-level function or use `cachetools.LRUCache`).

### Option B: cachetools.LRUCache with explicit maxsize
```python
from cachetools import LRUCache
self._cache: LRUCache[tuple[str, str], list[dict]] = LRUCache(maxsize=210)
```
Drop-in replacement for the dict with automatic LRU eviction. Requires adding `cachetools` to requirements.txt.

**Pros:** Simple 2-line change, explicit maxsize, thread-safe (not needed for asyncio but good practice)
**Cons:** New dependency

### Option C: Accept current behavior (defer)
Current dataset has 15 patients; production will have hundreds over months. Acceptable to defer until monitoring shows memory pressure.

**Effort:** Small (Option B) or Medium (Option A with refactor)

## Acceptance Criteria
- [ ] Cache has a documented upper bound on memory usage
- [ ] No single worker can accumulate unbounded patient data over process lifetime
- [ ] Existing tests pass with bounded cache

## Work Log
- 2026-04-02: Identified by performance-oracle during code review. Cache was intentional for session-level deduplication but lacks eviction. Pre-existing issue made more visible by the 3-layer fallback work.
- 2026-04-02: Implemented and marked complete.
