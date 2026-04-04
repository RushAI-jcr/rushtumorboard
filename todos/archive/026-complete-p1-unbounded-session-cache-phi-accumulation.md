---
status: complete
priority: p1
issue_id: "016"
tags: [code-review, security, hipaa, phi, cache, memory]
dependencies: []
---

## Problem Statement

`CaboodleFileAccessor._cache` is an unbounded `dict[tuple[str, str], list[dict]]` that accumulates every CSV file ever read for every patient during the process lifetime. In a long-running FastAPI server handling multiple tumor board sessions in sequence, the cache grows indefinitely: each patient's full clinical notes, pathology, radiology, lab, and medication data all remain in heap memory.

This creates two risks:
1. **HIPAA**: Patient A's clinical data is still in memory when Patient B's session begins, violating the minimal-necessary access principle
2. **Memory**: 15+ patients × 7 file types × up to 80 KB/file = potentially >8 MB uncompressed, growing without bound across a server's lifetime

## Findings

- **File:** `src/data_models/epic/caboodle_file_accessor.py` lines 69, 260–270
- **Reported by:** security-sentinel, performance-oracle
- **Severity:** P1 — unbounded PHI accumulation in heap; HIPAA minimization concern

## Proposed Solutions

### Option A (Recommended): Session-scoped accessor (preferred architectural fix)
Instantiate `CaboodleFileAccessor` per-request/per-session rather than as a process-level singleton. The cache then lives only for the duration of one tumor board session and is GC'd when the session ends.
```python
# In data_access.py factory — create new accessor per session, not once at startup
def create_accessor(session_id: str) -> CaboodleFileAccessor:
    return CaboodleFileAccessor()  # fresh cache per session
```
- **Pros:** Correct architectural scope; HIPAA minimization; no cache size limits needed; simplest
- **Cons:** Requires confirming accessor is not currently a singleton in DI container
- **Effort:** Small (verify scope) to Medium (refactor if singleton)
- **Risk:** Low

### Option B: LRU cache with TTL
Replace `dict` with `functools.lru_cache` or a manual LRU (e.g., `cachetools.TTLCache`):
```python
from cachetools import TTLCache
self._cache: TTLCache = TTLCache(maxsize=100, ttl=3600)  # 1h TTL, 100 entries max
```
- **Pros:** Bounds memory; auto-expires PHI; minimal refactor
- **Cons:** Adds `cachetools` dependency; TTL is a guess; doesn't fully solve minimization
- **Effort:** Small
- **Risk:** Low

### Option C: Clear cache after session
Add `clear_cache()` method and call it when a tumor board session ends.
- **Pros:** No dependency; surgical
- **Cons:** Requires session lifecycle hooks that don't currently exist
- **Effort:** Medium

## Recommended Action

Option A — verify accessor scope first. If it's already per-session (instantiated in group_chat.py per run), the cache is already bounded and this is low risk. If it's a singleton, refactor to per-session.

## Technical Details

- **Affected files:** `src/data_models/epic/caboodle_file_accessor.py:69` (`_cache = {}`)
- **Cache key:** `(patient_id, file_type)` — grows one entry per patient per file type
- **File types cached:** clinical_notes, pathology_reports, radiology_reports, lab_results, cancer_staging, medications, diagnoses (7 per patient)

## Acceptance Criteria

- [ ] Accessor lifetime verified in `group_chat.py` / `data_access.py`
- [ ] Either: accessor is confirmed per-session (cache bounded by design), OR LRU/TTL cap is applied
- [ ] No test processes multiple patients in sequence with the same accessor instance without cache reset

## Work Log

- 2026-04-02: Identified by security-sentinel and performance-oracle during code review
- 2026-04-02: Resolved — _CACHE_MAX_PATIENTS=5 LRU eviction confirmed in caboodle_file_accessor.py.
