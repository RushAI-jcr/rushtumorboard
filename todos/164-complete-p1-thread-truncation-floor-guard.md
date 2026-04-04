---
status: complete
priority: p1
issue_id: "164"
tags: [code-review, performance, correctness]
dependencies: []
---

# Thread Truncation Walk-Forward Has No Floor Guard

## Problem Statement

`group_chat.py:158-166` implements a walk-forward algorithm to find a safe truncation cut point that doesn't orphan tool_result messages. However, the walk-forward loop has no upper bound — if all remaining messages are tool messages, `cut` advances to `len(msgs)` and the thread becomes empty. An empty thread sent to `invoke()` wastes an LLM call and causes the agent to hallucinate without context.

Additionally, the walk-forward handles the pattern `[tool, tool, ..., assistant+tool_calls]` but NOT the interleaved pattern `[tool, assistant+tool_calls, tool, assistant+tool_calls, tool]` that occurs with sequential auto-function-invocation. The single `if` at lines 162-165 only skips one assistant+tool_calls message, but consecutive ones can exist.

## Findings

- **Source**: Performance Oracle (CRITICAL), Python Reviewer (MEDIUM), Code Simplicity (LOW)
- **File**: `src/group_chat.py`, lines 154-170
- **Evidence**: `while cut < len(msgs) and _is_tool_message(msgs[cut]): cut += 1` has no ceiling; the subsequent `if` block only advances past one assistant+tool_calls, not consecutive ones.

## Proposed Solutions

### Option A: Add floor guard + loop for consecutive tool_calls (Recommended)
```python
# Walk forward to a safe cut point
while cut < len(msgs):
    if _is_tool_message(msgs[cut]):
        cut += 1
    elif msgs[cut].role == AuthorRole.ASSISTANT and any(
        isinstance(item, FunctionCallContent) for item in (msgs[cut].items or [])
    ):
        cut += 1
    else:
        break
# Floor: keep at least 2 messages (system + one content message)
cut = min(cut, max(len(msgs) - 2, 0))
```
- **Pros**: Handles all interleaving patterns, guarantees minimum context
- **Cons**: Slightly more complex loop
- **Effort**: Small
- **Risk**: Low

### Option B: Simple floor guard only
- Add `cut = min(cut, len(msgs) - 1)` after the existing walk-forward
- **Pros**: Minimal change, prevents empty thread
- **Cons**: Doesn't fix interleaved tool_calls pattern
- **Effort**: Trivial
- **Risk**: Low

## Recommended Action

Option A — unified loop with floor guard.

## Technical Details

- **Affected files**: `src/group_chat.py`
- **Components**: CustomHistoryChannel.receive()
- **Related**: `len(msgs[cut:])` on line 169 creates a temporary list — use `len(msgs) - cut` instead

## Acceptance Criteria

- [ ] Thread never truncated to fewer than 2 messages
- [ ] Interleaved tool_calls/tool_result chains are handled correctly
- [ ] Log message uses `len(msgs) - cut` not `len(msgs[cut:])`
- [ ] Existing truncation tests still pass

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-04-04 | Code review finding | Performance Oracle identified interleaved pattern; Python Reviewer confirmed |

## Resources

- OpenAI tool message pairing requirement: every role='tool' must follow an assistant with tool_calls
- Semantic Kernel issue #12095 — tool messages leak across agents
