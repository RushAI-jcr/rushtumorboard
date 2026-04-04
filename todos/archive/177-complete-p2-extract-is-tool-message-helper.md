---
status: pending
priority: p2
issue_id: "177"
tags: [code-review, architecture, quality, dry]
dependencies: []
---

# Extract Shared _is_tool_message() Helper to Deduplicate Filtering

## Problem Statement

Tool-message filtering logic is duplicated identically in `receive()` (lines 95-103) and `create_channel()` (lines 167-176), with 3 separate import blocks for `FunctionCallContent`, `FunctionResultContent`, and `AuthorRole` (lines 84-86, 120-121, 157-159).

## Findings

- **Source**: Architecture Strategist (P1), Code Simplicity Reviewer, Python Quality Reviewer
- **Evidence**: Identical 3-way tool-message check duplicated across 2 methods with 3 import blocks
- **Risk**: Filter criteria could diverge as codebase evolves

## Proposed Solutions

### Option A: Static method on CustomHistoryChannel (Recommended)
```python
@staticmethod
def _is_tool_message(message: ChatMessageContent) -> bool:
    from semantic_kernel.contents.function_call_content import FunctionCallContent
    from semantic_kernel.contents.function_result_content import FunctionResultContent
    from semantic_kernel.contents.utils.author_role import AuthorRole
    return (
        message.role == AuthorRole.TOOL
        or any(isinstance(item, (FunctionCallContent, FunctionResultContent))
               for item in (message.items or []))
    )
```
Both `receive()` and `create_channel()` become one-liners: `if not self._is_tool_message(message)`
- **Pros**: Single source of truth; -8 LOC net; one import site
- **Cons**: None
- **Effort**: Small (15 min)
- **Risk**: None

## Acceptance Criteria
- [ ] Single _is_tool_message method used by both receive() and create_channel()
- [ ] Import blocks reduced from 3 to 1
- [ ] Filtering behavior unchanged
