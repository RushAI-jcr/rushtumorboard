---
name: patient-id-map-wrong-return-type-annotation
description: get_patient_id_map annotated as List[str] but returns a dict — lying type signature propagates incorrect expectations
type: code-review
status: complete
priority: p1
issue_id: 041
tags: [code-review, typing, correctness]
---

## Problem Statement
`fhir_clinical_note_accessor.py:129`: `async def get_patient_id_map(self) -> List[str]` but the method body returns a `dict`. The docstring also says "list of patient IDs." This is a lie in the type signature. Any caller that type-checks against this signature will have incorrect expectations. If the Protocol ever includes this method, the mismatch will silently propagate incorrect types.

## Findings
- `src/data_models/fhir/fhir_clinical_note_accessor.py:129`: Method signature declares `-> List[str]`; method body constructs and returns a `dict`. The docstring repeats the incorrect claim ("list of patient IDs"). Mypy/pyright will flag callers that iterate over the return value expecting strings rather than key-value pairs.

## Proposed Solutions
### Option A
Change return type annotation to `-> dict[str, str]` and update the docstring to accurately describe the mapping (e.g., "Returns a dict mapping patient FHIR ID to MRN or other identifier").

**Pros:** Type signature matches implementation; no behavior change; one-line fix plus docstring update
**Cons:** None
**Effort:** Small
**Risk:** Low

## Recommended Action
(leave blank)

## Technical Details
**Affected files:**
- `src/data_models/fhir/fhir_clinical_note_accessor.py:129`

## Acceptance Criteria
- [ ] Return type annotation matches the actual return value type
- [ ] Docstring accurately describes the dict structure (key type, value type, and semantic meaning)
- [ ] Mypy/pyright reports no type error for this method or its callers
- [ ] If the Protocol includes `get_patient_id_map`, the Protocol's return type annotation is updated to match

## Work Log
- 2026-04-02: Identified in code review

## Resources
- Branch: fix/accessor-protocol-cache-quality-015-022
