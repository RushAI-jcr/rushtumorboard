---
status: pending
priority: p2
issue_id: "182"
tags: [code-review, python, dry]
dependencies: []
---

# Extract repeated marker name normalization to a helper function

## Problem Statement
The normalization pattern `.lower().replace("-", "").replace(" ", "")` appears 6+ times across `tumor_markers.py`. This violates DRY (Don't Repeat Yourself) -- if the normalization logic needs to change (e.g., adding `.replace("_", "")` or stripping diacritics), every occurrence must be updated independently, risking inconsistency and bugs.

## Findings
- **Source**: Kieran Python Reviewer (Moderate)
- `src/scenarios/default/tools/tumor_markers.py:82-83` -- normalization in marker lookup
- `src/scenarios/default/tools/tumor_markers.py:156-157` -- normalization in matching logic
- `src/scenarios/default/tools/tumor_markers.py:181` -- normalization in comparison
- `src/scenarios/default/tools/tumor_markers.py:381` -- normalization in search
- `src/scenarios/default/tools/tumor_markers.py:383` -- normalization in filtering

## Proposed Solutions
1. **Extract to a module-level helper function**
   - Create `def _normalize_marker_name(name: str) -> str: return name.lower().replace("-", "").replace(" ", "")`
   - Replace all inline occurrences with calls to the helper
   - Pros: Single source of truth, easy to extend, self-documenting
   - Cons: None
   - Effort: ~15 minutes

2. **Extract as a static method on the class**
   - Add `@staticmethod def _normalize_marker_name(name: str) -> str` to the class
   - Pros: Scoped to the class, discoverable via class API
   - Cons: Slightly more verbose call syntax (`self._normalize_marker_name(...)`)
   - Effort: ~15 minutes

## Acceptance Criteria
- [ ] A single `_normalize_marker_name(name: str) -> str` function exists (module-level or static method)
- [ ] All 6+ inline normalization patterns are replaced with calls to the helper
- [ ] No duplicate normalization logic remains in the file
- [ ] All existing tumor marker tests pass
- [ ] Marker lookups and comparisons produce identical results before and after the change
