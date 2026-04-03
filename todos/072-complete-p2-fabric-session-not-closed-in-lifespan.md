---
status: pending
priority: p2
issue_id: "072"
tags: [code-review, resource-management, aiohttp, lifecycle, fabric, asgi]
dependencies: []
---

## Problem Statement

`FabricClinicalNoteAccessor` has a `close()` coroutine that closes the shared `aiohttp.ClientSession`, but nothing in the application lifecycle calls it. The accessor is created at app startup in `create_data_access()` (via `data_access.py`) and held by `AppContext` for the process lifetime. On clean shutdown, the session is closed by garbage collection (aiohttp emits `ResourceWarning: Unclosed client session` in test output). On `KeyboardInterrupt` or signal-based shutdown in production, the session may not drain in-flight requests gracefully.

This causes:
1. `ResourceWarning` in test output (failing CI if warnings-as-errors is configured)
2. Possible in-flight request abandonment on process shutdown
3. Inconsistency: FHIR uses `async with aiohttp.ClientSession()` (guaranteed cleanup); Fabric uses a long-lived session with manual teardown

## Findings

- **File:** `src/data_models/fabric/fabric_clinical_note_accessor.py`, `close()` method (lines 90–94)
- **File:** `src/app.py` — no shutdown hook calling `close()`
- **Reported by:** security-sentinel, performance-oracle, architecture-strategist
- **Severity:** P2 — resource leak in tests; graceful shutdown not guaranteed in production

## Proposed Solutions

### Option A (Recommended): Register in FastAPI lifespan

In `app.py` or `create_fast_mcp_app`, add to the existing `lifespan` context manager:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # Cleanup
    if isinstance(app_context.data_access.clinical_note_accessor, FabricClinicalNoteAccessor):
        await app_context.data_access.clinical_note_accessor.close()
```

### Option B: Add `__aenter__`/`__aexit__` to FabricClinicalNoteAccessor

Makes the accessor a context manager so callers get guaranteed cleanup:
```python
async def __aenter__(self):
    return self

async def __aexit__(self, *args):
    await self.close()
```

Then in `create_data_access`, use `async with FabricClinicalNoteAccessor(...) as accessor:`.

### Option C: Standardize on per-call sessions (remove lazy session)

Switch Fabric to use `async with aiohttp.ClientSession()` per method call, matching FHIR. Given the LRU note cache, `read_all` is called at most once per patient, so the per-call session cost is paid once per patient per session. Simpler but slightly higher overhead.

## Technical Details

- **File:** `src/data_models/fabric/fabric_clinical_note_accessor.py:90`
- **File:** `src/app.py` (lifespan registration point)

## Acceptance Criteria

- [ ] `FabricClinicalNoteAccessor.close()` is called on application shutdown
- [ ] No `ResourceWarning: Unclosed client session` in test output
- [ ] Shutdown does not abandon in-flight requests (session waits for pending requests)

## Work Log

- 2026-04-02: Identified during review. The `close()` method was correctly added in this PR but lifecycle registration was missed.
