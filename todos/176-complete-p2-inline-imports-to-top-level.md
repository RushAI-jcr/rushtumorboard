---
status: pending
priority: p2
issue_id: "176"
tags: [code-review, python, imports]
dependencies: []
---

# Move inline imports to top-level in pretumor_board_checklist.py

## Problem Statement
`import asyncio` appears at line 206 inside a method body, and `from .note_type_constants import GENERAL_TIER_B_TYPES, ONCOLOGY_TIER_A_TYPES` appears at line 266 inside the `_get_radiology()` method body. PEP 8 mandates top-level imports unless there is a specific reason (circular dependency, optional dependency). These inline imports obscure dependencies, prevent static analysis from catching missing modules early, and add per-call overhead.

## Findings
- **Source**: Kieran Python Reviewer (Must fix), Code Simplicity Reviewer
- `src/scenarios/default/tools/pretumor_board_checklist.py:206` -- `import asyncio` inside method body
- `src/scenarios/default/tools/pretumor_board_checklist.py:266` -- `from .note_type_constants import GENERAL_TIER_B_TYPES, ONCOLOGY_TIER_A_TYPES` inside `_get_radiology()`

## Proposed Solutions
1. **Move both imports to the top of the file**
   - Move `import asyncio` to the stdlib imports section
   - Move `from .note_type_constants import ...` to the local imports section
   - Pros: PEP 8 compliant, cleaner dependency graph, one-time import cost
   - Cons: None -- no circular dependency risk for these modules
   - Effort: ~5 minutes

## Acceptance Criteria
- [ ] `import asyncio` appears at the top of the file in the stdlib section
- [ ] `from .note_type_constants import GENERAL_TIER_B_TYPES, ONCOLOGY_TIER_A_TYPES` appears at the top of the file in the local imports section
- [ ] No inline imports remain in method bodies (unless justified by circular dependency)
- [ ] All existing tests pass
- [ ] `ruff check` / `flake8` reports no import-order violations
