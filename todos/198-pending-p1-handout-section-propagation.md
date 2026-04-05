---
status: complete
priority: p1
issue_id: "198"
tags: [code-review, architecture, prompt-engineering]
dependencies: []
---

# Propagate HANDOUT DISCUSSION/TRIAL NOTE Sections to Export Prompts

## Problem Statement

ClinicalGuidelines and ClinicalTrials agents now produce "Part 2: Handout" sections (`**HANDOUT DISCUSSION:**` and `**HANDOUT TRIAL NOTE:**`), but the export prompts (content_export.py, presentation_export.py) never mention these section headers. The export LLM must independently discover them buried in free-text blobs. Worse, `_MAX_TREATMENT_PLAN_CHARS = 2000` in presentation_export.py may truncate the treatment_plan string before the HANDOUT DISCUSSION section (which appears at the end of the agent's response).

## Findings

**Flagged by:** Agent-Native Reviewer (Warnings 1, 2, 4)

1. Export prompts don't reference `**HANDOUT DISCUSSION:**` or `**HANDOUT TRIAL NOTE:**` headers
2. ReportCreation agent instructions don't mention these sections
3. `_MAX_TREATMENT_PLAN_CHARS = 2000` will truncate HANDOUT DISCUSSION for complex cases

## Proposed Solutions

### Option A: Add extraction guidance to export prompts + raise char cap (Recommended)
1. In `TUMOR_BOARD_DOC_PROMPT` and `SLIDE_SUMMARIZATION_PROMPT`, add: "The `treatment_plan` field may contain a section labeled '**HANDOUT DISCUSSION:**' — use its content as the primary source for the `discussion` field."
2. Same for `clinical_trials` → `trial_eligible_note`: "Look for '**HANDOUT TRIAL NOTE:**' section."
3. Raise `_MAX_TREATMENT_PLAN_CHARS` from 2000 to 4000 in presentation_export.py to prevent truncation.
- Effort: Small | Risk: Low

### Option B: Extract HANDOUT sections before passing to export
Pre-process agent outputs to split Part 1 and Part 2, pass Part 2 separately via `board_discussion` parameter.
- Effort: Medium | Risk: Low (more robust but more code)

## Acceptance Criteria

- [x] Export prompts explicitly reference HANDOUT DISCUSSION and HANDOUT TRIAL NOTE headers
- [x] `_MAX_TREATMENT_PLAN_CHARS` raised to prevent truncation
- [x] ReportCreation agent instructions updated to acknowledge handout sections

## Work Log

- 2026-04-04: Created from code review (Agent-Native Reviewer)
- 2026-04-04: Fixed — Added HINT directives in TUMOR_BOARD_DOC_PROMPT (discussion + trial_eligible_note) and SLIDE_SUMMARIZATION_PROMPT (discussion_bullets + trial_eligible_note). Raised _MAX_TREATMENT_PLAN_CHARS 2000→4000. Updated ReportCreation agent instructions in agents.yaml to preserve HANDOUT sections when passing data to export tools.
