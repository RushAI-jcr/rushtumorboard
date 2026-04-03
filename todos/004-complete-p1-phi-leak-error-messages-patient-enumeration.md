---
status: complete
priority: p1
issue_id: "004"
tags: [code-review, security, hipaa, phi, error-handling]
dependencies: []
---

## Problem Statement

Two PHI leak vectors in error paths in `patient_data.py`:

1. **Exception text returned to LLM/user** (lines 125-126, 189-190):
   ```python
   return f"Error parsing timeline response: {e}"    # e = pydantic.ValidationError
   return f"Error parsing answer response: {e}"      # e = json.JSONDecodeError
   ```
   Pydantic validation errors include field names, field values, and schema details. If the LLM-generated JSON accidentally echoes clinical content in unexpected fields, this propagates fragments of that content to the user via the error message.

2. **Full patient list enumerated in error response** (lines 72-75):
   ```python
   patients = await self.data_access.clinical_note_accessor.get_patients()
   return f"Invalid patient ID: {patient_id}. Choose from following patient IDs: {', '.join(patients)}"
   ```
   On any invalid or unavailable patient ID, the full list of all patient GUIDs in the data directory is returned to the LLM and potentially surfaced in the chat response. In a system holding real patient GUIDs, this is a PHI enumeration disclosure.

## Findings

- **File:** `src/scenarios/default/tools/patient_data.py`
- **Lines:** 72-75, 125-126, 189-190
- **Reported by:** security-sentinel
- **Severity:** P1 — PHI disclosure in error paths

## Proposed Solutions

### Option A (Recommended): Generic error messages

**Lines 72-75:**
```python
# Remove the patient enumeration:
return "Invalid or unavailable patient ID. Please verify and try again."
```

**Lines 125-126 and 189-190:**
```python
# Remove exception content from user-facing return:
logger.error("Failed to parse timeline response for patient %s", patient_id, exc_info=True)
return "Error processing timeline. Please try again."

logger.error("Failed to parse answer response for patient %s", patient_id, exc_info=True)
return "Error processing response. Please try again."
```

The stack trace is preserved in logs (via `exc_info=True`) without exposing it to the user.

- **Effort:** Small
- **Risk:** None — errors are still logged; user gets a safe generic message

## Recommended Action

Option A — generic error messages, log with `exc_info=True`.

## Technical Details

- **Affected file:** `src/scenarios/default/tools/patient_data.py`
- **Lines:** 72-75, 125-126, 189-190

## Acceptance Criteria

- [ ] Error response at line 72-75 does not include `patients` list
- [ ] Error response at line 126 does not include `{e}` exception text
- [ ] Error response at line 190 does not include `{e}` exception text
- [ ] Errors still logged with `exc_info=True` for debuggability

## Work Log

- 2026-04-02: Identified by security-sentinel during code review
