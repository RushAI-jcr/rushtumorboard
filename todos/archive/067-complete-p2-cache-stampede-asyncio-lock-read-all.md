---
status: complete
priority: p2
issue_id: "067"
tags: [code-review, performance, asyncio, concurrency, caching, fhir, fabric]
dependencies: []
---

## Problem Statement

`read_all` in `FhirClinicalNoteAccessor` and `FabricClinicalNoteAccessor` uses a check-then-populate pattern without an asyncio lock:

```python
if patient_id in self._note_cache:
    return self._note_cache[patient_id]
# ... multiple awaits (HTTP calls) ...
self._note_cache[patient_id] = notes
```

With 10 Semantic Kernel agents all calling `read_all` concurrently at session start for the same patient, all 10 find the cache empty and all 10 proceed to fetch notes from FHIR/Fabric. For a patient with 60 notes in 6 batches of 10, this results in 600 FHIR DocumentReference reads instead of 60 — a 10x unnecessary load. Results are eventually correct (last write wins), but the waste is significant and could trigger FHIR rate limits.

## Findings

- **File:** `src/data_models/fhir/fhir_clinical_note_accessor.py`, lines 193–215
- **File:** `src/data_models/fabric/fabric_clinical_note_accessor.py`, lines 158–179
- **Reported by:** performance-oracle
- **Severity:** P2 — 10x redundant network I/O under normal 10-agent concurrent access

## Proposed Solutions

### Option A (Recommended): asyncio.Lock per patient

```python
# In __init__:
self._cache_locks: dict[str, asyncio.Lock] = {}

# In read_all:
if patient_id not in self._cache_locks:
    self._cache_locks[patient_id] = asyncio.Lock()
async with self._cache_locks[patient_id]:
    if patient_id in self._note_cache:  # double-check after acquiring lock
        return self._note_cache[patient_id]
    # ... fetch and populate ...
```

### Option B: Accept the stampede at current scale

At current scale (15 patients, 10 agents, 30–100 notes), the stampede produces at most 1,000 redundant FHIR reads per session. If FHIR is not the active backend (Rush uses Caboodle/Epic CSV which does not have this issue), this may be acceptable. Document the known limitation.

### Option C: Global lock for all patients

Simpler but serializes all agent note access:
```python
self._cache_lock = asyncio.Lock()
async with self._cache_lock:
    ...
```

Option A is preferred for production use.

## Technical Details

- **Files:** `fhir_clinical_note_accessor.py:193`, `fabric_clinical_note_accessor.py:158`
- **Note:** `CaboodleFileAccessor` has the same pattern for `_read_file` but is local disk I/O (benign)
- **Note:** The race window requires that context switches happen between the cache check and the populate. In asyncio, this requires an `await` between those two points — which both `read_all` implementations have (multiple `await` calls during HTTP fetch).

## Acceptance Criteria

- [ ] `read_all` in FHIR accessor uses per-patient `asyncio.Lock` to prevent stampede
- [ ] `read_all` in Fabric accessor uses per-patient `asyncio.Lock` to prevent stampede
- [ ] Cache hit path still returns without acquiring lock (fast path unchanged)
- [ ] After fix: 10 concurrent agents produce exactly 1 set of FHIR calls per patient (verified in test)

## Work Log

- 2026-04-02: Identified during performance review. At Rush scale (15 patients, Caboodle backend), this is low-urgency but becomes high-urgency if FHIR backend is used for larger patient populations.
