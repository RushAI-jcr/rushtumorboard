---
status: pending
priority: p3
issue_id: "079"
tags: [code-review, architecture, module-organization, utils]
dependencies: []
---

## Problem Statement

`clinical_note_filter_utils.py` is located in `src/data_models/` alongside accessor classes, protocol definitions, and Pydantic models. The filter functions are pure algorithmic helpers with no domain state, no models, and no I/O — they belong in `utils/` alongside `logging_http_client.py`.

The existing sub-package convention inside `data_models/` is `epic/`, `fhir/`, `fabric/` — backend-specific packages. A generic utility module does not fit this namespace.

## Findings

- **Current location:** `src/data_models/clinical_note_filter_utils.py`
- **Better location:** `src/utils/clinical_note_filter_utils.py`
- **Reported by:** architecture-strategist
- **Severity:** P3 — discoverability and organizational correctness

## Proposed Solutions

Move `src/data_models/clinical_note_filter_utils.py` → `src/utils/clinical_note_filter_utils.py`.

Update import paths in:
- `src/data_models/clinical_note_accessor.py`
- `src/data_models/fhir/fhir_clinical_note_accessor.py`
- `src/data_models/fabric/fabric_clinical_note_accessor.py`

## Acceptance Criteria

- [ ] File moved to `src/utils/clinical_note_filter_utils.py`
- [ ] All three accessor imports updated to `from utils.clinical_note_filter_utils import ...`
- [ ] No remaining references to `data_models.clinical_note_filter_utils`

## Work Log

- 2026-04-02: Identified during architecture review.
