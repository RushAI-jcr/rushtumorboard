---
status: pending
priority: p1
issue_id: "151"
tags: [code-review, security, architecture, data-integrity]
dependencies: []
---

# Empty String conversation_id Collision Risk

## Problem Statement

Both `assistant_bot.py` and `magentic_bot.py` fall back to `""` when `conversation.id` is `None`. This means all sessions without a conversation ID share the same chat context, chat artifacts, and blob paths — creating a data collision and cross-patient contamination risk.

The `""` value propagates into `ChatContextAccessor.read("")`, `ChatContextAccessor.write()`, blob paths like `"/user_message.txt"`, and the `turn_contexts` dict.

## Findings

- **Source**: Architecture Strategist, Security Sentinel, Code Simplicity Reviewer
- **Evidence**: `src/bots/assistant_bot.py` lines 88, 166; `src/bots/magentic_bot.py` lines 52, 127, 133, 208
- **Related**: todos/106-complete-p1-chatcontext-mutable-shared-patient-id-corruption.md (similar pattern)
- **Impact**: Two concurrent null-conversation requests would collide, potentially mixing patient data between sessions

## Proposed Solutions

### Option A: Reject and return early (Recommended)
```python
if not turn_context.activity.conversation or not turn_context.activity.conversation.id:
    logger.error("Received message with no conversation ID; dropping.")
    await turn_context.send_activity("Unable to process: no conversation context.")
    return
conversation_id = turn_context.activity.conversation.id
```
- **Pros**: Explicit failure, no silent data mixing
- **Cons**: Drops the message entirely
- **Effort**: Small
- **Risk**: Low (Teams always provides conversation.id for message activities)

### Option B: Generate ephemeral UUID
- Use `f"ephemeral-{uuid4()}"` when conversation.id is None
- **Pros**: Message still processed in isolation
- **Cons**: Context not recoverable across requests
- **Effort**: Small
- **Risk**: Low

## Technical Details
- **Affected files**: `src/bots/assistant_bot.py`, `src/bots/magentic_bot.py`
- **Pattern appears**: 6 times across both files

## Acceptance Criteria
- [ ] No empty-string conversation_id reaches ChatContextAccessor
- [ ] Explicit error or ephemeral ID generated when conversation.id is None
- [ ] Log warning when fallback is triggered

## Work Log
- 2026-04-02: Identified during code review (architecture-strategist, security-sentinel)
