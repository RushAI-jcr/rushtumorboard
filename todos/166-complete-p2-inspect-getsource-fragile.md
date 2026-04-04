---
status: complete
priority: p2
issue_id: "166"
tags: [code-review, python, robustness]
dependencies: []
---

# inspect.getsource() Assertion is Fragile

## Problem Statement

`group_chat.py:69-76` uses `inspect.getsource(ChatHistoryAgentThread.__init__)` to verify that SK's internal `_chat_history` attribute exists. While more correct than the previous `hasattr` on the class, this introduces new failure modes: `OSError` on .pyc-only deployments, string matching brittleness, and `assert` being stripped in `-O` mode.

## Findings

- **Source**: Python Reviewer (HIGH), Code Simplicity (MEDIUM), Architecture Strategist (noted)
- **File**: `src/group_chat.py`, lines 69-76

## Proposed Solutions

### Option A: Probe-instance check (Recommended)
```python
_probe = ChatHistoryAgentThread()
if not hasattr(_probe, '_chat_history'):
    raise ImportError("SK internal API changed: ...")
del _probe
```
- **Pros**: Tests actual runtime behavior, works in all deployment modes
- **Cons**: Instantiates a throwaway object
- **Effort**: Small
- **Risk**: Low

### Option B: Wrap in try/except OSError
```python
try:
    _init_src = _inspect.getsource(ChatHistoryAgentThread.__init__)
    assert '_chat_history' in _init_src, "..."
except OSError:
    logger.warning("Cannot verify SK internals (source unavailable)")
```
- **Pros**: Minimal change, graceful degradation
- **Cons**: Still string-based, still uses assert
- **Effort**: Trivial
- **Risk**: Low

### Option C: Remove module-level assertion entirely
- Rely on runtime `hasattr(self.thread, '_chat_history')` check at line 150
- **Pros**: Simplest, no import-time fragility
- **Cons**: Later failure point, less obvious error message
- **Effort**: Trivial (delete 8 lines)
- **Risk**: Low

## Recommended Action

Option A for maximum robustness, or Option C for maximum simplicity.

## Technical Details

- **Affected files**: `src/group_chat.py`

## Acceptance Criteria

- [ ] No `inspect.getsource()` call at module level
- [ ] Application starts successfully in .pyc-only environments
- [ ] SK API changes still produce a clear error message

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-04-04 | Code review finding | 3 reviewers flagged; probe-instance is consensus recommendation |
