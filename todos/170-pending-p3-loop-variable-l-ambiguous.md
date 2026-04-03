---
status: pending
priority: p3
issue_id: "170"
tags: [code-review, quality, python]
dependencies: []
---

# Ambiguous Loop Variable `l` in extract_page_title

## Problem Statement

`extract_page_title` in `nccn_pdf_processor.py` uses `l` as a loop variable in two list comprehensions. PEP 8 explicitly prohibits `l` (lowercase L) as a variable name because it is visually indistinguishable from `1` (the digit one) in many fonts.

## Findings

**Source:** kieran-python-reviewer

```python
# scripts/nccn_pdf_processor.py, extract_page_title (line ~233)
lines = [l.strip() for l in text.split("\n") if l.strip()]
filtered = [l for l in lines if not l.startswith("NCCN") ...]
```

## Proposed Solution

Rename both uses of `l` to `line`:

```python
lines = [line.strip() for line in text.split("\n") if line.strip()]
filtered = [line for line in lines if not line.startswith("NCCN") ...]
```

**Effort:** Trivial (2-line change).

## Acceptance Criteria

- [ ] No `l` loop variables in `extract_page_title`
- [ ] Uses `line` consistently

## Work Log

- 2026-04-03: Identified by kieran-python-reviewer during code review
