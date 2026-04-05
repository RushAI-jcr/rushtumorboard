---
status: complete
priority: p3
issue_id: "194"
tags: [code-review, quality, python]
dependencies: []
---

# Python Quality: Type Annotations, frozenset, Discussion Guard

## Problem Statement

Minor Python quality improvements identified during code review.

## Findings

**Flagged by:** Kieran Python Reviewer

1. **`config.py` `_resolve` type annotation**: Uses `object` → should use `Any` (idiomatic for heterogeneous structures). Eliminates `# type: ignore[misc]` on line 131.

2. **`model_utils.py` `_NON_TEMP_MODELS`**: Plain `set` with mixed-case strings. Should be `frozenset` (immutable constant) with all-lowercase values. Simplifies the lookup to one `.lower()` call.

3. **`content_export.py` `_build_col4_richtext`**: Add `.strip()` guard on `c.discussion` before using it as a conditional. Whitespace-only discussion from LLM would produce a space before action items instead of a newline.

## Proposed Solutions

Each is a 1-3 line change. Apply all together.

## Acceptance Criteria

- [x] `_resolve` uses `Any` type, `# type: ignore` removed
- [x] `_NON_TEMP_MODELS` is `frozenset` with lowercase values
- [x] `_build_col4_richtext` uses `c.discussion.strip()` for conditional

## Work Log

- 2026-04-04: Created from code review (Kieran Python Reviewer)
- 2026-04-04: Fixed — All 3 changes applied
