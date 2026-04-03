---
status: complete
priority: p2
issue_id: "004"
tags: [code-review, performance, reliability]
dependencies: []
---

# P2 — No input token caps on `_summarize_for_slides` (unlike `content_export.py`)

## Problem Statement

`_summarize_for_slides` serializes all 13 agent output fields raw into the LLM prompt.
`content_export.py` applies explicit per-field character caps before doing the same thing.
The asymmetry means PPTX summarization is vulnerable to context window overflow on complex
OSH-transfer cases with long `pathology_findings`, `radiology_findings`, or
`board_discussion` fields.

## Findings

`content_export.py` pattern (already correct):
```python
_MAX_ONCOLOGIC_HISTORY_CHARS  = 4000
_MAX_MEDICAL_HISTORY_CHARS    = 2000
_MAX_BOARD_DISCUSSION_CHARS   = 3000
_MAX_CT_FINDINGS_CHARS        = 500

all_data["oncologic_history"] = str(...)[:_MAX_ONCOLOGIC_HISTORY_CHARS]
all_data["medical_history"]   = str(...)[:_MAX_MEDICAL_HISTORY_CHARS]
```

`presentation_export.py` `_summarize_for_slides`: no equivalent caps. A full run through
all 9 agents can produce 30,000–60,000 characters across the fields. The MedicalResearch
RISEN synthesis and ClinicalGuidelines NCCN excerpts are the largest risks.

## Proposed Solution

Add a module-level constants block to `presentation_export.py` mirroring the pattern from
`content_export.py`:

```python
_MAX_PATHOLOGY_CHARS       = 3000
_MAX_RADIOLOGY_CHARS       = 2000
_MAX_TREATMENT_PLAN_CHARS  = 2000
_MAX_ONCOLOGIC_HIST_CHARS  = 3000
_MAX_BOARD_DISC_CHARS      = 2000
_MAX_CLINICAL_TRIALS_CHARS = 2000
```

Apply before `json.dumps` in `_summarize_for_slides`.

## Acceptance Criteria
- [ ] Per-field caps applied before serialization in `_summarize_for_slides`
- [ ] Cap constants are named and at module level (not inline magic numbers)
- [ ] Total serialized `all_data` stays under ~20,000 characters for a typical case
