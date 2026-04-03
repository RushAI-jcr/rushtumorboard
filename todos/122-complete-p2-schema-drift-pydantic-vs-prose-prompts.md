---
status: pending
priority: p2
issue_id: "122"
tags: [code-review, architecture, reliability, clinical-safety]
dependencies: []
---

# 122 — Pydantic model fields and LLM prose prompts can silently drift out of sync

## Problem Statement

`TumorBoardDocContent` and `SlideContent` Pydantic models are used as `response_format` for LLM structured output. Their field names and semantics are duplicated in three separate places: the Pydantic model definition, `TUMOR_BOARD_DOC_PROMPT` in `content_export.py:70-125`, and `SLIDE_SUMMARIZATION_PROMPT` in `presentation_export.py:63-120`. Adding a field to the Pydantic model without updating the corresponding prose prompt means the LLM will not populate the new field — producing silently empty output rather than an error. There is no compile-time or test-time check that validates prompt–model alignment.

## Findings

- `tumor_board_summary.py:21-93` — `TumorBoardDocContent` and `SlideContent` Pydantic model definitions
- `content_export.py:86-125` — hand-written `TUMOR_BOARD_DOC_PROMPT` JSON schema description block
- `presentation_export.py:116-119` — hand-written `SLIDE_SUMMARIZATION_PROMPT` JSON schema description block

## Proposed Solution

Option A (preferred): Generate the JSON schema block in each prompt programmatically from `TumorBoardDocContent.model_json_schema()` and `SlideContent.model_json_schema()` at module load time. Remove the hand-written schema descriptions.

Option B (minimum viable): Add a pytest test that iterates `TumorBoardDocContent.model_fields` and `SlideContent.model_fields` and asserts each field name appears in the corresponding prompt string. The test fails at PR time if a field is added to the model without updating the prompt.

Also verify that `_fallback_doc_content` populates every required field in `TumorBoardDocContent` — missing required fields in the fallback will cause Pydantic validation errors at runtime.

## Acceptance Criteria

- [ ] A test fails if any `TumorBoardDocContent` field name is absent from `TUMOR_BOARD_DOC_PROMPT`
- [ ] A test fails if any `SlideContent` field name is absent from `SLIDE_SUMMARIZATION_PROMPT`
- [ ] OR: both prompt schema blocks are generated from `model_json_schema()` rather than hand-written (eliminates need for the tests)
- [ ] `_fallback_doc_content` populates all required fields defined in `TumorBoardDocContent`
