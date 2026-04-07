---
status: pending
priority: p2
issue_id: "215"
tags: [code-review, simplicity, dry]
dependencies: []
---

# Export Data Preparation Duplicated Between Word and PPTX

## Problem Statement
`content_export.py` and `presentation_export.py` independently define identical `_MAX_*_CHARS` constants, build `all_data` dicts with the same fields, apply per-field truncation, and inject demographics. When caps change (they have — from commit history), both files must be updated in lockstep.

## Findings
- **File**: `src/scenarios/default/tools/content_export/content_export.py` — defines caps, builds data dict
- **File**: `src/scenarios/default/tools/presentation_export.py` — defines same caps, same data dict pattern
- Identical values: pathology 3000, radiology 3000, treatment_plan 4000, oncologic_hist 4000

## Proposed Solution
Extract shared `_prepare_export_data(kwargs, demographics, caps) -> dict` and `_MAX_FIELD_CAPS` to `content_export/_shared.py`. Prompts remain separate (different output schemas).

- **Effort**: Small (~30 lines consolidated)

## Acceptance Criteria
- [ ] Single source of truth for field caps
- [ ] Shared data preparation function used by both exports
