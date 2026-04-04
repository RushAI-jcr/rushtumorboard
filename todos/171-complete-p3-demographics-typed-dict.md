---
status: pending
priority: p3
issue_id: "171"
tags: [code-review, python, type-safety]
dependencies: ["165"]
---

# Consider TypedDict or Pydantic Model for Demographics

## Problem Statement

`patient_demographics` is typed as `dict | None` on ChatContext. Demographics contain PHI fields (MRN, PatientName, DOB, Sex) consumed in 4+ locations that all assume specific key names. An untyped dict provides no IDE autocompletion, no validation, and no protection against schema drift.

While `dict | None` is consistent with existing ChatContext conventions, the project uses Pydantic models elsewhere (TumorBoardDocContent, SlideContent). A TypedDict would be the minimum improvement.

## Findings

- **Source**: Python Reviewer (CRITICAL), Architecture Strategist (acceptable but noted)
- **Files**: `src/data_models/chat_context.py:16`, `src/data_models/epic/caboodle_file_accessor.py:271`

## Proposed Solutions

### Option A: TypedDict (Minimal)
```python
class PatientDemographics(TypedDict, total=False):
    PatientID: str
    MRN: str
    PatientName: str
    DOB: str
    Sex: str
```

### Option B: Pydantic BaseModel (Full validation)
```python
class PatientDemographics(BaseModel):
    patient_id: str = ""
    mrn: str = ""
    patient_name: str = ""
    dob: str = ""
    sex: str = ""
```

## Acceptance Criteria

- [ ] Demographics have typed structure (TypedDict or Pydantic)
- [ ] Consumers get IDE autocompletion on field names

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-04-04 | Code review finding | Python Reviewer flagged; Architecture Strategist noted acceptable for now |
