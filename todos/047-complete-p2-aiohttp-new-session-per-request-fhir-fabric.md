---
name: aiohttp-new-session-per-request-fhir-fabric
description: FHIR and Fabric accessors create a new aiohttp.ClientSession per HTTP request, incurring TCP/TLS overhead for every note fetch in the read_all batch
type: code-review
status: pending
priority: p2
issue_id: 047
tags: [code-review, performance, aiohttp, network]
---

## Problem Statement

`fhir_clinical_note_accessor.py` and `fabric_clinical_note_accessor.py` create a new `aiohttp.ClientSession` per HTTP request — including each individual note fetch inside the `asyncio.gather` batch in `read_all`. Session creation involves TCP connection setup and TLS handshake overhead. For 150 notes in 10-note batches: 150 individual TLS handshakes. At 5-30ms each, this is 750ms-4.5s of pure connection overhead before any data transfers.

## Findings

- `fhir_clinical_note_accessor.py`: new `aiohttp.ClientSession` created per request, including inside `asyncio.gather` batch
- `fabric_clinical_note_accessor.py`: same pattern
- Each `ClientSession` creation triggers TCP connection setup + TLS handshake
- For 150 notes fetched in 10-note batches: 150 separate TLS handshakes
- Estimated overhead: 5-30ms per handshake × 150 = 750ms-4.5s of connection overhead, excluding data transfer time
- `aiohttp` documentation recommends one `ClientSession` per application or per logical operation, not per request

## Proposed Solutions

### Option A
Create one `aiohttp.ClientSession` per accessor instance: instantiate in `__init__`, and expose an `async def close()` method that is called by `DataAccess` when the accessor is torn down. Connection pooling and TLS session reuse apply across all requests made by the accessor instance.

**Pros:** Maximum connection reuse; correct aiohttp usage pattern; eliminates all per-request TLS overhead
**Cons:** Requires `DataAccess` to call `close()` on accessor teardown; session lifecycle must be managed carefully to avoid unclosed session warnings
**Effort:** Small (2-3 hours including DataAccess wiring)
**Risk:** Low-medium (session lifecycle management)

### Option B
Create one `aiohttp.ClientSession` per `read_all` call using a context manager (`async with aiohttp.ClientSession() as session:`) scoped to the outer batch loop. All note fetches within a single `read_all` invocation share one session.

**Pros:** Simpler lifecycle — session is closed automatically when `read_all` returns; no changes to `DataAccess` required
**Cons:** Session is not reused across multiple `read_all` calls (e.g., if called twice in the same agent turn); still creates a new session per `read_all` invocation
**Effort:** Small (1-2 hours)
**Risk:** Low

## Recommended Action

## Technical Details

**Affected files:**
- `src/data_access/fhir_clinical_note_accessor.py`
- `src/data_access/fabric_clinical_note_accessor.py`
- `src/data_access/data_access.py` (if Option A — add `close()` call on teardown)

## Acceptance Criteria

- [ ] Neither FHIR nor Fabric accessor creates a new `aiohttp.ClientSession` per individual HTTP request
- [ ] All note fetches within a `read_all` batch share a single session
- [ ] Session is properly closed (no unclosed session ResourceWarning in tests)
- [ ] Existing accessor tests pass
- [ ] Session reuse verified by confirming connection count does not scale linearly with note count in a profiling test or log

## Work Log

- 2026-04-02: Identified in code review

## Resources

- Branch: fix/accessor-protocol-cache-quality-015-022
