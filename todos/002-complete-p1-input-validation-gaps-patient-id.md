---
status: complete
priority: p1
issue_id: "002"
tags: [code-review, security, hipaa, input-validation, path-traversal]
dependencies: []
---

## Problem Statement

Three separate input validation gaps allow untrusted `patient_id` values to flow into filesystem operations:

1. **`create_timeline` bypasses `_is_valid` entirely** (`patient_data.py:78`) — the LLM orchestrator can invoke this function with any string, including path-traversal payloads. `load_patient_data` and `process_prompt` validate; `create_timeline` does not.

2. **`_is_valid` uses `re.match` (prefix-only)** (`patient_data.py:38-40`) — `re.match` only requires the pattern to match at the start of the string. Input like `abc/../../etc/passwd` passes validation because `abc` matches `\w+` and the function stops there. The real defense is the `os.path.realpath` + `startswith` check in `_read_file`, but the validation function itself is ineffective.

3. **All `@kernel_function` entry points in extractor plugins lack patient ID validation** — `extract_pathology_findings`, `extract_radiology_findings`, `extract_oncologic_history`, `get_tumor_marker_trend`, `get_all_tumor_markers` all pass `patient_id` directly to internal methods without validation. Only `patient_data.py` validates.

## Findings

- **Files:** `src/scenarios/default/tools/patient_data.py:38-40, 78` and all `@kernel_function` entry points in extractor plugins
- **Reported by:** security-sentinel
- **Severity:** P1 — defense-in-depth violation in a HIPAA system

## Proposed Solutions

### Option A (Recommended): Fix validation function + add to all entry points

**Fix `_is_valid` to use `re.fullmatch`:**
```python
# patient_data.py lines 38-40 — replace:
def _is_valid(input: str) -> bool:
    pattern = "\\w+[\\s\\w\\-\\.]*"
    return bool(re.match(pattern, input))

# With:
import re
_PATIENT_ID_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_\-\.]{0,63}$')

def _is_valid(patient_id: str) -> bool:
    return bool(_PATIENT_ID_RE.fullmatch(patient_id))
```

**Add `_is_valid` to `create_timeline`:**
```python
async def create_timeline(self, patient_id: str) -> str:
    if not _is_valid(patient_id):
        return json.dumps({"error": "Invalid patient ID."})
    # ... rest of method
```

**Add validation to extractor entry points (example pattern):**
```python
@kernel_function(...)
async def extract_pathology_findings(self, patient_id: str) -> str:
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_\-\.]{0,63}', patient_id):
        return json.dumps({"error": "Invalid patient ID."})
    return await self._extract(patient_id)
```

- **Pros:** Complete coverage; consistent pattern; does not affect legitimate IDs
- **Effort:** Small-Medium (5 files to update)
- **Risk:** None for well-formed patient IDs

## Recommended Action

Option A — fix all three gaps.

## Technical Details

- **Affected files:**
  - `src/scenarios/default/tools/patient_data.py` lines 38-40, 78
  - `src/scenarios/default/tools/pathology_extractor.py` kernel function
  - `src/scenarios/default/tools/radiology_extractor.py` kernel function
  - `src/scenarios/default/tools/oncologic_history_extractor.py` kernel function
  - `src/scenarios/default/tools/tumor_markers.py` two kernel functions

## Acceptance Criteria

- [ ] `_is_valid` uses `re.fullmatch`, not `re.match`
- [ ] `create_timeline` calls `_is_valid` before accessing data
- [ ] All 5 `@kernel_function` entry points in extractor plugins validate `patient_id` before calling internal methods
- [ ] Test: `_is_valid("abc/../../etc/passwd")` returns `False`

## Work Log

- 2026-04-02: Identified by security-sentinel during code review
