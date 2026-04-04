---
status: complete
priority: p1
issue_id: "061"
tags: [code-review, reliability, fhir, json, error-handling]
dependencies: []
---

## Problem Statement

`FhirClinicalNoteAccessor._read_note` has no `json.JSONDecodeError` handling. A malformed or non-JSON payload from the FHIR server will raise an uncaught exception that propagates through `asyncio.gather` in `read_all` (which uses `return_exceptions=False` by default). One bad note in a batch aborts the entire patient note fetch, and the exception may surface raw stack trace text to the LLM via Semantic Kernel's tool error reporting. This is inconsistent with the Fabric accessor, which was fixed in this PR to add JSONDecodeError fallback.

## Findings

- **File:** `src/data_models/fhir/fhir_clinical_note_accessor.py`, lines 183–186
- **Reported by:** security-sentinel, kieran-python-reviewer
- **Severity:** P1 — one malformed FHIR note breaks entire patient note load; inconsistent behavior vs. Fabric accessor

```python
# Current — no exception handling:
note_content = document_reference["content"][0]["attachment"]["data"]
note_json = json.loads(base64.b64decode(note_content).decode("utf-8"))
note_json['id'] = note_id
return json.dumps(note_json)
```

## Proposed Solutions

### Option A (Recommended): Mirror Fabric's fallback pattern

```python
note_content = base64.b64decode(
    document_reference["content"][0]["attachment"]["data"]
).decode("utf-8")
try:
    note_json = json.loads(note_content)
    note_json['id'] = note_id
except json.JSONDecodeError as e:
    logger.warning("Non-JSON FHIR note %s: %s — using plain text fallback", note_id, e)
    note_json = {
        "id": note_id,
        "text": note_content,
        "date": "",
        "note_type": "clinical note",
    }
return json.dumps(note_json)
```

### Option B: Skip malformed notes

Catch the exception and return `None`, then filter `None` values in `read_all`. More complex but avoids polluting the note list with plain-text-wrapped content.

## Technical Details

- **File:** `src/data_models/fhir/fhir_clinical_note_accessor.py`
- **Method:** `_read_note` (lines 176–186)
- **Related:** Fabric accessor's equivalent fix at lines 137–151 (added in this PR)

## Acceptance Criteria

- [ ] `_read_note` catches `json.JSONDecodeError` and logs a warning without `note_id` in the message
- [ ] Fallback dict matches the Fabric pattern (id, text, date="", note_type)
- [ ] `read_all` continues to completion even with one malformed note
- [ ] Behavior is consistent with `FabricClinicalNoteAccessor._read_note`

## Work Log

- 2026-04-02: Identified during code review of P1/P2 accessor fixes PR. Fabric was fixed in this PR; FHIR was missed.
