---
status: pending
priority: p2
issue_id: "014"
tags: [code-review, python-quality, api-contract]
dependencies: ["013"]
---

## Problem Statement

`patient_data.py`'s `@kernel_function` entry points return plain strings on validation failure, while all 4 extractor plugins return `json.dumps({"error": "..."})`. This breaks the implicit API contract that callers can always `json.loads()` the result.

```python
# patient_data.py — inconsistent:
if not _is_valid(patient_id):
    return "Invalid patient ID"          # plain string — not JSON

# All 4 extractors — consistent:
if not _PATIENT_ID_RE.fullmatch(patient_id):
    return json.dumps({"error": "Invalid patient ID."})   # JSON
```

The Semantic Kernel orchestrator or downstream agents that call both `PatientHistory` and `Pathology` plugins may attempt `json.loads()` on the result and crash on the plain-string case.

## Findings

- **File:** `src/scenarios/default/tools/patient_data.py` lines ~74, ~128, ~192 (three `@kernel_function` methods)
- **Reported by:** code-simplicity-reviewer
- **Severity:** P2 — API contract bug; could cause orchestrator crash on invalid patient ID

## Proposed Solution

In `patient_data.py`, change all three validation guards to return JSON:
```python
if not validate_patient_id(patient_id):
    return json.dumps({"error": "Invalid patient ID."})
```

Note: `json` is already imported in `patient_data.py`. This change also aligns with todo 013 (centralized `validate_patient_id`).

- **Effort:** Small (3 lines changed)
- **Risk:** None — error path only; changes string return to JSON on invalid input

## Acceptance Criteria

- [ ] All `@kernel_function` entry points in `patient_data.py` return `json.dumps({"error": ...})` on invalid patient ID
- [ ] No `@kernel_function` returns a plain string (non-JSON) anywhere in the tools directory
- [ ] `load_patient_data`, `create_timeline`, `process_prompt` all consistent

## Work Log

- 2026-04-02: Identified by code-simplicity-reviewer during P1 re-review
