---
name: pathology-report-types-excluded-from-all-clinical-types
description: PATHOLOGY_REPORT_TYPES is silently excluded from ALL_CLINICAL_TYPES despite the name implying exhaustive coverage
type: code-review
status: complete
priority: p3
issue_id: 055
tags: [code-review, documentation, note-types, constants]
---

## Problem Statement

`note_type_constants.py:31` defines `PATHOLOGY_REPORT_TYPES = ("Surgical Pathology Final", "Pathology Consultation")` but this constant is excluded from both `GENERAL_CLINICAL_TYPES` and `ALL_CLINICAL_TYPES`. The name `ALL_CLINICAL_TYPES` implies exhaustive coverage of all clinical note types, but pathology report types are silently omitted. Any tool or agent iterating `ALL_CLINICAL_TYPES` with an expectation of complete coverage will miss pathology note type matches without any error or warning.

## Findings

`note_type_constants.py:31`:
```python
PATHOLOGY_REPORT_TYPES = ("Surgical Pathology Final", "Pathology Consultation")
```

`GENERAL_CLINICAL_TYPES` — does not include `PATHOLOGY_REPORT_TYPES`.
`ALL_CLINICAL_TYPES` — does not include `PATHOLOGY_REPORT_TYPES`.

If the exclusion is intentional (pathology reports are accessed via a dedicated `get_pathology_reports()` function rather than generic note type filtering), there is no comment to indicate this. Future developers may incorrectly add pathology types to `ALL_CLINICAL_TYPES` or assume they are already covered.

## Proposed Solutions

### Option A
Add a clarifying comment to `note_type_constants.py` documenting the intentional exclusion.

```python
# PATHOLOGY_REPORT_TYPES is intentionally excluded from GENERAL_CLINICAL_TYPES and
# ALL_CLINICAL_TYPES. Pathology reports are retrieved via get_pathology_reports(),
# not via generic note type filtering, to preserve accessor separation of concerns.
PATHOLOGY_REPORT_TYPES = ("Surgical Pathology Final", "Pathology Consultation")
```

**Pros:** Zero behavioral change; documents intent; prevents future accidental inclusion or confusion.
**Cons:** Does not fix the issue if the exclusion is actually a bug.
**Effort:** Small
**Risk:** Low

### Option B
If the exclusion is a bug, add `PATHOLOGY_REPORT_TYPES` to `ALL_CLINICAL_TYPES`.

```python
ALL_CLINICAL_TYPES = GENERAL_CLINICAL_TYPES + PATHOLOGY_REPORT_TYPES
```

**Pros:** Makes `ALL_CLINICAL_TYPES` truly exhaustive.
**Cons:** Behavioral change — any tool iterating `ALL_CLINICAL_TYPES` will now process pathology note types, potentially duplicating results with `get_pathology_reports()`; requires audit of all call sites.
**Effort:** Small (code change small; audit effort medium)
**Risk:** Medium

## Technical Details

**Affected files:**
- `note_type_constants.py` (line 31 definition; `GENERAL_CLINICAL_TYPES` and `ALL_CLINICAL_TYPES` definitions)
- Any accessor or tool that iterates `ALL_CLINICAL_TYPES` and expects full coverage (audit required before Option B)

## Acceptance Criteria

- [ ] `note_type_constants.py` has an explicit comment explaining whether `PATHOLOGY_REPORT_TYPES` exclusion from `ALL_CLINICAL_TYPES` is intentional or a bug
- [ ] If intentional: comment references `get_pathology_reports()` as the correct access path
- [ ] If a bug: `ALL_CLINICAL_TYPES` includes `PATHOLOGY_REPORT_TYPES` and all affected call sites are audited for duplicate-result behavior
- [ ] No regression in pathology report retrieval via existing accessor methods

## Work Log

- 2026-04-02: Identified in code review

## Resources

- Branch: fix/accessor-protocol-cache-quality-015-022
