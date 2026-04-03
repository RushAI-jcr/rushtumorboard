---
status: pending
priority: p1
issue_id: "064"
tags: [code-review, reliability, fabric, data-integrity, error-handling]
dependencies: []
---

## Problem Statement

`FabricClinicalNoteAccessor._read_note` initializes `note_json = {}` before the try/except block. When `note_content` is an empty string (possible from a base64-decoded empty FHIR attachment), `json.loads("")` raises `JSONDecodeError`, and the except block's `if note_content:` guard is falsy — so the fallback assignment is skipped. `json.dumps({})` is returned silently. This empty dict accumulates in `read_all`'s notes list without any warning.

Downstream, `filter_notes_by_type` passes the empty dict through to keyword/type matching: `{}.get("note_type", ...)` returns `""`, which never matches any type set, so the empty note is silently excluded from all filtering. This causes data loss without any signal.

## Findings

- **File:** `src/data_models/fabric/fabric_clinical_note_accessor.py`, lines 124–151 (current)
- **Reported by:** kieran-python-reviewer, code-simplicity-reviewer
- **Severity:** P1 — silent data loss; `{}` returned for empty/malformed Fabric notes

```python
# Current problematic code:
note_json = {}   # sentinel that leaks as return value on empty content
try:
    note_json = json.loads(note_content)
    note_json['id'] = note_id
except json.JSONDecodeError as e:
    logger.warning("Non-JSON content for note %s: %s — using plain text fallback", note_id, e)
    if note_content:   # <-- falsy for empty string, skips fallback!
        target_date = date.today() - timedelta(days=30)
        note_json = { "id": note_id, "text": note_content, "date": target_date.isoformat(), ... }
return json.dumps(note_json)  # returns '{}' if note_content was empty
```

## Proposed Solutions

### Option A (Recommended): Remove sentinel, unconditional fallback

```python
try:
    note_json = json.loads(note_content)
    note_json['id'] = note_id
except json.JSONDecodeError as e:
    logger.warning("Non-JSON Fabric note %s: %s — using plain text fallback", note_id, e)
    note_json = {
        "id": note_id,
        "text": note_content,
        "date": "",
        "note_type": "clinical note",
    }
return json.dumps(note_json)
```

Also removes:
- `note_json = {}` initialization (dead code)
- `if note_content:` guard (unnecessary — always true when JSONDecodeError raises since empty string would still parse as valid JSON "" or raise a different error)
- `date.today() - timedelta(days=30)` misleading fallback date (replaced with `""`)
- `timedelta` import if no longer used elsewhere

## Technical Details

- **File:** `src/data_models/fabric/fabric_clinical_note_accessor.py`
- **Method:** `_read_note` (lines 119–151 in current version)
- **Also:** Remove `timedelta` from `from datetime import date, timedelta` if unused after fix

## Acceptance Criteria

- [ ] `_read_note` never returns `json.dumps({})` — always returns a dict with at least `id` and `text` keys
- [ ] `note_json = {}` sentinel initialization removed
- [ ] `if note_content:` guard inside except block removed
- [ ] Fallback date is `""` not `date.today() - timedelta(days=30)`
- [ ] `timedelta` import removed if no longer needed
- [ ] Warning log does not contain patient_id (note_id is borderline acceptable per PHI review)

## Work Log

- 2026-04-02: Identified during code review. Code simplicity and Kieran reviewer both flagged this pattern. The empty dict sentinel is a classic defensive-default anti-pattern that silently leaks as a return value.
