---
status: pending
priority: p1
issue_id: "149"
tags: [code-review, quality, null-safety, crash]
dependencies: []
---

# assistant_bot.py Missing Null Guard on activity.text

## Problem Statement

`assistant_bot.py:96` accesses `turn_context.activity.text.endswith("clear")` without the `or ""` null guard that was applied in `magentic_bot.py` (lines 60, 69). If `activity.text` is `None`, this raises `AttributeError: 'NoneType' object has no attribute 'endswith'`, crashing the message handler.

This is an inconsistency introduced during the null-safety pass — the same fix was applied to `magentic_bot.py` but missed in `assistant_bot.py`.

## Findings

- **Source**: Kieran Python Reviewer
- **Evidence**: `src/bots/assistant_bot.py` line 96 vs `src/bots/magentic_bot.py` lines 60, 69
- **Impact**: Runtime crash in assistant bot when Teams sends a message activity with null text (possible during installation events, broken webhooks)

## Proposed Solutions

### Option A: Apply same guard (Recommended)
```python
if (turn_context.activity.text or "").endswith("clear"):
```
- **Effort**: Small (1 line)
- **Risk**: None

## Technical Details
- **Affected files**: `src/bots/assistant_bot.py`
- **Lines**: 96

## Acceptance Criteria
- [ ] `assistant_bot.py` uses `(turn_context.activity.text or "")` guard matching `magentic_bot.py`
- [ ] No `AttributeError` when `activity.text` is `None`

## Work Log
- 2026-04-02: Identified during code review (kieran-python-reviewer agent)
