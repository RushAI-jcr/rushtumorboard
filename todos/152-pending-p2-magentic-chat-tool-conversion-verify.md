---
status: pending
priority: p2
issue_id: "152"
tags: [code-review, architecture, autogen, semantic-kernel]
dependencies: []
---

# Verify magentic_chat.py function.method to function Change

## Problem Statement

`magentic_chat.py:19` changed from `tools.append(function.method)` to `tools.append(function)`, passing full SK `KernelFunction` objects to AutoGen's `AssistantAgent`. AutoGen expects `Callable` or `Tool` objects. If `KernelFunction.__call__` has a generic signature (e.g., `**kwargs`), AutoGen's `inspect.signature()` will fail to discover the tool schema, and the LLM won't know what parameters to pass.

## Findings

- **Source**: Kieran Python Reviewer, Architecture Strategist, Agent-Native Reviewer
- **Evidence**: `src/magentic_chat.py` line 19
- **Risk**: Silent tool invocation failure in the MagenticOne experimental path
- **Note**: Primary SK AgentGroupChat path is unaffected

## Proposed Solutions

### Option A: Add runtime test (Recommended)
Add a test in `test_local_agents.py` that verifies AutoGen correctly discovers KernelFunction schemas.
- **Effort**: Medium
- **Risk**: Low

### Option B: Revert to function.method if .method still exists
- **Effort**: Small
- **Risk**: May fail if SK removed .method in recent version

## Acceptance Criteria
- [ ] Runtime test confirms AutoGen tool schema discovery from KernelFunction objects
- [ ] Comment in `convert_tools` documenting the SK-to-AutoGen bridge contract

## Work Log
- 2026-04-02: Identified during code review (multiple agents)
