---
status: pending
priority: p2
issue_id: "068"
tags: [code-review, performance, fhir, caching, network]
dependencies: []
---

## Problem Statement

`FhirClinicalNoteAccessor.get_metadata_list` calls `get_patient_id_map()` which calls `fetch_all_entries("/Patient")` — fetching all patients from the FHIR server — before it can look up a single patient's notes. This `/Patient` list is static within a session and changes only when patients are added to the system.

With 10 concurrent agents calling `get_metadata_list` for the same patient, each call makes an independent `/Patient` fetch. On a FHIR server with 100+ patients and pagination, each fetch takes 200–500ms. Under 10-agent concurrency, this is 10 simultaneous `/Patient` fetches — likely to trigger FHIR rate limits and definitely adding 200–500ms of unnecessary latency per call.

Additionally, `get_metadata_list` and `get_patient_id_map` each create their own `aiohttp.ClientSession`, meaning 2 sessions are created per `get_metadata_list` call (one for `/Patient`, one for `/DocumentReference`), while `read_all` creates a third session for the actual reads.

## Findings

- **File:** `src/data_models/fhir/fhir_clinical_note_accessor.py`, lines 146–174
- **Reported by:** performance-oracle
- **Severity:** P2 — redundant 200–500ms network call per agent per patient; potential FHIR rate limiting under concurrent load

## Proposed Solutions

### Option A (Recommended): Cache _patient_id_map with asyncio.Lock

```python
# In __init__:
self._patient_id_map: dict[str, str] | None = None
self._patient_id_map_lock: asyncio.Lock = asyncio.Lock()

# New method:
async def _get_patient_id_map(self) -> dict[str, str]:
    if self._patient_id_map is not None:
        return self._patient_id_map
    async with self._patient_id_map_lock:
        if self._patient_id_map is not None:
            return self._patient_id_map
        self._patient_id_map = await self.get_patient_id_map()
        return self._patient_id_map
```

Then replace `await self.get_patient_id_map()` in `get_metadata_list` with `await self._get_patient_id_map()`.

### Option B: TTL-based cache (30 min)

Use `time.monotonic()` to expire the cache after 30 minutes, appropriate for a tumor board session lifetime.

## Technical Details

- **File:** `src/data_models/fhir/fhir_clinical_note_accessor.py:146`
- **Method:** `get_metadata_list` calls `get_patient_id_map` on every invocation

## Acceptance Criteria

- [ ] `_patient_id_map` is fetched at most once per accessor instance lifetime (or TTL)
- [ ] Concurrent callers during first fetch wait on the lock, not issue duplicate requests
- [ ] Cache is invalidated appropriately (session restart or TTL)

## Work Log

- 2026-04-02: Identified during performance review.
