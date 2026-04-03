---
name: legacy-typing-list-dict-mixed-with-builtins
description: Legacy typing.List/Dict/Optional/Tuple mixed with Python 3.9+ built-in generics — type checker flags protocol mismatches
type: code-review
status: complete
priority: p1
issue_id: 042
tags: [code-review, typing, python312]
---

## Problem Statement
`fhir_clinical_note_accessor.py:9` imports `from typing import Any, Callable, Coroutine, Dict, List` and uses `List[dict]`, `Dict` in older method signatures, while all new methods use `list[dict]`, `dict`. The same issue exists in `fabric_clinical_note_accessor.py:7` using `Optional`, `Tuple`, `List`. Python 3.9+ supports built-in generics; Python 3.12 code should not use `typing.List`/`Dict`/`Optional`/`Tuple`. The inconsistency causes type checkers to flag potential mismatches between protocol return types (built-in generics) and concrete implementations (typing generics).

## Findings
- `src/data_models/fhir/fhir_clinical_note_accessor.py:9`: Imports `Dict`, `List` from `typing`; used at lines 86 and 129 in method signatures alongside newer `list[dict]` usage elsewhere in the same file.
- `src/data_models/fabric/fabric_clinical_note_accessor.py:7`: Imports `Optional`, `Tuple`, `List` from `typing`; used at lines 30 and 133 while other methods in the same file use built-in generics.
- Protocol definitions use built-in generics (`list[dict]`, `dict | None`); concrete implementations using `typing` generics create surface-level mismatches visible to strict type checkers.

## Proposed Solutions
### Option A
Drop `Dict`, `List`, `Optional`, `Tuple` from typing imports in both files; replace all usages with built-in equivalents: `list`, `dict`, `X | None`, `tuple[X, Y]`.

**Pros:** Consistent with Python 3.12 idioms; eliminates type checker warnings about generic mismatches; reduces import surface; aligns concrete implementations with Protocol definitions
**Cons:** Requires careful search-replace to catch all usages including docstrings; if repo targets Python < 3.9 anywhere, must confirm minimum version
**Effort:** Small
**Risk:** Low

## Recommended Action
(leave blank)

## Technical Details
**Affected files:**
- `src/data_models/fhir/fhir_clinical_note_accessor.py:9, 86, 129`
- `src/data_models/fabric/fabric_clinical_note_accessor.py:7, 30, 133`

## Acceptance Criteria
- [ ] No `typing.List`, `typing.Dict`, `typing.Optional`, or `typing.Tuple` usage remains in either file
- [ ] All method signatures use built-in generics (`list[...]`, `dict[...]`, `X | None`, `tuple[...]`)
- [ ] Mypy/pyright passes with no new errors after the change
- [ ] `from typing import` lines in both files retain only the imports still needed (e.g., `Any`, `Callable`, `Coroutine`, `Protocol`)
- [ ] Confirmed Python minimum version is 3.9+ (required for built-in generics in type annotations at runtime)

## Work Log
- 2026-04-02: Identified in code review

## Resources
- Branch: fix/accessor-protocol-cache-quality-015-022
