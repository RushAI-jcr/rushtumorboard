---
status: pending
priority: p2
issue_id: "114"
tags: [code-review, performance, reliability, concurrency]
dependencies: []
---

# 114 — NCCN class-level cache has no concurrency lock

## Problem Statement

`NCCNGuidelinesPlugin` uses class-level mutable dicts (`_pages`, `_disease_index`, `_type_index`, `_keyword_index`, `_guidelines`) as shared caches. `_ensure_loaded()` checks `_loaded = False` then calls `_load_guideline` for every JSON file without a lock. Two concurrent first-access requests can both see `_loaded = False`, both load all files, and produce duplicate entries in every index dict. Missing `ClassVar` annotations mean Pyright treats the dicts as instance variables, masking the sharing. Mutable class-level containers without `ClassVar` are also shared with any future subclasses.

## Findings

- `nccn_guidelines.py:37-42` — class-level mutable dict declarations without `ClassVar`
- `nccn_guidelines.py:49-79` — `_ensure_loaded` checks `_loaded` and calls `_load_guideline` with no lock; race window between the `if not cls._loaded` check and the `cls._loaded = True` assignment

## Proposed Solution

1. Add `_load_lock: ClassVar[asyncio.Lock]` initialized at class definition time (not inside a method, to avoid the lock being created inside an event loop).
2. Wrap the `_ensure_loaded` body with double-checked locking:

```python
async def _ensure_loaded(cls) -> None:
    if cls._loaded:
        return
    async with cls._load_lock:
        if cls._loaded:   # second check inside the lock
            return
        for path in cls._guideline_paths:
            await cls._load_guideline(path)
        cls._loaded = True
```

3. Add `ClassVar` annotations to all five class-level containers and `_loaded`.

## Acceptance Criteria

- [ ] `_ensure_loaded` is safe under concurrent access — concurrent callers cannot both enter the load block
- [ ] `ClassVar` annotations added to `_pages`, `_disease_index`, `_type_index`, `_keyword_index`, `_guidelines`, and `_loaded`
- [ ] No duplicate page entries after a concurrent first load (verifiable via unit test with `asyncio.gather`)
- [ ] Pyright reports no errors on the class-level field declarations
