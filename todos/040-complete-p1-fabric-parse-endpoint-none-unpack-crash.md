---
name: fabric-parse-endpoint-none-unpack-crash
description: __parse_fabric_endpoint returns None on bad URL and unconditional unpack at __init__ raises opaque TypeError
type: code-review
status: complete
priority: p1
issue_id: 040
tags: [code-review, reliability, error-handling]
---

## Problem Statement
`fabric_clinical_note_accessor.py:52`: `__parse_fabric_endpoint` can return `None` when the URL matches neither expected pattern. At `__init__` line 26: `workspace_id, data_function_id = self.__parse_fabric_endpoint(...)` — unconditional unpack. If the Fabric endpoint URL is misconfigured, this raises `TypeError: cannot unpack non-iterable NoneType object` at constructor time with no useful error message about what was wrong with the URL.

## Findings
- `src/data_models/fabric/fabric_clinical_note_accessor.py:52`: `__parse_fabric_endpoint` returns `None` when the URL matches no known pattern — the return type annotation does not reflect this.
- `src/data_models/fabric/fabric_clinical_note_accessor.py:26`: `workspace_id, data_function_id = self.__parse_fabric_endpoint(...)` — no null-check before unpack; a misconfigured URL raises `TypeError` with no diagnostic information about the URL itself.

## Proposed Solutions
### Option A
Raise `ValueError` with a descriptive message inside `__parse_fabric_endpoint` when no pattern matches, before returning `None` (eliminate the `None` return entirely).

**Pros:** Fail-fast at the point of bad input; error message can include the problematic URL; return type becomes `tuple[str, str]` with no `None` case; cleaner call site
**Cons:** Slightly changes the public behavior of the private method (acceptable since it's private)
**Effort:** Small
**Risk:** Low

### Option B
Add a null-check at the unpack site in `__init__`: `result = self.__parse_fabric_endpoint(...); if result is None: raise ValueError(f"Invalid Fabric endpoint URL: {url}")`.

**Pros:** Preserves existing method signature; descriptive error at constructor
**Cons:** `None` return path still exists in `__parse_fabric_endpoint`; type checker still sees `Optional[tuple]` return
**Effort:** Small
**Risk:** Low

## Recommended Action
(leave blank)

## Technical Details
**Affected files:**
- `src/data_models/fabric/fabric_clinical_note_accessor.py:26, 52`

## Acceptance Criteria
- [ ] A misconfigured Fabric endpoint URL raises `ValueError` (not `TypeError`) with a message that includes the problematic URL
- [ ] The error is raised at constructor time, not deferred to first API call
- [ ] `__parse_fabric_endpoint` return type annotation is accurate (no silent `None` case)
- [ ] Unit test: passing a nonsense URL to the constructor raises `ValueError` containing the URL

## Work Log
- 2026-04-02: Identified in code review

## Resources
- Branch: fix/accessor-protocol-cache-quality-015-022
