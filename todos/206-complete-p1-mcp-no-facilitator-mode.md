---
status: pending
priority: p1
issue_id: "206"
tags: [code-review, agent-native, mcp, orchestration]
dependencies: []
---

# MCP Cannot Trigger Facilitator-Mode Orchestration

## Problem Statement
The MCP path exposes each agent as a separate tool and always calls `chat.invoke(agent=agent)` with a specific agent. In contrast, the WebSocket path sets `target_agent = None` when the Orchestrator is the target, triggering the full multi-agent turn-taking workflow. An MCP consumer (Copilot Studio) cannot run the core tumor board workflow end-to-end in a single call.

## Findings
- **File**: `src/mcp_app.py`, lines 60-104 — always passes specific `agent` to `chat.invoke()`
- **File**: `src/routes/api/chats.py`, line 163 — sets `target_agent = None` for facilitator mode
- Calling the "Orchestrator" MCP tool passes `agent=Orchestrator` directly — Orchestrator responds alone, cannot delegate
- This is the application's primary use case: "prepare tumor board for patient X"

## Proposed Solutions

### Solution A: Detect facilitator and pass agent=None (Recommended)
In `process_chat`, check if `agent_name` matches the facilitator and set `agent=None`:
```python
if agent.name == facilitator:
    agent = None  # Trigger full multi-agent orchestration
```

- **Pros**: 3-line fix, mirrors WebSocket behavior
- **Cons**: None
- **Effort**: Small (10 minutes)
- **Risk**: Low

### Solution B: Add dedicated `run_tumor_board` MCP tool
Add a separate tool that accepts a message and runs the full pipeline.

- **Pros**: More explicit API contract
- **Cons**: Duplicates the facilitator concept
- **Effort**: Small-Medium
- **Risk**: Low

## Acceptance Criteria
- [ ] MCP consumer can trigger full multi-agent workflow with single tool call
- [ ] Agents take turns (PatientHistory, Pathology, Radiology, etc.) per the selection strategy
- [ ] Responses stream back via MCP as they are generated

## Work Log
| Date | Action | Learnings |
|------|--------|-----------|
| 2026-04-06 | Created from agent-native review | Blocks Copilot Studio integration |
