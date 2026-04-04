---
status: pending
priority: p3
issue_id: "160"
tags: [code-review, quality]
dependencies: []
---

# Replace assert with Proper Guards in chat_simulator.py

## Problem Statement

`chat_simulator.py` lines 358, 380, 422 use `assert self.group_chat is not None` for runtime validation. Assertions are stripped when Python runs with `-O` (optimized mode). In a medical system, these should be proper `RuntimeError` guards.

## Proposed Solutions

Replace `assert` with:
```python
if self.group_chat is None:
    raise RuntimeError("group_chat must be initialized via setup_group_chat() before calling chat()")
```

## Work Log
- 2026-04-02: Identified during code review (kieran-python-reviewer)
