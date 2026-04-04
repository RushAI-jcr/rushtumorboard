---
status: pending
priority: p1
issue_id: "175"
tags: [code-review, architecture, clinical-safety]
dependencies: []
---

# Termination Parser Defaults to "Terminate" on Parse Failure — Clinical Safety Risk

## Problem Statement

`src/group_chat.py` lines 394-401: `evaluate_termination` catches all exceptions and returns `True` (terminate). If the LLM returns malformed JSON (which happens with Azure OpenAI under load), the conversation silently ends. In a clinical workflow, this could cut off mid-case review without ReportCreation having run, producing an incomplete tumor board presentation.

## Findings

- **Source**: Agent-Native Reviewer (Warning #4)
- **Evidence**: Lines 399-401 — `except Exception as exc: ... return True`
- **Clinical Risk**: Premature termination means a patient case could be reviewed without Pathology, Radiology, ClinicalGuidelines, or ClinicalTrials input
- **Known Pattern**: Past solution `clinical-trials-eligibility-matcher-rewrite.md` documents silent 400 errors from Azure OpenAI reasoning models

## Proposed Solutions

### Option A: Default to "continue" on parse failure (Recommended)
- Change `return True` to `return False` on line 401
- The conversation continues safely; the facilitator gets another chance to guide it
- `maximum_iterations=30` provides the ultimate circuit breaker
- **Pros**: Safer default for clinical workflows; iteration limit prevents runaway
- **Cons**: Could extend conversation unnecessarily on repeated parse failures
- **Effort**: Small (5 min)
- **Risk**: Very low — worst case is extra iterations before hitting max_iterations

### Option B: Add retry counter, terminate after N consecutive failures
- Track consecutive parse failures; only terminate after 3 in a row
- **Pros**: More nuanced; avoids infinite loops
- **Cons**: More complex; needs state tracking across calls
- **Effort**: Medium (30 min)
- **Risk**: Low

## Acceptance Criteria
- [ ] evaluate_termination returns False (continue) on parse failure
- [ ] Warning log emitted on each parse failure
- [ ] Conversation does not prematurely end on transient LLM JSON errors
