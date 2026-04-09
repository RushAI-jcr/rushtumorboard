---
status: complete
priority: p2
issue_id: "232"
tags: [code-review, performance]
dependencies: []
---

# Hoist .lower() Out of Keyword Matching Loops

## Problem Statement

In `radiology_extractor.py` Layer 3 filtering and in `clinical_note_filter_utils.py`, `.lower()` is called inside the `any()` generator for every keyword check. Since the text doesn't change between iterations, `.lower()` should be called once and cached.

## Findings

**Flagged by:** Performance Oracle (Priority 2)

**Files:**
- `src/scenarios/default/tools/radiology_extractor.py` — Layer 3 keyword matching
- `src/utils/clinical_note_filter_utils.py` — similar pattern

```python
# Current (calls .lower() per keyword check):
if any(kw in text.lower() for kw in layer3_keywords):

# Should be:
text_lower = text.lower()
if any(kw in text_lower for kw in layer3_keywords):
```

## Proposed Solutions

### Option A: Cache .lower() result (Recommended)
Hoist the `.lower()` call above the `any()` check in both files.
- Effort: Tiny | Risk: None

## Acceptance Criteria

- [ ] `.lower()` called once per note, not per keyword
- [ ] Applied in both radiology_extractor.py and clinical_note_filter_utils.py

## Work Log

- 2026-04-09: Created from Phase 2 code review (Performance Oracle)
