---
status: pending
priority: p2
issue_id: "216"
tags: [code-review, simplicity, architecture]
dependencies: []
---

# OncologicHistory False Inheritance from MedicalReportExtractorBase

## Problem Statement
`OncologicHistoryExtractorPlugin` inherits `MedicalReportExtractorBase` but completely overrides `_extract()` with a 120-line method that reads structured CSVs — a fundamentally different strategy from the base class's 3-layer fallback. It does not set `accessor_method`, and `layer2_note_types`/`layer3_keywords` are never used. Only reuses `__init__` (4 attributes) and 2 constants.

## Findings
- **File**: `src/scenarios/default/tools/oncologic_history_extractor.py` — overrides 100% of extraction logic
- Only uses `_JSON_FENCE_RE`, `_LLM_TIMEOUT_SECS` from base class (module-level constants)
- Misleading: looks like a 3-layer extractor but is actually a completely different tool

## Proposed Solution
Make standalone class with own `__init__`. Import `_JSON_FENCE_RE` and `_LLM_TIMEOUT_SECS` as constants.

- **Effort**: Small (0 LOC change, refactor only)
- **Impact**: Major clarity improvement

## Acceptance Criteria
- [ ] OncologicHistoryExtractorPlugin is a standalone class
- [ ] No false inheritance from MedicalReportExtractorBase
- [ ] All tests pass unchanged
