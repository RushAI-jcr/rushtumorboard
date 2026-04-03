---
name: 4column-5column-content-export-description
description: Stale "4-column" references in content_export.py conflict with the current 5-column Word document schema
type: code-review
status: complete
priority: p2
issue_id: 045
tags: [code-review, documentation, coherence]
---

## Problem Statement

`content_export.py` `@kernel_function` description at line 122 says "landscape 4-column Word document" — the schema now has 5 columns. The method docstring at line 145 also says "4-column". An inline comment at line 200 says "4-column clinical shorthand". The `@kernel_function` description is what Semantic Kernel exposes to the LLM orchestrator for tool selection — an incorrect column count could mislead the Orchestrator's reasoning about the document structure.

## Findings

- `content_export.py:122`: `@kernel_function` description says "landscape 4-column Word document" (stale)
- `content_export.py:145`: method docstring says "4-column" (stale)
- `content_export.py:200`: inline comment says "4-column clinical shorthand" (stale)
- Current schema has 5 columns; all three sites must be updated for coherence
- The `@kernel_function` description at line 122 is the highest-priority fix as it is surfaced to the LLM orchestrator at runtime

## Proposed Solutions

### Option A
Change all "4-column" string occurrences in `content_export.py` to "5-column": line 122 (`@kernel_function` description), line 145 (method docstring), and line 200 (inline comment).

**Pros:** Eliminates all stale references in a single file; no logic changes required; prevents orchestrator confusion
**Cons:** None
**Effort:** Trivial (< 15 minutes)
**Risk:** None

## Recommended Action

## Technical Details

**Affected files:**
- `src/plugins/content_export.py` (lines 122, 145, 200)

## Acceptance Criteria

- [ ] `content_export.py:122` `@kernel_function` description updated to "5-column"
- [ ] `content_export.py:145` method docstring updated to "5-column"
- [ ] `content_export.py:200` inline comment updated to "5-column"
- [ ] No other "4-column" string literals remain in `content_export.py`
- [ ] Grep confirms no "4-column" in any other export-related file

## Work Log

- 2026-04-02: Identified in code review

## Resources

- Branch: fix/accessor-protocol-cache-quality-015-022
