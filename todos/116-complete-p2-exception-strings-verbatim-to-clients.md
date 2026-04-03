---
status: complete
priority: p2
issue_id: "116"
tags: [code-review, security, reliability]
dependencies: []
---

# 116 — Raw `str(e)` exception messages returned verbatim to WebSocket/REST clients

## Problem Statement

Unhandled exceptions are stringified with `str(e)` and returned directly to WebSocket and REST clients in multiple places. Azure SDK exception messages can contain connection strings, storage account URLs, internal service endpoints, and partial patient identifiers. Returning `str(e)` to the browser exposes internal architecture and potentially PHI to any client-side observer (browser DevTools, proxies, logs).

## Findings

- `src/routes/api/chats.py:108` — `str(e)` in REST error response
- `src/routes/api/chats.py:196` — `{"error": str(e)}` in WebSocket error frame
- `src/routes/api/user.py:128` — `str(e)` in REST error response
- `src/mcp_servers/clinical_trials_mcp.py:134` — `str(e)` in MCP tool error return
- `src/mcp_servers/clinical_trials_mcp.py:212` — `str(e)` in MCP tool error return
- `src/mcp_servers/clinical_trials_mcp.py:277` — `str(e)` in MCP tool error return
- `src/mcp_servers/clinical_trials_mcp.py:443` — `str(e)` in MCP tool error return

## Proposed Solution

1. Generate a short correlation ID (e.g., `uuid4().hex[:8]`) at the point of exception.
2. Log the full exception — including traceback and `str(e)` — server-side at ERROR severity with the correlation ID.
3. Return only an opaque message and the correlation ID to the client:

```python
ref = uuid.uuid4().hex[:8]
logger.error("Unhandled exception [ref=%s]: %s", ref, e, exc_info=True)
return {"error": "An internal error occurred.", "reference_id": ref}
```

4. Apply this pattern consistently at all seven locations above. In MCP tool returns, use the MCP error content type rather than a raw dict where appropriate.

## Acceptance Criteria

- [ ] No `str(e)` appears in any HTTP response body, WebSocket frame, or MCP tool error return
- [ ] Full exception including traceback is logged server-side at ERROR severity with a correlation ID
- [ ] Client receives an opaque error message and a `reference_id` for support lookup
- [ ] All seven locations listed in Findings are addressed
