---
name: CaboodleFileAccessor _read_file lacks file_type allowlist
description: _read_file constructs file paths from an unvalidated file_type parameter; adversarial input could read arbitrary files within data_dir
type: security
status: complete
priority: p2
issue_id: "016"
tags: [security, path-traversal, code-review]
---

## Problem Statement

`CaboodleFileAccessor._read_file(patient_id, file_type)` constructs the file path as:
```python
parquet_path = os.path.join(patient_dir, f"{file_type}.parquet")
csv_path = os.path.join(patient_dir, f"{file_type}.csv")
```

`file_type` is never validated against an allowlist. If an adversarial value like `../../other_patient/lab_results` is passed, the `os.path.join` would construct a path that escapes the intended file type constraint. The existing `is_relative_to(self._resolved_data_dir)` check protects against full path traversal to outside the data directory, but a `file_type` like `other_patient_id/lab_results` would read another patient's file within the same data_dir — a PHI cross-patient read.

**Current callers:** All callers in this codebase pass hardcoded string literals (`"clinical_notes"`, `"pathology_reports"`, etc.), so exploitation requires either a code change or a future caller that passes user-controlled input. The risk is currently low but grows as the codebase expands.

**Affected file:** `src/data_models/epic/caboodle_file_accessor.py`, `_read_file` method (~line 260)

## Proposed Solutions

### Option A: Allowlist at top of _read_file (Recommended)
```python
_VALID_FILE_TYPES = frozenset({
    "clinical_notes", "pathology_reports", "radiology_reports",
    "lab_results", "cancer_staging", "medications", "diagnoses",
})

async def _read_file(self, patient_id: str, file_type: str) -> list[dict]:
    if file_type not in _VALID_FILE_TYPES:
        raise ValueError(f"Invalid file_type {file_type!r}")
    ...
```

**Pros:** Simple, zero runtime overhead for valid calls, makes intent explicit
**Cons:** Requires updating allowlist when new file types are added
**Effort:** Small (5 lines)
**Risk:** None — all existing callers use valid types

### Option B: Use a Literal type annotation
Annotate `file_type` as `Literal["clinical_notes", "pathology_reports", ...]` so Pyright catches invalid calls at type-check time (no runtime guard needed for internal callers).

**Pros:** Zero runtime cost; catches mistakes at development time
**Cons:** No protection against dynamic/untrusted input at runtime
**Effort:** Small

## Acceptance Criteria
- [ ] `_read_file` validates `file_type` against an allowlist or Literal annotation
- [ ] All existing callers pass type check with no changes needed

## Work Log
- 2026-04-02: Identified by security-sentinel during code review. Current patient_id path traversal check does not cover cross-patient reads via adversarial file_type.
- 2026-04-02: Implemented and marked complete.
