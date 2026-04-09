---
status: pending
priority: p2
issue_id: "231"
tags: [code-review, concurrency]
dependencies: []
---

# Add asyncio.Lock to Lazy MRN Index Initialization

## Problem Statement

`resolve_patient_id` lazily builds the MRN index on first call. If two concurrent requests trigger resolution simultaneously, `_build_mrn_index_sync` runs twice — wasting I/O and potentially producing inconsistent results if patient folders are being modified.

## Findings

**Flagged by:** Security Sentinel (MEDIUM)

**File:** `src/data_models/epic/caboodle_file_accessor.py`

```python
if self._mrn_index is None:
    self._mrn_index = self._build_mrn_index_sync()
```

No lock protects this check-then-act sequence.

## Proposed Solutions

### Option A: asyncio.Lock (Recommended)
```python
_mrn_index_lock: asyncio.Lock  # initialized in __init__

async def resolve_patient_id(self, identifier: str) -> str:
    ...
    if self._mrn_index is None:
        async with self._mrn_index_lock:
            if self._mrn_index is None:  # double-check
                self._mrn_index = self._build_mrn_index_sync()
    ...
```
- Effort: Small | Risk: None

## Acceptance Criteria

- [ ] asyncio.Lock guards lazy initialization
- [ ] Double-check pattern prevents redundant builds
- [ ] Lock initialized in __init__

## Work Log

- 2026-04-09: Created from Phase 2 code review (Security Sentinel)
