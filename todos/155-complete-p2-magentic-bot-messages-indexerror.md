---
status: pending
priority: p2
issue_id: "155"
tags: [code-review, quality, crash]
dependencies: []
---

# magentic_bot.py messages[-1].content IndexError Risk

## Problem Statement

`magentic_bot.py` lines 137 and 251 access `chat_ctx.chat_history.messages[-1].content` without checking if `messages` is empty. If empty, raises `IndexError`. If `content` is `None`, string concatenation with `"**User**: "` raises `TypeError`.

## Findings

- **Source**: Kieran Python Reviewer
- **Evidence**: `src/bots/magentic_bot.py` lines 137, 251

## Proposed Solutions

### Option A: Guard with empty check (Recommended)
```python
if chat_ctx.chat_history.messages:
    last_content = chat_ctx.chat_history.messages[-1].content or ""
    await turn_context.send_activity("**User**: " + last_content)
```
- **Effort**: Small
- **Risk**: None

## Acceptance Criteria
- [ ] No IndexError when messages list is empty
- [ ] No TypeError when content is None

## Work Log
- 2026-04-02: Identified during code review (kieran-python-reviewer)
