---
status: pending
priority: p1
issue_id: "207"
tags: [code-review, agent-native, mcp, data-access]
dependencies: []
---

# MCP Path Never Sets request_date on ChatContext

## Problem Statement
The WebSocket path sets `chat_context.request_date = datetime.now().strftime("%Y-%m-%d")` and the Teams bot sets it from the activity timestamp. The MCP path reads the chat context and immediately processes the message without ever setting `request_date`. This drives per-file-type date windows (notes=90d, labs=1yr) — without it, data filtering may return incorrect results.

## Findings
- **File**: `src/mcp_app.py`, lines 63-64 — no `request_date` assignment
- **File**: `src/routes/api/chats.py`, line 138 — WebSocket sets it correctly
- **File**: `src/bots/assistant_bot.py`, line 62 — Teams bot sets it correctly
- `CaboodleFileAccessor._reference_date` used for lookback windows depends on this

## Proposed Solutions

### Solution A: Set request_date in process_chat (Recommended)
Add one line after reading chat context:
```python
if not chat_ctx.request_date:
    chat_ctx.request_date = datetime.now().strftime("%Y-%m-%d")
```

- **Pros**: 2-line fix, matches WebSocket/Teams behavior
- **Cons**: None
- **Effort**: Small (5 minutes)
- **Risk**: None

## Acceptance Criteria
- [ ] `request_date` is set in MCP path before agents run
- [ ] Date window filtering works correctly via MCP

## Work Log
| Date | Action | Learnings |
|------|--------|-----------|
| 2026-04-06 | Created from agent-native review | 2-line fix |
