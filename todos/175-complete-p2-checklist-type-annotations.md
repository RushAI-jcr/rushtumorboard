---
status: pending
priority: p2
issue_id: "175"
tags: [code-review, python, type-safety]
dependencies: []
---

# Add type annotations to checklist and message enrichment parameters

## Problem Statement
`pretumor_board_checklist.py` has untyped `__init__` params (`data_access`, `chat_ctx`) and all `_get_*` methods have an untyped `accessor` parameter. Similarly, `message_enrichment.py`'s `apply_sas_urls` has an untyped `data_access` parameter. Without type annotations, static analysis tools (mypy, pyright) cannot catch misuse at call sites, and contributors must read implementation bodies to understand expected interfaces.

## Findings
- **Source**: Kieran Python Reviewer (Must fix)
- `src/scenarios/default/tools/pretumor_board_checklist.py:165-167` -- `__init__` params `data_access` and `chat_ctx` lack type annotations
- `src/scenarios/default/tools/pretumor_board_checklist.py` -- all `_get_*` methods accept untyped `accessor` parameter
- `src/utils/message_enrichment.py:40` -- `apply_sas_urls` has untyped `data_access` parameter

## Proposed Solutions
1. **Add explicit type annotations inline**
   - Add `data_access: DataAccess`, `chat_ctx: ChatContext` to `__init__`
   - Add `accessor: ClinicalNoteAccessorProtocol` to each `_get_*` method
   - Add `data_access: DataAccess` to `apply_sas_urls`
   - Pros: Immediate mypy coverage, self-documenting
   - Cons: Minimal -- just import the types at the top
   - Effort: ~15 minutes

2. **Use Protocol-based typing for accessor**
   - If `ClinicalNoteAccessorProtocol` doesn't exist yet, define a Protocol class for the accessor interface
   - Pros: Decoupled from concrete implementation
   - Cons: Slightly more setup if Protocol doesn't exist
   - Effort: ~30 minutes

## Acceptance Criteria
- [ ] `data_access` and `chat_ctx` in `__init__` have type annotations
- [ ] Every `_get_*` method's `accessor` parameter is typed
- [ ] `apply_sas_urls` `data_access` parameter is typed
- [ ] `mypy --strict` passes on both files with no new errors
- [ ] No runtime behavior changes
