---
status: pending
priority: p1
issue_id: "204"
tags: [code-review, security, hipaa, mcp, phi]
dependencies: []
---

# MCP Logs PHI and Bearer Tokens (HIPAA Violation)

## Problem Statement
`mcp_app.py` logs full HTTP request headers (including `Authorization: Bearer` tokens) and user message content (which contains patient identifiers and clinical data) at INFO level. In production with Azure Monitor, this persists PHI and credentials in Application Insights — a HIPAA violation and token replay risk.

## Findings
- **File**: `src/mcp_app.py`, line 120: `logger.info(f"Request headers: {request.headers}")` — logs ALL headers including bearer tokens
- **File**: `src/mcp_app.py`, lines 61, 66: `logger.info(f"Processing chat with question: {message}...")` — logs full user message with PHI
- Related: Prior P1 fix (TODO #200) addressed similar PHI-in-logs in `ChatArtifactAccessor` — this is the same pattern in MCP

## Proposed Solutions

### Solution A: Remove/redact sensitive logging (Recommended)
1. Remove line 120 (header logging) entirely
2. Replace lines 61, 66 with: `logger.info("Processing chat (len=%d) for agent %s", len(message), agent_name)`

- **Pros**: Direct fix, 3 lines changed
- **Cons**: Reduces debug visibility
- **Effort**: Small (5 minutes)
- **Risk**: None

## Acceptance Criteria
- [ ] No bearer tokens logged at any level
- [ ] No user message content logged at any level
- [ ] Log only message length and agent name for debugging
- [ ] Grep confirms no f-string logging with `message` variable in mcp_app.py

## Work Log
| Date | Action | Learnings |
|------|--------|-----------|
| 2026-04-06 | Created from security review | Matches prior TODO #200 pattern |
