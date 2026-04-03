---
status: pending
priority: p1
issue_id: "003"
tags: [code-review, security, path-traversal, hipaa]
dependencies: []
---

## Problem Statement

The path traversal guard in `CaboodleFileAccessor._read_file` uses `startswith` which is vulnerable to sibling-directory prefix collision:

```python
if not resolved.startswith(os.path.realpath(self.data_dir)):
```

If `self.data_dir` resolves to `/var/data/patient_data`, then a path like `/var/data/patient_data_exfil/evil` passes this check because `"/var/data/patient_data_exfil/evil".startswith("/var/data/patient_data")` is `True`. This is a well-documented Python path containment anti-pattern.

Additionally, `_read_legacy_json_sync` follows symlinks inside the `clinical_notes/` subdirectory without per-file containment verification — a symlink named `evil.json` pointing outside the data directory would be followed.

## Findings

- **File:** `src/data_models/epic/caboodle_file_accessor.py`
- **Lines:** 261, 331-347
- **Reported by:** security-sentinel
- **Severity:** P1 — path traversal in a HIPAA-regulated clinical data reader

## Proposed Solutions

### Option A (Recommended): Use `Path.is_relative_to()` 

```python
# caboodle_file_accessor.py _read_file — replace lines 259-262:
from pathlib import Path

patient_dir = os.path.join(self.data_dir, patient_id)
if not Path(patient_dir).resolve().is_relative_to(Path(self.data_dir).resolve()):
    raise ValueError(f"Invalid patient_id {patient_id!r}: path traversal detected")
```

`Path.is_relative_to()` is available Python 3.9+ and is immune to the prefix-collision issue. It appends `/` semantically, not as a string.

**For legacy JSON files — add per-file check:**
```python
# In _read_legacy_json_sync, after constructing filepath:
filepath = os.path.join(notes_dir, filename)
if not Path(filepath).resolve().is_relative_to(Path(notes_dir).resolve()):
    logger.warning("Skipping suspicious file path: %s", filename)
    continue
```

**Also fix the f-string with no interpolation in the current raise:**
```python
# Current:
raise ValueError(f"Invalid patient_id: path traversal detected")
# Fix:
raise ValueError(f"Invalid patient_id {patient_id!r}: path traversal detected")
```

- **Effort:** Small
- **Risk:** None — same logic, immune to prefix collision

## Recommended Action

Option A — use `Path.is_relative_to()` in both locations.

## Technical Details

- **Affected file:** `src/data_models/epic/caboodle_file_accessor.py` lines 259-262, 331-347
- **Root cause:** `str.startswith()` does not semantically check path containment

## Acceptance Criteria

- [ ] `_read_file` uses `Path.is_relative_to()` for path traversal check
- [ ] `_read_legacy_json_sync` validates each file path before opening
- [ ] Error message includes the offending patient_id value
- [ ] Test: `_read_file("../../../etc", "clinical_notes")` raises `ValueError`

## Work Log

- 2026-04-02: Identified by security-sentinel during code review
