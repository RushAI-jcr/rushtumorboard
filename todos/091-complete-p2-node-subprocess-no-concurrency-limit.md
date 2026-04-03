---
status: complete
priority: p2
issue_id: "091"
tags: [code-review, performance, architecture]
dependencies: []
---

# P2 — No semaphore on Node.js subprocess spawning — concurrency risk under load

## Problem Statement

`asyncio.create_subprocess_exec` spawns a Node.js process per `export_to_pptx` call with no concurrency cap. In a 15-patient batch meeting processed by `scripts/run_batch_e2e.py`, or in multiple simultaneous WebSocket sessions, up to N Node processes can run concurrently. Node + PptxGenJS is CPU-bound during PPTX generation. N simultaneous processes on a shared Azure host will compete for CPU, extend wall times, and prematurely trigger the 60-second `_NODE_TIMEOUT_SECS` guard.

## Findings

**`presentation_export.py`, line 195:** `proc = await asyncio.create_subprocess_exec("node", _JS_SCRIPT, ...)` — no semaphore, no queue, no limit.

Architecture agent: "There is no semaphore, queue, or concurrency cap anywhere in the subprocess path." The primary use case (one interactive session per meeting) is low-risk. The batch mode `run_batch_e2e.py` is the acute risk.

## Proposed Solution

Add a module-level semaphore (not instance-level — it must be shared across all concurrent calls):

```python
# Module level
_NODE_SEMAPHORE = asyncio.Semaphore(max(os.cpu_count() or 2, 2))

# In export_to_pptx, wrap the subprocess block:
async with _NODE_SEMAPHORE:
    proc = await asyncio.create_subprocess_exec(...)
    ...
```

Note: `asyncio.Semaphore` must be created inside a running event loop in Python 3.10+. Create lazily or at first use. Alternatively, initialize in the FastAPI `lifespan` context.

## Acceptance Criteria
- [ ] A module-level or app-level semaphore limits concurrent Node subprocess spawning
- [ ] Semaphore value matches available CPU count or a configurable env var
- [ ] Semaphore is not created at module import time (Python 3.10+ requires event loop context)
