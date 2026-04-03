---
status: pending
priority: p3
issue_id: "078"
tags: [code-review, data-integrity, fabric, dates, clinical-notes]
dependencies: [064]
---

## Problem Statement

In `FabricClinicalNoteAccessor._read_note`, when a non-JSON note is encountered, the fallback dict assigns a date of `date.today() - timedelta(days=30)`:

```python
target_date = date.today() - timedelta(days=30)
note_json = {
    "id": note_id,
    "text": note_content,
    "date": target_date.isoformat(),  # always "30 days ago"
    "type": "clinical note",
}
```

This date is arbitrary and misleading. Notes with unknown dates will be sorted as if they occurred 30 days before they were processed — potentially placing them in the middle of a patient's chronological note history rather than flagging them as undated. Agents constructing timelines may present this note with an incorrect date to clinicians.

The correct behavior is to use an empty string `""` for date when it's unknown, which all other accessors and the `_parse_date` function already handle gracefully.

Note: This is closely related to todo-064 (the `note_json = {}` sentinel fix). Both can be resolved in the same edit.

## Findings

- **File:** `src/data_models/fabric/fabric_clinical_note_accessor.py`, `_read_note` method
- **Reported by:** code-simplicity-reviewer
- **Severity:** P3 — misleading date in timeline construction for non-JSON Fabric notes

## Proposed Solutions

Replace `date.today() - timedelta(days=30)` with `""`:

```python
note_json = {
    "id": note_id,
    "text": note_content,
    "date": "",  # unknown date — handle gracefully
    "note_type": "clinical note",
}
```

Also remove the `timedelta` import if no longer used after this fix.

## Acceptance Criteria

- [ ] Non-JSON Fabric notes have `"date": ""` not an arbitrary date
- [ ] `from datetime import date, timedelta` — `timedelta` removed if unused (may keep `date` for other uses)
- [ ] `_parse_date("")` returns `datetime.min` (already handles empty string gracefully per existing test)

## Work Log

- 2026-04-02: Identified during code review. Resolving as part of todo-064 (which fixes the `note_json = {}` sentinel).
