---
name: mrn-attending-no-data-source-patient-safety
description: TumorBoardDocContent MRN and attending fields have no data source — LLM will hallucinate values on printed clinical handout
type: code-review
status: complete
priority: p1
issue_id: 038
tags: [code-review, patient-safety, agent-native, data-source]
---

## Problem Statement
`TumorBoardDocContent` (tumor_board_summary.py:29-30) adds `mrn: str` and `attending_initials: str` fields populated by the LLM. CaboodleFileAccessor uses patient GUIDs as its lookup key — MRN is a distinct Epic identifier not present in any of the 7 Caboodle CSV schemas. Attending physician assignment is likewise absent from all CSV files. The LLM cannot derive these from available data and will produce blank strings or hallucinated values. These fields appear on a printed clinical handout used in a live tumor board meeting — a wrong MRN or attending initials is a patient safety issue.

## Findings
- `src/data_models/tumor_board_summary.py:29-30`: `mrn: str` and `attending_initials: str` defined as LLM-populated fields with no grounded data source.
- `src/scenarios/default/tools/content_export/content_export.py:73-76`: These fields are rendered directly into the exported Word document that is printed for the live tumor board meeting.
- None of the 7 Caboodle CSV schemas (labs, imaging, pathology, medications, diagnoses, procedures, clinical notes) include PatientMRN or AttendingProvider columns.
- CaboodleFileAccessor lookup key is patient GUID (e.g., `XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX`), which is not the MRN.

## Proposed Solutions
### Option A
Add `demographics.csv` to the Caboodle export spec (PatientID, MRN, AttendingProvider, ClinicLocation, AdmissionStatus); add a `get_patient_demographics` tool to the PatientStatus agent to populate these fields from a trusted data source.

**Pros:** Fully automated; MRN and attending pulled from Epic source of truth; no manual step required
**Cons:** Requires Caboodle export change (DBAs), new tool implementation, and agent prompt update; large effort
**Effort:** Large
**Risk:** Medium (new data pipeline; must validate MRN mapping)

### Option B
Remove `mrn` and `attending_initials` from the printed document; add a comment in the template and code stating "requires manual entry before printing."

**Pros:** Eliminates hallucination risk immediately; safest short-term option; no data pipeline changes
**Cons:** Manual step for clinical staff before each meeting; fields must be tracked elsewhere
**Effort:** Small
**Risk:** Low

### Option C
Make the ReportCreation agent prompt the user for `mrn` and `case_number` before calling `export_to_word_doc`, storing responses as verified user input rather than LLM-generated values.

**Pros:** Keeps fields in document; grounds values in explicit human input; no Caboodle change needed
**Cons:** Adds friction to export workflow; user input still not validated against Epic; risk of typo
**Effort:** Medium
**Risk:** Medium

## Recommended Action
(leave blank)

## Technical Details
**Affected files:**
- `src/data_models/tumor_board_summary.py:29-30`
- `src/scenarios/default/tools/content_export/content_export.py:73-76`

## Acceptance Criteria
- [ ] No LLM-hallucinated MRN or attending value can appear on a printed tumor board handout
- [ ] If MRN is shown, it is sourced from a verified data source (Epic/Caboodle) or explicit user input — never LLM inference
- [ ] If Option B: Word template renders without blank-field artifacts and clinical staff are notified of the manual entry requirement
- [ ] If Option A: demographics.csv is validated against known patient GUIDs in the test dataset before production use

## Work Log
- 2026-04-02: Identified in code review

## Resources
- Branch: fix/accessor-protocol-cache-quality-015-022
