---
status: complete
priority: p3
issue_id: "146"
tags: [code-review, architecture, reliability]
dependencies: []
---

# 146 — MCP server global HTTP session has race condition, no shutdown handler, unsafe cleanup tool

## Problem Statement

`clinical_trials_mcp.py:79-88` maintains a module-level `_http_session` global for the `aiohttp.ClientSession`. Three distinct problems exist:

1. **Race condition on creation:** Two concurrent requests that both observe `_http_session is None` will both execute `_http_session = aiohttp.ClientSession()`. The first session is orphaned — it is overwritten by the second and its underlying connections are never closed.

2. **No shutdown handler:** There is no FastAPI lifespan or `shutdown` event handler to close `_http_session` when the application exits. The session and its underlying connections are leaked on every restart.

3. **Unsafe `cleanup` MCP tool:** The `cleanup` tool can be called at any time, including while other coroutines are mid-flight using the session. Closing the session mid-request causes `aiohttp.ClientConnectionError` for in-flight requests with no recovery path.

## Findings

- `src/mcp_servers/clinical_trials_mcp.py:79-88` — `_http_session` global creation, `cleanup` tool

## Proposed Solution

**(A)** Guard session creation with a module-level `asyncio.Lock`:

```python
_session_lock = asyncio.Lock()

async def _get_session() -> aiohttp.ClientSession:
    global _http_session
    if _http_session is None:
        async with _session_lock:
            if _http_session is None:
                _http_session = aiohttp.ClientSession()
    return _http_session
```

**(B)** Register a FastAPI shutdown handler in the MCP server's lifespan to close the session on graceful shutdown.

**(C)** Remove the `cleanup` MCP tool, or guard it so it can only be called when no requests are in flight (e.g., by tracking in-flight request count with an `asyncio.Semaphore`).

## Acceptance Criteria

- [ ] Session creation is race-free under concurrent first requests (double-checked locking pattern)
- [ ] Application graceful shutdown closes the `aiohttp.ClientSession`
- [ ] No orphaned session objects on concurrent first access
- [ ] In-flight requests are not disrupted by a concurrent `cleanup` call
