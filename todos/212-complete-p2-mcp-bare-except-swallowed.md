---
status: pending
priority: p2
issue_id: "212"
tags: [code-review, quality, mcp, error-handling]
dependencies: []
---

# MCP Server Swallows Exceptions and Debug Mode via Env Var

## Problem Statement
Two related issues in `mcp_app.py`:
1. Bare `except Exception` at lines 155-157 and 197-198 logs `logger.error(f"...")` but swallows the full traceback. Use `logger.exception()` instead.
2. Line 207: `debug=os.environ.get("DEBUG", "").lower() in ("1", "true")` — Starlette debug mode exposes full stack traces (including local variables with PHI) in HTTP error responses. Should be hardcoded `False`.

## Findings
- **File**: `src/mcp_app.py`, lines 155-157, 197-198 — swallowed exceptions
- **File**: `src/mcp_app.py`, line 207 — debug mode controllable via env var

## Proposed Solution
1. Replace `logger.error(f"Error: {e}")` with `logger.exception("MCP server error")`
2. Hardcode `debug=False`

- **Effort**: Small (3 lines)

## Acceptance Criteria
- [ ] MCP server exceptions include full traceback in logs
- [ ] Debug mode hardcoded to False
