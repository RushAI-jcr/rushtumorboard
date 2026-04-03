---
status: pending
priority: p3
issue_id: "074"
tags: [code-review, style, python, typing, annotations]
dependencies: []
---

## Problem Statement

`from __future__ import annotations` is present in `clinical_note_filter_utils.py`, `presentation_export.py`, and `content_export.py`, but absent from `fhir_clinical_note_accessor.py` and `fabric_clinical_note_accessor.py`. All five files use Python 3.12 union syntax (`X | Y`, `list[str]`, `dict[str, str]`). In Python 3.12, `from __future__ import annotations` is not required for these features, but the inconsistency in the same PR signals the import was added without a project-wide convention decision.

## Findings

- **Files:** `fhir_clinical_note_accessor.py`, `fabric_clinical_note_accessor.py` (missing)
- **Files:** `clinical_note_filter_utils.py`, `presentation_export.py`, `content_export.py` (present)
- **Reported by:** kieran-python-reviewer
- **Severity:** P3 — style inconsistency; no functional impact on Python 3.12

## Proposed Solutions

### Option A: Remove `from __future__ import annotations` from new files
Since Python 3.12 supports all the annotation syntax used, remove the import from `clinical_note_filter_utils.py` and `presentation_export.py` to match the existing codebase convention (most files do not have it).

### Option B: Add it everywhere
Establish a project-wide convention to include it in all files for forward-compatibility. Requires touching ~20 files.

Option A is preferred — the new files should match the existing convention.

## Acceptance Criteria

- [ ] `from __future__ import annotations` usage is consistent across all files modified in this PR

## Work Log

- 2026-04-02: Identified during code review.
