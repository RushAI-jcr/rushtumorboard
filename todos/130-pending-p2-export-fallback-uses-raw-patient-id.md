---
status: pending
priority: p2
issue_id: "130"
tags: [code-review, security, phi, clinical-safety]
dependencies: []
---

# 130 — Fallback export paths embed raw `patient_id` and unsummarized clinical text in documents

## Problem Statement

When LLM summarization fails, `_fallback_doc_content` in `content_export.py:451-486` sets `patient_last_name=str(pid)` where `pid` is the raw `patient_id` — which in production is an Epic Caboodle GUID or MRN. This value is rendered into the Word document and uploaded to blob storage. The fallback also includes up to 500 chars of raw `oncologic_history` and 300 chars of raw `surgical_findings`, bypassing the LLM's clinical shorthand summarization. In `presentation_export.py`, the PPTX fallback similarly uses the raw `patient_id` string. A clinician printing the fallback document would see a raw identifier in the patient name field and raw clinical text without clinical summarization.

## Findings

- `content_export.py:453` — `patient_last_name=str(pid)` in `_fallback_doc_content`; `pid` is raw Epic identifier
- `presentation_export.py:366` — PPTX fallback uses raw `patient_id` in slide content

## Proposed Solution

1. Replace raw `patient_id` in both fallback paths with a safe placeholder: `"[VERIFY — LLM UNAVAILABLE]"`.
2. Set the document title / slide title to include a visible watermark: `"[SUMMARIZATION FAILED — MANUAL REVIEW REQUIRED]"`.
3. Cap fallback `oncologic_history` content to ≤200 characters with a truncation indicator.
4. Ensure the blob filename does not include the raw `patient_id` when the fallback path is taken (use `"fallback"` or a timestamp instead).

## Acceptance Criteria

- [ ] Fallback Word documents do not contain the raw `patient_id` as a display name field
- [ ] Fallback PPTX slides do not contain the raw `patient_id` in any rendered text field
- [ ] Both fallback documents include a prominent title-level watermark indicating LLM summarization failure
- [ ] Oncologic history content in the fallback Word document is capped to ≤200 characters
- [ ] Fallback blob filename does not embed the raw `patient_id`
