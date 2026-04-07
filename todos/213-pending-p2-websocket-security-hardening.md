---
status: pending
priority: p2
issue_id: "213"
tags: [code-review, security, websocket]
dependencies: []
---

# WebSocket Lacks Message Size Limits and Ownership Check

## Problem Statement
Two related WebSocket security gaps:
1. No message size limit — `websocket.receive_json()` accepts arbitrarily large payloads, risking memory exhaustion and LLM API quota abuse.
2. No chat_id ownership check — `chat_id` is not bound to `principal_id`. Any authenticated user can access any conversation by guessing/enumerating chat IDs (horizontal privilege escalation).

## Findings
- **File**: `src/routes/api/chats.py`, lines 112-207
- Line 127: `websocket.receive_json()` — no size limit
- Line 136: `data_access.chat_context_accessor.read(chat_id)` — no ownership verification
- No rate limiting per connection

## Proposed Solutions
1. Add message size limit: reject messages over 10KB
2. Bind chat_id to principal_id in ChatContext, verify on access
3. Add rate limiting per connection

- **Effort**: Medium (~30 lines)

## Acceptance Criteria
- [ ] Messages over 10KB rejected with error
- [ ] chat_id bound to authenticated user, cross-user access prevented
- [ ] Rate limiting in place (e.g., max 10 messages/minute)
