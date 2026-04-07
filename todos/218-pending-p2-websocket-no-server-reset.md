---
status: pending
priority: p2
issue_id: "218"
tags: [code-review, agent-native, websocket]
dependencies: []
---

# WebSocket Has No Server-Side Conversation Reset

## Problem Statement
The MCP path has `reset_conversation()` which archives chat context and artifacts. The Teams bot recognizes "clear" suffix. The WebSocket path has no equivalent — `deleteChat` in React only removes from client-side Redux. Server-side context and artifacts persist indefinitely. The SET-ONCE `patient_id` means a user who "deletes" and recreates a chat for a different patient gets a ValueError.

## Findings
- **File**: `src/routes/api/chats.py` — no reset/delete endpoint
- **File**: `src/mcp_app.py`, lines 106-113 — MCP has `reset_conversation()`
- **File**: `src/bots/assistant_bot.py`, line 65 — Teams has "clear" suffix

## Proposed Solution
Add `DELETE /api/chats/{chat_id}` or `POST /api/chats/{chat_id}/reset` that archives context and artifacts.

- **Effort**: Small (~15 lines)

## Acceptance Criteria
- [ ] Server-side endpoint to reset/archive conversation
- [ ] React frontend calls it on chat deletion
- [ ] Orphaned artifacts cleaned up
