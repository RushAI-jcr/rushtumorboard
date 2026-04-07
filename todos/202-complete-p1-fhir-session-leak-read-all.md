---
status: pending
priority: p1
issue_id: "202"
tags: [code-review, performance, correctness, fhir]
dependencies: []
---

# FHIR Accessor Session Leak in read_all

## Problem Statement
`FhirClinicalNoteAccessor.read_all()` creates a **new** `aiohttp.ClientSession()` via `async with` on every call instead of using the shared `self._get_session()` method. This bypasses connection reuse, leaks sockets into TIME_WAIT, and is inconsistent with `read()` (which uses the shared session) and the Fabric accessor.

Confirmed by 3 independent review agents (Performance Oracle, Python Reviewer, Architecture Strategist).

## Findings
- **File**: `src/data_models/fhir/fhir_clinical_note_accessor.py`, line 273
- `read_all()` uses `async with aiohttp.ClientSession() as session:` — creates new TCP pool per call
- `read()` at line 254 correctly uses `await self._get_session()` — shared session
- `FabricClinicalNoteAccessor.read_all()` at line 174 correctly uses `await self._get_session()`
- Under concurrent load (multiple patients), this could exhaust OS file descriptors

## Proposed Solutions

### Solution A: Use shared session (Recommended)
Replace line 273 `async with aiohttp.ClientSession() as session:` with `session = await self._get_session()` and remove the `async with` wrapper.

- **Pros**: 1-line fix, matches Fabric accessor pattern
- **Cons**: None
- **Effort**: Small (5 minutes)
- **Risk**: None

## Acceptance Criteria
- [ ] `read_all()` uses `self._get_session()` instead of creating a new session
- [ ] Also add `close()` method to FHIR accessor (matching Fabric pattern)
- [ ] Verify `close()` is called in all entry point shutdown handlers

## Work Log
| Date | Action | Learnings |
|------|--------|-----------|
| 2026-04-06 | Created from code review | Confirmed by 3 agents |
