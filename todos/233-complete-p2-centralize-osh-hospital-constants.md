---
status: complete
priority: p2
issue_id: "233"
tags: [code-review, architecture]
dependencies: []
---

# Centralize OSH Hospital Names and Imaging Constants

## Problem Statement

OSH hospital names ("riverside", "lutheran", "good samaritan", "edwards") and the Copley affiliate exception appear in 4+ files: radiology_extractor.py, agents.yaml, content_export.py, presentation_export.py, and oncologic_history_extractor.py. Adding a new hospital or changing the Copley rule requires updating all files — high risk of drift.

## Findings

**Flagged by:** Architecture Strategist (HIGH), Code Simplicity Reviewer

**Affected files:**
- `src/scenarios/default/tools/radiology_extractor.py` — layer3_keywords + system prompt rule 13
- `src/scenarios/default/config/agents.yaml` — OSH RULE in Radiology + PatientStatus agents
- `src/scenarios/default/tools/content_export/content_export.py` — OSH RULE
- `src/scenarios/default/tools/presentation_export.py` — OSH mandate
- `src/scenarios/default/tools/oncologic_history_extractor.py` — Copley rule

## Proposed Solutions

### Option A: Create imaging_constants.py (Recommended)
```python
# src/scenarios/default/tools/imaging_constants.py
OSH_HOSPITAL_NAMES = frozenset(["riverside", "lutheran", "good samaritan", "edwards"])
RUSH_AFFILIATES = frozenset(["rush copley", "copley"])
```
Import from this module in radiology_extractor.py and pretumor_board_checklist.py.
For YAML and prompt files, add a comment referencing imaging_constants.py as the source of truth.
- Effort: Medium | Risk: Low

### Option B: Keep duplicated, add comments
Add `# Keep in sync with imaging_constants list in radiology_extractor.py` comments.
- Effort: Tiny | Risk: Medium (comments drift)

## Acceptance Criteria

- [x] Hospital names defined in one canonical location
- [x] Copley affiliate rule defined once
- [x] Python files import from shared module
- [x] YAML/prompt files reference the canonical location in comments

## Work Log

- 2026-04-09: Created from Phase 2 code review (Architecture Strategist)
- 2026-04-09: Implemented Option A. Created imaging_constants.py with OSH_HOSPITAL_NAMES and RUSH_AFFILIATES frozensets. radiology_extractor.py imports and dynamically builds rule 13 via .replace(). Added "Source of truth: imaging_constants.py" comments in agents.yaml, content_export.py, presentation_export.py, oncologic_history_extractor.py.
