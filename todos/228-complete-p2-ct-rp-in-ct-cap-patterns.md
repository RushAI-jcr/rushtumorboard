---
status: complete
priority: p2
issue_id: "228"
tags: [code-review, quality, checklist]
dependencies: []
---

# "ct rp" Misplaced in _CT_CAP_PATTERNS (Semantic Error)

## Problem Statement

`pretumor_board_checklist.py` groups "ct rp" (CT retroperitoneum) inside `_CT_CAP_PATTERNS` (CT chest/abdomen/pelvis). CT retroperitoneum is a distinct study — it should not satisfy a CT CAP completeness check.

## Findings

**Flagged by:** Kieran Python Reviewer (MEDIUM), Code Simplicity Reviewer

**File:** `src/scenarios/default/tools/pretumor_board_checklist.py`

```python
_CT_CAP_PATTERNS = ["ct chest, abdomen and pelvis", "ct chest abdomen pelvis",
                    "ct chest abdomen & pelvis", "ct a/p", "ct ap", "ct cap",
                    "ctap", "ct chest/abdomen/pelvis", "ct rp"]  # <-- wrong group
```

## Proposed Solutions

### Option A: Move to its own pattern list (Recommended)
```python
_CT_RP_PATTERNS = ["ct rp", "ct retroperitoneum", "retroperitoneal ct"]
```
And remove "ct rp" from `_CT_CAP_PATTERNS`. Add a conditional check for CT RP similar to the TVUS/bone scan checks.
- Effort: Small | Risk: None

### Option B: Simply remove from _CT_CAP_PATTERNS
If CT RP doesn't need its own checklist item, just remove it.
- Effort: Tiny | Risk: None

## Acceptance Criteria

- [ ] "ct rp" removed from _CT_CAP_PATTERNS
- [ ] Either added to its own pattern list or removed entirely

## Work Log

- 2026-04-09: Created from Phase 2 code review
