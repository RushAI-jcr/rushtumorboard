---
status: pending
priority: p2
issue_id: "183"
tags: [code-review, simplicity, python]
dependencies: []
---

# Collapse redundant imaging fallback tiers in _get_radiology()

## Problem Statement
`_get_radiology()` in `pretumor_board_checklist.py` has separate Tier A and Tier B+C steps that perform the same operation: keyword-filter clinical notes for imaging terms. The tier distinction adds no downstream value because `_note_to_rad_format()` discards the provenance (tier source) and `_check_imaging` does not distinguish between tiers. This results in an extra async call, ~15 lines of unnecessary code, and cognitive overhead for maintainers trying to understand why the tiers are separated.

## Findings
- **Source**: Code Simplicity Reviewer
- `src/scenarios/default/tools/pretumor_board_checklist.py:269-296` -- separate Tier A and Tier B+C calls that do the same filtering

## Proposed Solutions
1. **Collapse into a single call with combined note types**
   - Merge `ONCOLOGY_TIER_A_TYPES + GENERAL_TIER_B_TYPES` into one list
   - Make a single `get_clinical_notes_by_keywords()` call with the combined types and imaging keywords
   - Pros: Eliminates redundant async call, reduces code by ~15 lines, simpler to understand
   - Cons: Loses the ability to re-introduce tier-based logic later (easy to add back if needed)
   - Effort: ~15 minutes

2. **Keep tiers but make them a single parametric call**
   - Refactor into a loop over tier configurations
   - Pros: Preserves tier structure for future differentiation
   - Cons: Adds complexity for no current benefit (YAGNI)
   - Effort: ~20 minutes

## Acceptance Criteria
- [ ] `_get_radiology()` makes a single async call instead of separate tier calls
- [ ] Combined note types include both oncology and general types
- [ ] Imaging keyword filtering is preserved
- [ ] `_check_imaging` produces identical results on test data
- [ ] All existing tests pass
- [ ] Net reduction of ~15 lines of code
