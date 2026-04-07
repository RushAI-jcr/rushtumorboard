---
status: pending
priority: p3
issue_id: "223"
tags: [code-review, architecture, type-safety]
dependencies: []
---

# Protocol Lacks @runtime_checkable and Accessor Tests

## Problem Statement
`ClinicalNoteAccessorProtocol` provides static type checking but no runtime verification. Not decorated with `@runtime_checkable`. No unit tests for Fabric or FHIR accessors — stub mixin behavior (returning empty lists) has never been tested in integration context. `getattr(accessor, self.accessor_method)` in `MedicalReportExtractorBase` bypasses static checking.

## Findings
- **File**: `src/data_models/clinical_note_accessor_protocol.py` — no `@runtime_checkable`
- **File**: `src/scenarios/default/tools/medical_report_extractor.py:100` — string-based `getattr` dispatch
- **File**: `src/tests/` — no Fabric/FHIR accessor tests with mocked HTTP backends
- Protocol returns `list[dict]` everywhere — should be `list[dict[str, str]]` minimum

## Proposed Solutions
1. Add `@runtime_checkable` to Protocol
2. Add `isinstance()` check in factory
3. Add `__init_subclass__` to validate `accessor_method` in `MedicalReportExtractorBase`
4. Create `TestFabricStubBehavior` test class with mocked HTTP

## Acceptance Criteria
- [ ] Protocol is `@runtime_checkable`
- [ ] Factory validates accessor satisfies protocol at startup
- [ ] Fabric/FHIR accessors have unit tests with mocked backends
