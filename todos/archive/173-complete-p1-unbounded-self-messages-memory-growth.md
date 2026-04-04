---
status: pending
priority: p1
issue_id: "173"
tags: [code-review, performance, memory]
dependencies: []
---

# Unbounded self.messages List Growth in CustomHistoryChannel

## Problem Statement

`src/group_chat.py` lines 91-115: The `receive()` method truncates `self.thread._chat_history.messages` to 14 messages, but **never truncates `self.messages`** itself. The parent `ChatHistoryChannel.receive()` appends every broadcast to `self.messages` via `self.messages.extend(filtered_history)`. With 10 agents producing multi-message turns and `maximum_iterations=30`, `self.messages` grows to hundreds of entries. Each ChatMessageContent with tool results can be 10-20KB, leading to 30-60MB per conversation across all 10 agent channels.

## Findings

- **Source**: Performance Oracle (P0 finding)
- **Evidence**: `self.messages` is never truncated; only `self.thread._chat_history.messages` is capped
- **Impact**: Memory scales linearly per agent turn. Over 25-turn session: ~250KB x 10 agents = 2.5MB unbounded growth. At 10 concurrent sessions: 25-60MB live objects that cannot be GC'd
- **Root cause**: Parent `invoke()` indexes into `self.messages[-1]` and tracks `message_count`, so the list must exist, but old entries are never cleaned

## Proposed Solutions

### Option A: Truncate self.messages alongside thread (Recommended)
- Add after the thread truncation block:
```python
if len(self.messages) > self._MAX_THREAD_MESSAGES:
    self.messages = self.messages[-self._MAX_THREAD_MESSAGES:]
```
- **Pros**: 2-line fix, bounded memory, parent invoke() only reads self.messages[-1]
- **Cons**: Must verify parent invoke()'s message_count tracking resets each call
- **Effort**: Small (10 min)
- **Risk**: Low — verify parent invoke() behavior first

## Acceptance Criteria
- [ ] self.messages is bounded to _MAX_THREAD_MESSAGES after each receive() call
- [ ] Parent invoke() still functions correctly (passes existing tests)
- [ ] Memory usage stays flat across 25+ turn conversations
