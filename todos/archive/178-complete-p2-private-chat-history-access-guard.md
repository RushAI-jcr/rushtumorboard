---
status: pending
priority: p2
issue_id: "178"
tags: [code-review, architecture, maintainability]
dependencies: []
---

# Private _chat_history Access Needs Version Guard

## Problem Statement

`src/group_chat.py` lines 107 and 123 access `self.thread._chat_history`, a private attribute on `ChatHistoryAgentThread`. The `hasattr` guard means failures are invisible — if SK renames this attribute, truncation silently stops working and thread sizes become unbounded again.

## Findings

- **Source**: Architecture Strategist (HIGH), Python Quality Reviewer (HIGH)
- **Evidence**: Lines 107-111, 123-124 — `hasattr(self.thread, '_chat_history')`
- **SK Version**: semantic-kernel==1.37.0 (pinned in requirements.txt)
- **Risk**: Silent degradation on SK upgrade

## Proposed Solutions

### Option A: Add startup assertion + version comment (Recommended)
```python
# At module level, after imports:
from semantic_kernel.agents.chat_completion.chat_completion_agent import ChatHistoryAgentThread
assert hasattr(ChatHistoryAgentThread, '_chat_history'), (
    "SK internal API changed: ChatHistoryAgentThread no longer has _chat_history. "
    "Review CustomHistoryChannel for SK version compatibility (tested: 1.37.0)."
)
```
- **Pros**: Fails loudly on SK upgrade; documents version coupling
- **Cons**: Assert in production (but this is a load-time check, not runtime)
- **Effort**: Small (5 min)
- **Risk**: None

## Acceptance Criteria
- [ ] Module-level assertion verifies _chat_history exists on ChatHistoryAgentThread
- [ ] Comment documents tested SK version (1.37.0)
- [ ] SK upgrade immediately surfaces breakage
