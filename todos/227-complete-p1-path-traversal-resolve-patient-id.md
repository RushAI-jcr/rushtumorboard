---
status: complete
priority: p1
issue_id: "227"
tags: [code-review, security]
dependencies: []
---

# Path Traversal Guard Missing in resolve_patient_id Fast Path

## Problem Statement

`resolve_patient_id` in `caboodle_file_accessor.py` has a fast path that checks `if (self.base_path / identifier).is_dir()` without validating that the resolved path stays within `base_path`. A crafted identifier like `../../etc` would pass the directory check and return a path outside the patient data directory.

## Findings

**Flagged by:** Security Sentinel (MEDIUM)

**File:** `src/data_models/epic/caboodle_file_accessor.py` — `resolve_patient_id()`

```python
async def resolve_patient_id(self, identifier: str) -> str:
    # Fast path: identifier is already a folder name
    if (self.base_path / identifier).is_dir():
        return identifier  # No traversal check!
    ...
```

Note: This is different from todo 197 which fixed `local_dev_stubs.py`. This is the production accessor.

## Proposed Solutions

### Option A: resolve() + startswith check (Recommended)
```python
async def resolve_patient_id(self, identifier: str) -> str:
    candidate = (self.base_path / identifier).resolve()
    base_resolved = self.base_path.resolve()
    if candidate.is_dir() and str(candidate).startswith(str(base_resolved)):
        return identifier
    ...
```
- Effort: Small | Risk: None

## Acceptance Criteria

- [ ] Fast path validates resolved path is within base_path
- [ ] `../../` style identifiers are rejected
- [ ] Normal GUID identifiers continue to work

## Work Log

- 2026-04-09: Created from Phase 2 code review (Security Sentinel)
