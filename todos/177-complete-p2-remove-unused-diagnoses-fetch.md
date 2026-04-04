---
status: pending
priority: p2
issue_id: "177"
tags: [code-review, python, yagni]
dependencies: []
---

# Remove unused _get_diagnoses() fetch from checklist gather

## Problem Statement
`_diagnoses` is loaded via `_get_diagnoses()` in the `asyncio.gather` call but is never consumed -- no `_check_diagnoses()` method exists. This wastes an async I/O call on every checklist invocation, adding unnecessary latency and network overhead. The underscore-prefixed variable name suggests it was speculatively added for future use, violating YAGNI.

## Findings
- **Source**: Kieran Python Reviewer (Moderate), Code Simplicity Reviewer (YAGNI)
- `src/scenarios/default/tools/pretumor_board_checklist.py:209` -- `_get_diagnoses()` included in `asyncio.gather`
- `src/scenarios/default/tools/pretumor_board_checklist.py:217` -- `_diagnoses` result variable assigned but never read
- `src/scenarios/default/tools/pretumor_board_checklist.py:326-327` -- `_get_diagnoses` method definition (dead code)

## Proposed Solutions
1. **Remove _get_diagnoses() from gather and delete the method**
   - Remove the call from `asyncio.gather`
   - Remove the `_diagnoses` variable from the unpacking
   - Delete the `_get_diagnoses` method entirely
   - Pros: Eliminates wasted I/O, reduces code surface, follows YAGNI
   - Cons: Must re-add if diagnoses checking is implemented later
   - Effort: ~5 minutes

2. **Implement _check_diagnoses() to use the data**
   - Only if there is a known upcoming requirement for diagnosis checking
   - Pros: Completes the intended feature
   - Cons: Speculative work if no requirement exists
   - Effort: ~1-2 hours (depending on clinical logic)

## Acceptance Criteria
- [ ] `_get_diagnoses()` is no longer called in `asyncio.gather`
- [ ] `_diagnoses` variable is removed from the gather result unpacking
- [ ] `_get_diagnoses` method is deleted from the class
- [ ] No references to `_diagnoses` or `_get_diagnoses` remain in the file
- [ ] All existing tests pass
- [ ] Checklist execution time improves by eliminating the unnecessary async call
