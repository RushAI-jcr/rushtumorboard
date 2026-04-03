---
status: pending
priority: p2
issue_id: "128"
tags: [code-review, simplicity, quality]
dependencies: []
---

# 128 — Dead legacy methods in `ContentExportPlugin` inflate audit surface

## Problem Statement

`ContentExportPlugin` contains four methods marked "kept for backward compatibility" that are never called from the current `export_to_word_doc` code path: `_get_patient_images`, `_load_patient_timeline`, `_load_research_papers`, and `_get_clinical_trials`. These methods reference `self.chat_ctx.patient_data` and `self.chat_ctx.output_data`, which belong to a blob-based workflow that no longer exists. The dead code accounts for approximately 55 unmaintained lines in a PHI-handling service — expanding the security audit surface without providing any functionality. The `PatientTimeline` import at `content_export.py:43` is also used only by this dead code.

## Findings

- `content_export/content_export.py:490-542` — four dead methods: `_get_patient_images`, `_load_patient_timeline`, `_load_research_papers`, `_get_clinical_trials`
- `content_export.py:43` — `PatientTimeline` import, only referenced by dead code

## Proposed Solution

1. Search the entire codebase for call sites of `_get_patient_images`, `_load_patient_timeline`, `_load_research_papers`, and `_get_clinical_trials` — confirm no callers exist outside `ContentExportPlugin`.
2. Remove all four methods.
3. Remove the `PatientTimeline` import.
4. Run the test suite to confirm no regressions.

## Acceptance Criteria

- [ ] `_get_patient_images`, `_load_patient_timeline`, `_load_research_papers`, and `_get_clinical_trials` are removed from `ContentExportPlugin`
- [ ] `PatientTimeline` import is removed from `content_export.py`
- [ ] No remaining references to the four removed methods anywhere in the codebase
- [ ] Test suite passes after removal
