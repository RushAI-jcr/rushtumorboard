---
status: pending
priority: p2
issue_id: "181"
tags: [code-review, quality, performance]
dependencies: ["172", "177"]
---

# Move Repeated Function-Level Imports to Module Scope

## Problem Statement

`FunctionCallContent`, `FunctionResultContent`, and `AuthorRole` are imported inside 3 separate method bodies (lines 84-86, 120-121, 157-159). These types are in the same `semantic_kernel` package already imported at module level (lines 10-28), so there is no lazy-loading benefit or circular import risk.

## Findings

- **Source**: Python Quality Reviewer (MEDIUM), Performance Oracle
- **Evidence**: 3 identical import blocks in receive(), invoke(), create_channel()
- **Also**: `model_rebuild()` on line 161 should be called once at module scope, not per create_channel()
- **Also**: Line 389 `from semantic_kernel.agents.agent import Agent` buried mid-function

## Proposed Solutions

### Option A: Move to module-level imports (Recommended)
Add to the import block at top of file:
```python
from semantic_kernel.agents.agent import Agent
from semantic_kernel.contents.function_call_content import FunctionCallContent
from semantic_kernel.contents.function_result_content import FunctionResultContent
from semantic_kernel.contents.utils.author_role import AuthorRole
```
Move `CustomHistoryChannel.model_rebuild()` to module scope after class definition.
- **Pros**: Cleaner code; eliminates per-call import lookups; removes 3 duplicate blocks
- **Cons**: None (no circular import risk)
- **Effort**: Small (10 min)
- **Risk**: None

## Acceptance Criteria
- [ ] All SK content types imported at module scope
- [ ] No function-level import blocks remain in group_chat.py
- [ ] model_rebuild() called once at module scope
