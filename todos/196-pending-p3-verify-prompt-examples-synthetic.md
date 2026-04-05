---
status: complete
priority: p3
issue_id: "196"
tags: [code-review, security, hipaa, compliance]
dependencies: []
---

# Verify Clinical Prompt Examples Are Synthetic

## Problem Statement

The updated prompts in `content_export.py`, `presentation_export.py`, and `agents.yaml` now contain extensive real-world-style clinical examples (e.g., "42 yo with invasive SCC of cervix. Hx elevated creatinine, anemia, thrombocytosis & bipolar disorder..."). These are intended as formatting examples for the LLM.

## Findings

**Flagged by:** Security Sentinel

If these examples are derived from actual patient records (even if de-identified), they should be validated against HIPAA Safe Harbor or Expert Determination standards. Even de-identified clinical scenarios can be re-identifiable if they contain unique combinations of conditions, procedures, and timelines.

## Proposed Solutions

1. Confirm with compliance/IRB that examples meet de-identification standards
2. Add a comment in the prompt sections: `# All clinical examples below are synthetic and do not represent actual patients`
3. If any are derived from real cases, apply formal de-identification review

## Acceptance Criteria

- [ ] Compliance team confirms examples are synthetic or properly de-identified
- [x] Comment added to prompt sections confirming synthetic status

## Work Log

- 2026-04-04: Created from code review (Security Sentinel)
- 2026-04-04: Added `# All clinical examples in this prompt are synthetic and do not represent actual patients.` comment above TUMOR_BOARD_DOC_PROMPT and SLIDE_SUMMARIZATION_PROMPT. Compliance confirmation still needed (manual step).
