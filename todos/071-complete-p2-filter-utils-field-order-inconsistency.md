---
status: pending
priority: p2
issue_id: "071"
tags: [code-review, data-integrity, filter-utils, clinical-notes, field-naming]
dependencies: []
---

## Problem Statement

The field lookup order for note text differs between the shared filter utilities and the Caboodle accessor:

- **`clinical_note_filter_utils.filter_notes_by_keywords`**: checks `text` → `NoteText` → `note_text`
- **`CaboodleFileAccessor.get_clinical_notes_by_keywords`**: checks `NoteText` → `note_text` → `text`

If a note has both a `text` key and a `NoteText` key (possible if a normalization step adds `text` while the original Epic Caboodle CSV key `NoteText` is also preserved), the two implementations will use different values. Keyword matches on Caboodle raw rows via the shared utils would check `text` first (wrong order for raw Caboodle data) while Caboodle's own filter checks `NoteText` first (correct for Epic schema).

The same inconsistency exists for note_type lookup in `filter_notes_by_type`: utils checks `note_type` → `NoteType`; Caboodle checks `NoteType` → `note_type`. For the raw Caboodle CSV rows (which use `NoteType` PascalCase), the utils would fall through to the second key unnecessarily.

## Findings

- **File:** `src/data_models/clinical_note_filter_utils.py`, lines 21–22 (type), 54–59 (text)
- **File:** `src/data_models/epic/caboodle_file_accessor.py` (type: NoteType first; text: NoteText first)
- **Reported by:** architecture-strategist, code-simplicity-reviewer
- **Severity:** P2 — latent data mismatch; notes with both key spellings produce different results across backends

## Proposed Solutions

### Option A (Recommended): Align shared utils to Epic/Caboodle priority (NoteType/NoteText first)

Change in `clinical_note_filter_utils.py`:
```python
# filter_notes_by_type: NoteType → note_type (matches Caboodle schema)
note.get("NoteType", note.get("note_type", "")).lower()

# filter_notes_by_keywords: NoteText → note_text → text (matches Caboodle schema)
note.get("NoteText") or note.get("note_text") or note.get("text") or ""
```

The primary backend is Epic/Caboodle which uses PascalCase keys. FHIR/Fabric notes that use snake_case `text` would still work via fallback. This aligns the shared utils with the dominant schema.

### Option B: Normalize at ingestion

Add a normalization step in each accessor that ensures all returned notes use a consistent field schema (e.g., always lowercase `note_type` and `text`). More work but eliminates the field aliasing complexity everywhere.

## Technical Details

- **Files:** `src/data_models/clinical_note_filter_utils.py`, `src/data_models/epic/caboodle_file_accessor.py`
- **Note:** In practice, Caboodle uses its own filter logic and doesn't call the shared utils. The mismatch would only matter if the shared utils are ever called directly with raw Caboodle rows.

## Acceptance Criteria

- [ ] Field lookup order in shared utils matches Caboodle/Epic schema priority (PascalCase first)
- [ ] FHIR and Fabric notes still work via fallback to snake_case keys
- [ ] Comment in `clinical_note_filter_utils.py` documents the key priority rationale
- [ ] Unit test covering notes with only `NoteType`/`NoteText` (Caboodle shape) and notes with only `note_type`/`text` (FHIR shape)

## Work Log

- 2026-04-02: Identified during architecture and simplicity review. The mismatch is latent — it only matters if raw Caboodle rows are passed to the shared utils, which doesn't happen in the current codebase.
