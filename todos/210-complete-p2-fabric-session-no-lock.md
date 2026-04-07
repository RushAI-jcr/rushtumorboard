---
status: pending
priority: p2
issue_id: "210"
tags: [code-review, architecture, fabric, concurrency]
dependencies: []
---

# Fabric Accessor _get_session() Lacks asyncio.Lock

## Problem Statement
`FabricClinicalNoteAccessor._get_session()` lazily creates an `aiohttp.ClientSession` without a lock. Under concurrent requests, multiple sessions can be created — only one is kept, others leak. The FHIR accessor correctly uses `self._session_lock`. Also, per-patient lock creation in both accessors has a race condition.

## Findings
- **File**: `src/data_models/fabric/fabric_clinical_note_accessor.py`, lines 87-91 — no lock
- **File**: `src/data_models/fhir/fhir_clinical_note_accessor.py`, lines 90-91 — has lock (correct)
- Per-patient lock race: `self._read_locks[patient_id] = asyncio.Lock()` — use `setdefault()` instead
  - Fabric: line 164
  - FHIR: line 262-263

## Proposed Solution
1. Add `self._session_lock = asyncio.Lock()` to Fabric `__init__`
2. Wrap `_get_session()` body in `async with self._session_lock:`
3. Replace lock creation with `self._read_locks.setdefault(patient_id, asyncio.Lock())`

- **Effort**: Small (10 lines)

## Acceptance Criteria
- [ ] Fabric `_get_session()` protected by asyncio.Lock
- [ ] Per-patient locks use `setdefault()` in both Fabric and FHIR accessors
