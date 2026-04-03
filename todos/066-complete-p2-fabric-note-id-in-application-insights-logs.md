---
status: complete
priority: p2
issue_id: "066"
tags: [code-review, security, hipaa, phi, logging, azure-monitor]
dependencies: []
---

## Problem Statement

`FabricClinicalNoteAccessor._read_note` logs `note_id` in a `logger.warning` call:
```python
logger.warning("Non-JSON content for note %s: %s — using plain text fallback", note_id, e)
```

`note_id` is the Fabric `DocumentReference` resource GUID (e.g., `"3fa85f64-5717-4562-b3fc-2c963f66afa6"`). While this is a pseudonymous identifier, it can be cross-referenced against the Fabric workspace by anyone with workspace read access to identify the patient record. Azure Monitor (Application Insights) ingests all `WARNING`+ logs and stores them in Log Analytics, which has broader access than the clinical data store. Under HIPAA, data is PHI if it "could be used to identify an individual alone or in combination with other information."

The existing codebase convention (established after todo-001) is to log fallback layer/count information but never patient-linked identifiers.

## Findings

- **File:** `src/data_models/fabric/fabric_clinical_note_accessor.py`, line ~129
- **Reported by:** security-sentinel
- **Severity:** P2 — pseudonymous identifier in Azure Monitor; cross-referenceable to patient records

## Proposed Solutions

### Option A (Recommended): Replace note_id with structural description

```python
logger.warning(
    "Non-JSON content in Fabric DocumentReference (type=%s): %s — using plain text fallback",
    type(e).__name__, str(e)[:100],
)
```

### Option B: Log a hash of note_id

```python
import hashlib
note_id_hash = hashlib.sha256(note_id.encode()).hexdigest()[:8]
logger.warning("Non-JSON Fabric note [%s...]: %s", note_id_hash, e)
```

Option A is simpler and sufficient for debugging — the exception message contains enough context.

## Technical Details

- **File:** `src/data_models/fabric/fabric_clinical_note_accessor.py`
- **Affected log:** `logger.warning("Non-JSON content for note %s: %s...", note_id, e)`
- **Azure Monitor:** All WARNING+ logs → Application Insights → Log Analytics workspace

## Acceptance Criteria

- [ ] `note_id` is not emitted in any log statement in the Fabric accessor
- [ ] Warning log still provides enough context to identify the failure type for debugging
- [ ] Same pattern verified in FHIR accessor (when JSONDecodeError handling is added per todo-061)

## Work Log

- 2026-04-02: Identified during security review. The codebase convention from todo-001 fix is to log structural data, not patient-linked identifiers.
