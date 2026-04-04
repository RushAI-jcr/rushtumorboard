---
status: complete
priority: p2
issue_id: "020"
tags: [code-review, architecture, maintainability, constants, note-types]
dependencies: [017]
---

## Problem Statement

Epic Caboodle NoteType strings are defined in at least 5 separate places across the codebase:

1. `tumor_markers.py` — `_MARKER_NOTE_TYPES` list
2. `oncologic_history_extractor.py` — `_RELEVANT_NOTE_TYPES` set
3. `radiology_extractor.py` — `layer2_note_types`, `layer3_note_types` tuples
4. `pathology_extractor.py` — `layer2_note_types`, `layer3_note_types` tuples
5. `patient_data.py` — `TIMELINE_NOTE_TYPES` (55-entry filter)

When a new NoteType is confirmed in real Rush Epic data (as happened with "ED Provider Notes", "Procedure Notes"), it must be updated in all 5 places. This has already caused drift — some files got updated and others didn't.

## Findings

- **Files:** All tool files under `src/scenarios/default/tools/`
- **Reported by:** code-simplicity-reviewer, architecture-strategist
- **Severity:** P2 — maintenance burden; drift already observed between files

## Proposed Solutions

### Option A (Recommended): Centralize in `validation.py` or a new `note_type_constants.py`
```python
# src/scenarios/default/tools/note_type_constants.py

# Confirmed in real Rush University Epic Caboodle exports (2025)
PROGRESS_NOTE_TYPES = ("Progress Notes", "Progress Note")
CONSULT_NOTE_TYPES = ("Consults", "Consult Note", "Oncology Consultation")
OPERATIVE_NOTE_TYPES = ("Operative Report", "Brief Op Note", "Procedure Note", "Procedure Notes", "Procedures")
DISCHARGE_TYPES = ("Discharge Summary",)
HP_TYPES = ("H&P", "History and Physical")
ED_NOTE_TYPES = ("ED Provider Notes", "ED Notes")
UNMAPPED_TYPES = ("Unmapped External Note", "Patient Instructions", "Addendum Note")
ASSESSMENT_PLAN_TYPES = ("Assessment & Plan Note", "Multidisciplinary Tumor Board")

# Composite sets for common use cases
GENERAL_CLINICAL_NOTE_TYPES = PROGRESS_NOTE_TYPES + CONSULT_NOTE_TYPES + HP_TYPES + DISCHARGE_TYPES + ED_NOTE_TYPES
ALL_NOTE_TYPES = GENERAL_CLINICAL_NOTE_TYPES + OPERATIVE_NOTE_TYPES + UNMAPPED_TYPES + ASSESSMENT_PLAN_TYPES
```
- **Pros:** Single source of truth; one edit propagates everywhere; validates against confirmed Rush data
- **Cons:** Requires updating all 5 files to import from new module
- **Effort:** Medium (refactor imports, verify no behavior change)
- **Risk:** Low

### Option B: Consolidate into `validation.py` (already imported everywhere)
Add note type constants to the existing shared utility module.
- **Pros:** One less file; already imported in most tools
- **Cons:** Mixes validation logic with constants

## Recommended Action

Option A — create `note_type_constants.py`. Note type values are domain knowledge (Rush Epic configuration), not code logic, and deserve their own module.

## Technical Details

- **Affected files:** `tumor_markers.py`, `oncologic_history_extractor.py`, `radiology_extractor.py`, `pathology_extractor.py`, `patient_data.py`
- **Confirmed Rush NoteTypes (2025):** "Progress Notes", "Consults", "ED Provider Notes", "Patient Instructions" — verified in real patient CSVs
- **NOT confirmed in real data:** "H&P", "Operative Report" (present in synthetic data only)

## Acceptance Criteria

- [ ] Single `note_type_constants.py` (or equivalent) contains all NoteType string constants
- [ ] All 5 tool files import from the centralized module
- [ ] Adding a new NoteType requires editing exactly one file
- [ ] Existing test cases pass (behavior unchanged)

## Work Log

- 2026-04-02: Identified by code-simplicity-reviewer and architecture-strategist during code review
- 2026-04-02: Resolved — note_type_constants.py already exists in tools/ with all canonical NoteType constants.
