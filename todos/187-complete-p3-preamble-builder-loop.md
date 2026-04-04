---
status: pending
priority: p3
issue_id: "187"
tags: [code-review, simplicity, python]
dependencies: []
---

# Preamble Builder: Replace Repetitive If/Append Blocks with Loop

## Problem Statement
Three identical if/append blocks for building `structured_preamble` (diagnoses, staging, medications) could be a simple loop over `(label, data)` tuples.

## Findings
- **Source agent:** Code Simplicity Reviewer
- **File:** `src/scenarios/default/tools/oncologic_history_extractor.py:192-201`

## Proposed Solutions
1. Replace the three if/append blocks with a loop:
   ```python
   for label, data in [("DIAGNOSES", diagnoses), ("STAGING", staging), ("MEDICATIONS", medications)]:
       if data:
           structured_preamble.append(f"{label}:\n{data}")
   ```
   - **Effort:** Small (5 min)

## Acceptance Criteria
- [ ] The three if/append blocks are replaced with a single `for` loop over `(label, data)` tuples
- [ ] `structured_preamble` output is identical before and after the change
- [ ] Existing tests pass without modification
