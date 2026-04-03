---
status: pending
priority: p3
issue_id: "136"
tags: [code-review, performance, memory]
dependencies: []
---

# 136 — `_read_locks` dicts grow unboundedly in FHIR and Fabric accessors

## Problem Statement

`FhirClinicalNoteAccessor._read_locks` and `FabricClinicalNoteAccessor._read_locks` are plain dicts mapping `patient_id -> asyncio.Lock`. Entries are created on demand when a patient ID is first encountered and are never removed. The lock only serves a purpose during the initial cache-population window — once the cache entry is set, the lock object is retained indefinitely. In a long-running server processing many distinct patients over its lifetime, this constitutes a slow unbounded memory leak: one `asyncio.Lock` object per historical patient ID, forever.

## Findings

- `fhir_clinical_note_accessor.py:65` — `_read_locks: dict[str, asyncio.Lock] = {}`
- `fhir_clinical_note_accessor.py:219-222` — lock creation and acquisition
- `fabric_clinical_note_accessor.py:41` — `_read_locks: dict[str, asyncio.Lock] = {}`
- `fabric_clinical_note_accessor.py:162-165` — lock creation and acquisition

## Proposed Solution

Option A — Delete after use: after the lock is released and the cache entry is confirmed populated, delete the entry:

```python
async with self._read_locks[patient_id]:
    if patient_id not in self._cache:
        self._cache[patient_id] = await self._fetch(patient_id)
del self._read_locks[patient_id]
```

Option B — `WeakValueDictionary`: replace the plain dict with `weakref.WeakValueDictionary` so lock objects are garbage-collected automatically when no coroutine holds a reference.

Option A is simpler and recommended. Apply the same fix in both `FhirClinicalNoteAccessor` and `FabricClinicalNoteAccessor`.

## Acceptance Criteria

- [ ] `_read_locks` entries are cleaned up after cache population completes
- [ ] A long-running server processing N distinct patients does not accumulate N lock objects
- [ ] Fix applied in both `fhir_clinical_note_accessor.py` and `fabric_clinical_note_accessor.py`
- [ ] No regression: concurrent requests for the same patient still serialize correctly during initial fetch
