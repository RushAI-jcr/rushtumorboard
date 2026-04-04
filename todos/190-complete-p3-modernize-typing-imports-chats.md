---
status: pending
priority: p3
issue_id: "190"
tags: [code-review, python, style]
dependencies: []
---

# Modernize Typing Imports in chats.py

## Problem Statement
`chats.py` uses `from typing import Dict, List, Optional` (Python 3.9 style). The project targets Python 3.12+ and uses modern builtin type hints elsewhere, making this file inconsistent with the rest of the codebase.

## Findings
- **Source agent:** Kieran Python Reviewer (Low)
- **File:** `src/routes/api/chats.py:9`

## Proposed Solutions
1. Replace legacy `typing` imports with modern builtin equivalents:
   - `Dict` -> `dict`
   - `List` -> `list`
   - `Optional[X]` -> `X | None`
   - Remove the `from typing import Dict, List, Optional` line
   - **Effort:** Small (10 min)

## Acceptance Criteria
- [ ] No imports of `Dict`, `List`, or `Optional` from `typing` remain in `chats.py`
- [ ] All type annotations use `dict`, `list`, and `X | None` syntax
- [ ] File passes `pyright` / `mypy` type checking
- [ ] Existing tests pass without modification
