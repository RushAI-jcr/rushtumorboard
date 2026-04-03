---
status: pending
priority: p3
issue_id: "133"
tags: [code-review, architecture, reliability]
dependencies: []
---

# 133 — Single-message termination window causes premature group chat stop

## Problem Statement

`KernelFunctionTerminationStrategy` in `group_chat.py:330` configures `ChatHistoryTruncationReducer(target_count=1, auto_reduce=True)`, meaning the termination LLM evaluates only the single most recent message in the conversation. If any agent issues a clarifying question directed at the user mid-workflow, the termination function sees that question in isolation and may return `yes` — stopping the entire group chat before the remaining agents have presented. The termination logic has no awareness of whether the Orchestrator has issued a conclusion statement.

## Findings

- `group_chat.py:330` — `ChatHistoryTruncationReducer(target_count=1, auto_reduce=True)`

## Proposed Solution

Increase `target_count` to 3–5 messages so the termination LLM has enough context to distinguish mid-workflow clarifications from genuine completion signals:

```python
ChatHistoryTruncationReducer(target_count=5, auto_reduce=True)
```

Additionally or alternatively, update the termination prompt to require that the Orchestrator has emitted an explicit conclusion statement (e.g., containing a sentinel phrase) before the function returns `yes` in response to a user-directed question.

## Acceptance Criteria

- [ ] Termination reducer is configured with `target_count` of at least 3
- [ ] A mid-workflow clarifying question addressed to the user does not cause the group chat to terminate prematurely
- [ ] The Orchestrator conclusion statement is visible in the termination window before `yes` is returned
