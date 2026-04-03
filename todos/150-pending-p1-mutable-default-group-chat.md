---
status: pending
priority: p1
issue_id: "150"
tags: [code-review, quality, type-safety, mutable-default]
dependencies: []
---

# Mutable Default Argument in group_chat.py

## Problem Statement

`group_chat.py` line 111 has `participants: list[dict] = None` — the exact same mutable default / type mismatch bug that was fixed in `chat_simulator.py` and `evaluator.py` in this changeset but missed here.

## Findings

- **Source**: Kieran Python Reviewer
- **Evidence**: `src/group_chat.py` line 111
- **Known Pattern**: todos/137-complete-p3-python-type-annotation-quality-bundle.md documented this class of bug
- **Impact**: Type error under strict checking; potential shared-state mutation if `participants` is ever mutated in-place

## Proposed Solutions

### Option A: Fix type annotation (Recommended)
```python
def create_group_chat(
    app_ctx: AppContext, chat_ctx: ChatContext, participants: list[dict] | None = None
) -> tuple[AgentGroupChat, ChatContext]:
```
Also change `Tuple` (typing import) to `tuple` (builtin, Python 3.9+).
- **Effort**: Small (2 lines)
- **Risk**: None

## Technical Details
- **Affected files**: `src/group_chat.py`
- **Lines**: 111

## Acceptance Criteria
- [ ] `participants` typed as `list[dict] | None = None`
- [ ] Return type uses `tuple` not `Tuple`
- [ ] No pyright/mypy errors

## Work Log
- 2026-04-02: Identified during code review (kieran-python-reviewer)
