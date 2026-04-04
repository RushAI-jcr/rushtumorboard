---
name: dry-violation-filter-logic-duplicated-3x
description: get_clinical_notes_by_type and get_clinical_notes_by_keywords are byte-for-byte duplicated across three fallback accessor classes
type: code-review
status: complete
priority: p2
issue_id: 043
tags: [code-review, dry, architecture, maintainability]
---

## Problem Statement

`get_clinical_notes_by_type` and `get_clinical_notes_by_keywords` are byte-for-byte identical in three fallback accessor classes, totaling ~240 lines of duplicated code. Any bug fix or field name change must be applied in 3 places. Additionally, `get_lab_results`/`get_tumor_markers` stubs are duplicated (4 lines × 3 = 12 lines, with wrong docstrings), and the field lookup order subtly differs from `CaboodleFileAccessor` (`NoteType` vs `note_type` precedence).

## Findings

- `clinical_note_accessor.py:81-111`: `get_clinical_notes_by_type` and `get_clinical_notes_by_keywords` defined
- `fhir_clinical_note_accessor.py:212-252`: byte-for-byte duplicate of the above
- `fabric_clinical_note_accessor.py:151-181`: byte-for-byte duplicate of the above
- ~80 lines × 3 = 240 lines of duplicated filter logic
- `get_lab_results`/`get_tumor_markers` stubs duplicated across 3 classes: 4 lines × 3 = 12 lines, with incorrect docstrings
- Field lookup order differs from `CaboodleFileAccessor`: `NoteType` vs `note_type` key precedence is inconsistent, creating a latent bug if field names ever diverge

## Proposed Solutions

### Option A
Extract module-level helper functions into `src/data_models/clinical_note_filter_utils.py`: `filter_notes_by_type(notes, note_types)` and `filter_notes_by_keywords(notes, note_types, keywords)`. Each accessor delegates to these helpers. No inheritance required; any accessor can import and call the helpers independently.

**Pros:** No inheritance coupling; easy to test in isolation; single source of truth for filter logic; field lookup order can be standardized in one place
**Cons:** Requires updating imports in three files
**Effort:** Small (1-2 hours)
**Risk:** Low

### Option B
Create a `ClinicalNoteFilterMixin` class that all three accessors inherit from, providing the shared filter methods.

**Pros:** Keeps logic co-located with accessor classes; standard OOP pattern
**Cons:** Adds inheritance coupling to classes that currently use composition; mixin ordering can cause subtle MRO issues if accessor hierarchy grows
**Effort:** Small (1-2 hours)
**Risk:** Low-medium (MRO complexity)

## Recommended Action

Option A — module-level helper functions in `clinical_note_filter_utils.py`. No inheritance coupling needed, and the helpers are easier to unit test independently.

## Technical Details

**Affected files:**
- `src/data_access/clinical_note_accessor.py` (lines 81-111)
- `src/data_access/fhir_clinical_note_accessor.py` (lines 212-252)
- `src/data_access/fabric_clinical_note_accessor.py` (lines 151-181)
- New file: `src/data_models/clinical_note_filter_utils.py`

## Acceptance Criteria

- [ ] `filter_notes_by_type` and `filter_notes_by_keywords` extracted to shared utility module
- [ ] All three accessor classes delegate to the shared helpers
- [ ] Field lookup order (`NoteType` vs `note_type`) is consistent across all accessors
- [ ] `get_lab_results`/`get_tumor_markers` stubs have correct docstrings
- [ ] Existing tests pass without modification
- [ ] New unit tests for the shared filter helpers

## Work Log

- 2026-04-02: Identified in code review

## Resources

- Branch: fix/accessor-protocol-cache-quality-015-022
