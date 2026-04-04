---
status: pending
priority: p3
issue_id: "188"
tags: [code-review, documentation, architecture]
dependencies: []
---

# Document Intentional Overlap Between Oncology Tier A and General Tier B Note Types

## Problem Statement
`ONCOLOGY_TIER_A_TYPES` includes "Oncology Consultation" which also appears in `CONSULT_NOTE_TYPES` (part of `GENERAL_TIER_B_TYPES`). The overlap is intentional (priority-ordered tiers, not partitions) but could confuse a future contributor into "fixing" it.

## Findings
- **Source agent:** Architecture Strategist (P4)
- **File:** `src/scenarios/default/tools/note_type_constants.py:48-57`

## Proposed Solutions
1. Add an inline comment explaining the intentional overlap between tiers, e.g.:
   ```python
   # NOTE: Some types (e.g. "Oncology Consultation") intentionally appear in both
   # Tier A and Tier B lists. Tiers are priority-ordered, not partitions — a note
   # matched in Tier A will not fall through to Tier B.
   ```
   - **Effort:** Small (2 min)

## Acceptance Criteria
- [ ] A comment near the tier constant definitions explains the intentional overlap
- [ ] The comment clarifies that tiers are priority-ordered, not mutually exclusive partitions
- [ ] No functional code changes are made
