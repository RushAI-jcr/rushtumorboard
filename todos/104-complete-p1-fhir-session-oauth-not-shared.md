---
status: pending
priority: p1
issue_id: "104"
tags: [code-review, performance, fhir, http-session]
dependencies: []
---

# 104 — FHIR Accessor: Unshared Sessions, Per-Request OAuth, and Async Race in Lazy Init

## Problem Statement

`FhirClinicalNoteAccessor` has three distinct session management failures that together cause excessive TCP connections, redundant OAuth round-trips, and a latent concurrency bug that can produce orphaned sessions:

**A — `fetch_all_entries` creates its own `ClientSession`**, bypassing the shared `_session` field. This opens a new connection pool for every call and is never explicitly closed, leaking file descriptors.

**B — `read()` (single-note method)** opens `async with aiohttp.ClientSession()` at lines 210–212, uses it for one request, and immediately destroys it. `read_all()` correctly reuses the shared session; `read()` does not. Any code path that calls `read()` per-note creates O(n) ClientSession objects.

**C — `bearer_token_provider` closure** uses `aiohttp.request(...)` (the module-level convenience function, which creates a new internal session per call) on every single invocation, with no token caching and no timeout. For a patient with 100 clinical notes, this produces 100 separate OAuth round-trips to the token endpoint — in addition to the 100 FHIR API calls.

**D — `_get_session()` lazy init** at lines 87–89 has an async race: if two coroutines concurrently observe `self._session is None`, both will construct a `ClientSession`. The first session created is leaked (orphaned) because the second assignment overwrites the reference.

## Findings

- `fhir_clinical_note_accessor.py:43-47` — `bearer_token_provider` uses `aiohttp.request(...)` with no TTL cache and no timeout parameter.
- `fhir_clinical_note_accessor.py:87-89` — `_get_session()` lacks an `asyncio.Lock` guard; susceptible to concurrent double-init.
- `fhir_clinical_note_accessor.py:105` — `fetch_all_entries` creates `aiohttp.ClientSession()` inline, independent of `self._session`.
- `fhir_clinical_note_accessor.py:210-212` — `read()` opens a fresh `ClientSession` per call instead of calling `_get_session()`.

## Proposed Solution

**A — Pass shared session to `fetch_all_entries`:**

```python
async def fetch_all_entries(self, url: str) -> list[dict]:
    session = await self._get_session()
    async with session.get(url, headers=...) as resp:
        ...
```

**B — Align `read()` to use `_get_session()`:**

```python
async def read(self, note_id: str) -> dict:
    session = await self._get_session()
    async with session.get(f"{self.base_url}/{note_id}", headers=...) as resp:
        ...
```

**C — Cache the bearer token with TTL:**

```python
_token_cache: dict[str, tuple[str, float]] = {}  # key → (token, expiry_epoch)
_TOKEN_TTL = 3540  # 59 minutes; refresh 60s before expiry

async def _get_bearer_token(self) -> str:
    cached = _token_cache.get(self._cache_key)
    if cached and time.monotonic() < cached[1]:
        return cached[0]
    token = await _fetch_token_from_endpoint(...)
    _token_cache[self._cache_key] = (token, time.monotonic() + _TOKEN_TTL)
    return token
```

**D — Guard `_get_session()` with `asyncio.Lock`:**

```python
_session_lock: asyncio.Lock = asyncio.Lock()

async def _get_session(self) -> aiohttp.ClientSession:
    async with self._session_lock:
        if self._session is None:
            self._session = aiohttp.ClientSession(...)
    return self._session
```

## Acceptance Criteria

- [ ] `fetch_all_entries` uses the shared `_session` (via `_get_session()`), not a locally-created `ClientSession`
- [ ] `read()` uses `_get_session()` consistently with `read_all()`
- [ ] Bearer token is cached with a TTL of ~3540s; a new token is fetched only when within 60s of expiry or absent
- [ ] `_get_session()` is guarded by an `asyncio.Lock` to prevent concurrent double-initialization
- [ ] A test verifies that 10 concurrent `read()` calls result in exactly one `ClientSession` being created and one OAuth token fetch
