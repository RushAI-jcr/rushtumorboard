---
name: case-number-always-1-no-data-source
description: TumorBoardDocContent.case_number is hardcoded to 1 in the LLM prompt with no data source or user input path, so all generated documents show "Case 1"
type: code-review
status: pending
priority: p2
issue_id: 048
tags: [code-review, agent-native, data-source, user-input]
---

## Problem Statement

`TumorBoardDocContent.case_number` (`tumor_board_summary.py:27`) is the sequential case number for the tumor board meeting agenda. The LLM prompt instructs `"case_number": 1`. No agent has access to meeting schedule data — this field will always be 1 in all generated documents. Real tumor board handouts use sequential case numbers (Case 1, Case 2... for each patient presented). The `SlideContent` `patient_title` field has the same gap: always renders as "Case 1 — <GUID>".

## Findings

- `tumor_board_summary.py:27`: `TumorBoardDocContent.case_number` field defined
- LLM prompt instructs `"case_number": 1` (hardcoded literal in prompt)
- No agent, kernel function, or data source provides actual meeting schedule or case ordering information
- All generated Word documents and PPTX slides render "Case 1" regardless of the patient's actual position on the agenda
- `SlideContent.patient_title` inherits the same gap: always "Case 1 — <GUID>"
- Real GYN Tumor Board handouts at Rush use sequential case numbers per meeting

## Proposed Solutions

### Option A
Add `case_number` as an explicit parameter to `export_to_word_doc` and `export_to_pptx` kernel functions with `default=1`. Update ReportCreation agent instructions in `agents.yaml` to ask the user for the case number before generating exports. The agent can pass the user-supplied value through to the export functions.

**Pros:** Correct behavior when user supplies the case number; minimal code change; preserves default=1 for single-patient use cases; follows agent-native pattern of gathering missing inputs
**Cons:** Adds a conversational turn when the user doesn't know or care about case number; requires agents.yaml instruction update
**Effort:** Small (2-3 hours)
**Risk:** Low

### Option B
Document as a known limitation. Add a `# TODO: case_number always 1 — no meeting schedule data source` comment in `content_export.py` and `presentation_export.py`. Remove the hardcoded `1` from the prompt and use the Pydantic field default instead.

**Pros:** Zero code risk; honest documentation of the gap
**Cons:** Does not fix the problem; generated handouts remain incorrect for multi-patient meetings
**Effort:** Trivial
**Risk:** None

## Recommended Action

## Technical Details

**Affected files:**
- `src/data_models/tumor_board_summary.py` (line 27, `case_number` field)
- `src/plugins/content_export.py` (LLM prompt with hardcoded `"case_number": 1`)
- `src/plugins/presentation_export.py` (`patient_title` construction)
- `config/agents.yaml` (ReportCreation agent instructions)

## Acceptance Criteria

- [ ] `case_number` is no longer hardcoded to `1` in the LLM prompt
- [ ] Either: user can supply `case_number` via agent conversation and it is reflected in exported documents, OR the limitation is explicitly documented with a TODO comment
- [ ] `SlideContent.patient_title` renders the correct case number when one is provided
- [ ] Default behavior (case_number=1) preserved for single-patient use

## Work Log

- 2026-04-02: Identified in code review

## Resources

- Branch: fix/accessor-protocol-cache-quality-015-022
