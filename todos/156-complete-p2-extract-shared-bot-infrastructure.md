---
status: pending
priority: p2
issue_id: "156"
tags: [code-review, architecture, dry, simplicity]
dependencies: ["151"]
---

# Extract Shared Bot Infrastructure (DRY)

## Problem Statement

`create_turn_context` (34 lines) and `get_bot_context` (12 lines) are copy-pasted verbatim between `assistant_bot.py` and `magentic_bot.py`. The conversation_id null-safety pattern also appears 6+ times across both files.

## Findings

- **Source**: Code Simplicity Reviewer, Architecture Strategist
- **Evidence**: ~47 duplicated lines across `src/bots/assistant_bot.py` and `src/bots/magentic_bot.py`
- **Additionally**: MagenticBot directly accesses `container_client` for raw blob operations, bypassing the accessor abstraction

## Proposed Solutions

### Option A: Create BotBase mixin (Recommended)
Create `src/bots/bot_base.py` with `create_turn_context`, `get_bot_context`, and `_get_conversation_id`.
- **Effort**: Medium
- **Risk**: Low

## Acceptance Criteria
- [ ] Shared methods live in one place
- [ ] Both bots use the shared implementation
- [ ] conversation_id helper centralizes the null-safety guard

## Work Log
- 2026-04-02: Identified during code review (code-simplicity-reviewer, architecture-strategist)
