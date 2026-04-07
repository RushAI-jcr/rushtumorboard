---
status: pending
priority: p1
issue_id: "203"
tags: [code-review, security, hipaa, mcp]
dependencies: []
---

# MCP Endpoint Has No Authentication

## Problem Statement
The MCP endpoint mounted at `/mcp` has **no authentication**. Unlike the WebSocket endpoint (checks `X-MS-CLIENT-PRINCIPAL-ID`) and the Teams bot (uses `AccessControlMiddleware`), the MCP handler accepts any connection. Any caller with network access can create sessions, invoke agent tools (including tools that read patient PHI), and reset conversations.

## Findings
- **File**: `src/mcp_app.py`, lines 117-164
- **File**: `src/app.py`, line 159 (mount point)
- Session ID auto-generated from `token_hex(16)` if not provided (line 124-125)
- `handle_clinical_trials_http` at `/mcp/clinical-trials/` is similarly unauthenticated
- No authentication middleware applied to the MCP Starlette app

## Proposed Solutions

### Solution A: Add bearer token / header auth middleware (Recommended)
Add ASGI middleware to the MCP Starlette app that validates `Authorization: Bearer <token>` or `X-MS-CLIENT-PRINCIPAL-ID` header before processing requests.

- **Pros**: Consistent with other endpoints, straightforward
- **Cons**: Requires Copilot Studio to pass credentials
- **Effort**: Medium (~30 lines)
- **Risk**: Low

### Solution B: Network-level isolation
Deploy MCP endpoint on internal network only, rely on network boundary.

- **Pros**: No code change
- **Cons**: Defense-in-depth violation, single failure point
- **Effort**: Infra config
- **Risk**: Medium

## Acceptance Criteria
- [ ] MCP endpoints require authentication before processing requests
- [ ] Unauthenticated requests receive 401 response
- [ ] Authentication method documented in deployment guide

## Work Log
| Date | Action | Learnings |
|------|--------|-----------|
| 2026-04-06 | Created from security review | Production blocker |
