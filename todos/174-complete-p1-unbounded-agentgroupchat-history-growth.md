---
status: pending
priority: p1
issue_id: "174"
tags: [code-review, architecture, performance, memory]
dependencies: []
---

# Unbounded AgentGroupChat.history Growth After Removing Top-Level Reducer

## Problem Statement

The commit removed the `ChatHistoryTruncationReducer` wrapper that previously capped `chat_ctx.chat_history` before passing it to `AgentGroupChat`. Now the raw `ChatHistory` is passed directly (line 415). Since `create_group_chat()` is called fresh per user message but `chat_ctx.chat_history` is the **same object persisted across the entire conversation session**, it grows without bound: ~10 messages per turn, reaching 60-100 messages over a full tumor board case.

The per-agent channel caps (14 messages), selection reducer (12), and termination reducer (1) only truncate **their local copies** — the canonical `chat_ctx.chat_history` that gets serialized and persisted is never truncated.

## Findings

- **Source**: Architecture Strategist
- **Evidence**: Lines 414-416 pass raw `chat_ctx.chat_history` to AgentGroupChat; selection/termination reducers only truncate local views
- **Impact**: Serialized session state grows without limit. `create_channel()` re-filters and re-truncates this full history on every instantiation, becoming increasingly wasteful.
- **Prior code**: Had `ChatHistoryTruncationReducer(target_count=14, threshold_count=4, auto_reduce=True)` wrapping chat_ctx.chat_history

## Proposed Solutions

### Option A: Re-introduce bounded reducer at chat_ctx level (Recommended)
- Add a truncation cap in `create_group_chat()` before constructing AgentGroupChat:
```python
MAX_CANONICAL_HISTORY = 60
if len(chat_ctx.chat_history.messages) > MAX_CANONICAL_HISTORY:
    chat_ctx.chat_history.messages = chat_ctx.chat_history.messages[-MAX_CANONICAL_HISTORY:]
```
- **Pros**: Bounds serialized state, keeps create_channel() efficient, simple
- **Cons**: Loses early conversation context in long sessions
- **Effort**: Small (15 min)
- **Risk**: Low

### Option B: Use ChatHistoryTruncationReducer wrapper (like before, but with higher limit)
- Wrap chat_ctx.chat_history in `ChatHistoryTruncationReducer(target_count=60, auto_reduce=True)`
- **Pros**: Uses SK's built-in safe truncation; preserves function call/result pairs
- **Cons**: Previously removed because it was too aggressive at 14; need to pick right value
- **Effort**: Small (15 min)
- **Risk**: Low

## Acceptance Criteria
- [ ] chat_ctx.chat_history.messages is bounded after create_group_chat()
- [ ] Multi-turn conversations (3+ user messages) don't accumulate unbounded history
- [ ] Serialized session state size is stable
