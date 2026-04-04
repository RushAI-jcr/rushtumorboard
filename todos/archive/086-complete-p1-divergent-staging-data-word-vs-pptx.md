---
status: complete
priority: p1
issue_id: "086"
tags: [code-review, architecture, clinical-safety]
dependencies: []
---

# P1 — Divergent FIGO stage and genetics between Word and PPTX exports (clinical safety)

## Problem Statement

`content_export.py` and `presentation_export.py` each make independent Azure OpenAI calls with the same raw agent output. `TumorBoardDocContent.stage` (Word) and `SlideContent.stage` (PPTX) are filled by two separate LLM inference calls. Even at `temperature=0`, Azure OpenAI does not guarantee deterministic output across independent requests. A physician printing the Word handout may see "IIIC" while the PPTX displayed at the meeting shows "IVB" — a patient safety issue in a clinical decision support context.

## Findings

Architecture agent: "This is the most significant architectural concern in the changeset." At `temperature=0`, GPT-4o is typically deterministic, but o3-mini (reasoning model) is not. When `model_supports_temperature()` returns False (o3 model in use), the temperature constraint is not applied and sampling introduces divergence.

Both LLM prompts instruct the model to "extract" stage from the free-text `all_data` blob even though `figo_stage` and `molecular_profile` are also passed as explicit named parameters. The prompts do not instruct the model to prefer the named parameter over what it finds in the narrative — creating ambiguity when the narrative and the named field conflict.

The fields most at risk: `stage`, `germline_genetics`, `somatic_genetics`, `primary_site`.

## Proposed Solution

**Near-term (tighten prompts):**

In both `SLIDE_SUMMARIZATION_PROMPT` and `TUMOR_BOARD_DOC_PROMPT`, add explicit instruction:

```
IMPORTANT: Use the explicit `figo_stage` field as the authoritative FIGO stage value.
Do NOT re-extract stage from the narrative text — use the provided value verbatim.
Same for molecular_profile, germline_genetics, and somatic_genetics when provided.
```

**Architectural (single extraction):**

Create a shared `UnifiedExportContent` Pydantic model that is a superset of `TumorBoardDocContent` and `SlideContent`. `ReportCreation` calls the LLM once to produce `UnifiedExportContent`, then passes slices to the Word and PPTX renderers as pure data-mapping functions with no additional LLM calls. Both outputs necessarily agree on all shared fields.

## Acceptance Criteria
- [ ] Both LLM prompts explicitly instruct the model to use `figo_stage` as authoritative (not re-extract from narrative)
- [ ] At minimum: near-term prompt fix deployed before next live meeting
- [ ] Architectural fix (single LLM call / shared extraction model) tracked as follow-on
