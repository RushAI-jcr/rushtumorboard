---
status: pending
priority: p2
issue_id: "124"
tags: [code-review, agent-native, reliability, clinical-safety]
dependencies: []
---

# 124 — Fallback and template-not-found paths do not use `ERROR_TYPE:` prefix — ReportCreation reports false success

## Problem Statement

Two failure paths do not use the `ERROR_TYPE:` prefix that the ReportCreation agent is instructed to parse:

(A) When LLM summarization fails or times out in `content_export.py` and `presentation_export.py`, both tools return a success-looking HTML download link wrapping fallback content. ReportCreation parses this as a successful export and reports success to the Orchestrator — even though the document contains `[FALLBACK]` placeholders. A clinician could print or present a tumor board handout with placeholder content without any system-level warning.

(B) When the Word template file is not found, `content_export.py` returns `f"Error: Word template not found at {doc_template_path}"` — without an `ERROR_TYPE:` prefix. ReportCreation's error-handling logic checks for `ERROR_TYPE:` and will miss this condition, again reporting ambiguous or false success.

## Findings

- `presentation_export.py` — LLM summarization exception/fallback paths; returns clean download URL
- `content_export.py` — LLM summarization exception/fallback paths; returns clean download URL
- `content_export.py:230-232` — template-not-found branch returns unstructured error string without `ERROR_TYPE:` prefix

## Proposed Solution

(A) When the fallback path is taken after an LLM summarization failure, return a string that either:
- Starts with `ERROR_TYPE: RENDER_DEGRADED\n` followed by the download link and a message explaining LLM failure, OR
- Embeds a prominent `[SUMMARIZATION FAILED — MANUAL REVIEW REQUIRED]` watermark in the document title and filename so it is visible to the clinician even if ReportCreation reports success.

(B) Change template-not-found to: `"ERROR_TYPE: RENDER_FAILED\nWord template not found at {doc_template_path}"`.

## Acceptance Criteria

- [ ] LLM summarization fallback in `content_export.py` includes `ERROR_TYPE: RENDER_DEGRADED` or a document-level failure watermark visible to the end user
- [ ] LLM summarization fallback in `presentation_export.py` includes the same signal
- [ ] Template-not-found error in `content_export.py` uses `ERROR_TYPE: RENDER_FAILED` prefix
- [ ] ReportCreation agent can detect and surface degraded or failed exports rather than reporting false success
