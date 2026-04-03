---
status: pending
priority: p2
issue_id: "070"
tags: [code-review, data-integrity, filter-utils, clinical-notes, string-handling]
dependencies: []
---

## Problem Statement

`filter_notes_by_keywords` in `clinical_note_filter_utils.py` wraps the text field lookup in `str()`:

```python
str(note.get("text", note.get("NoteText", note.get("note_text", "")))).lower()
```

If a note has `"text": None` (possible from malformed or partially constructed note dicts), `str(None)` produces `"none"` — a non-empty string that lowercases to `"none"`. A keyword search for `"none"` or any keyword that appears in `"none"` (e.g., `"on"`) would falsely match this note. The correct behavior is to treat a `None` text field as an empty string.

The same pattern exists in `grounded_clinical_note.py`:
```python
note_text = str(note_dict.get("text") or "")  # correct: or "" collapses None
```
The `or ""` guard is correct there. The filter utils do not use this guard.

## Findings

- **File:** `src/data_models/clinical_note_filter_utils.py`, line ~58
- **Reported by:** kieran-python-reviewer, code-simplicity-reviewer
- **Severity:** P2 — false keyword matches on notes with `None` text fields

## Proposed Solutions

### Option A (Recommended): Use `or ""` guard

```python
text = (
    note.get("text") or note.get("NoteText") or note.get("note_text") or ""
)
kw in str(text).lower()
```

The `or ""` chain short-circuits on the first truthy value and falls back to `""` for `None` or missing keys. This is the pattern already used correctly in `grounded_clinical_note.py`.

### Option B: Extract a helper

```python
def _note_text(note: dict) -> str:
    return str(note.get("text") or note.get("NoteText") or note.get("note_text") or "")
```

Use it in both `filter_notes_by_keywords` and any other place that looks up note text.

## Technical Details

- **File:** `src/data_models/clinical_note_filter_utils.py`, `filter_notes_by_keywords`
- **Related:** `grounded_clinical_note.py` uses the correct `or ""` pattern

## Acceptance Criteria

- [ ] `filter_notes_by_keywords` uses `or ""` guard so `None` text fields match no keywords
- [ ] `str(None)` can never produce `"none"` in any text field lookup in the filter utils
- [ ] Unit test: note with `"text": None` does not match any keyword

## Work Log

- 2026-04-02: Identified during code review. The `str()` coercion was added defensively but without the `or ""` guard, making it incorrect for `None` values.
