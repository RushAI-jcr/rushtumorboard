---
status: complete
priority: p3
issue_id: "168"
tags: [code-review, quality, python]
dependencies: []
---

# `_find_data_dir` Uses os.path Instead of pathlib

## Problem Statement

`_find_data_dir` in `nccn_guidelines.py` uses `os.path.dirname(os.path.abspath(__file__))` when `pathlib.Path` is already imported.

**Why:** Inconsistency — `nccn_pdf_processor.py` uses `Path(__file__).resolve().parent` correctly. Mixing `os.path` and `pathlib` in the same codebase creates unnecessary inconsistency.

## Findings

**Source:** kieran-python-reviewer

```python
# Current (nccn_guidelines.py line ~150):
tools_dir = Path(os.path.dirname(os.path.abspath(__file__)))

# Should be:
tools_dir = Path(__file__).resolve().parent
```

## Proposed Solution

One-line change. `Path(__file__).resolve().parent` is idiomatic and matches the pattern used in `nccn_pdf_processor.py` line 37.

## Acceptance Criteria

- [ ] `_find_data_dir` uses `Path(__file__).resolve().parent`
- [ ] 0 Pyright errors after change

## Work Log

- 2026-04-03: Identified by kieran-python-reviewer during code review
