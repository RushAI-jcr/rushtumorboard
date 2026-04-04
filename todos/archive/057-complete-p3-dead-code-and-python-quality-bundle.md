---
name: dead-code-and-python-quality-bundle
description: Bundle of 8 small Python quality issues across changed files including dead code, style violations, and missing type annotations
type: code-review
status: complete
priority: p3
issue_id: 057
tags: [code-review, code-quality, dead-code, style, python312]
---

## Problem Statement

Eight small, independent Python quality issues were identified across the files changed in this branch. None are individually blocking, but collectively they introduce maintenance overhead, noisy diffs, and minor style inconsistency. They are bundled here for a single cleanup commit.

## Findings

### 1. Dead code — bare `isoformat()` call (`fabric_clinical_note_accessor.py:123`)
```python
target_date.isoformat()  # return value discarded
```
The return value is never used. This is a dead statement.

### 2. Useless f-string prefix — no interpolation (`fabric_clinical_note_accessor.py:57`)
```python
f"https://analysis.windows.net/powerbi/api"
```
The `f` prefix adds no value; no `{}` interpolation present. Should be a plain string literal.

### 3. Missing trailing newline (`fhir_clinical_note_accessor.py`, `fabric_clinical_note_accessor.py`)
Both files are missing a trailing newline (EOF). This causes noisy `git diff` output (missing newline warning) and fails `flake8`/`ruff` rule W292.

### 4. Eager f-string evaluation in logging calls (`content_export.py:198`, `presentation_export.py:183`)
```python
logger.info(f"Processing patient {patient_id}...")
```
The codebase convention is deferred `%s` formatting:
```python
logger.info("Processing patient %s...", patient_id)
```
Eager f-string evaluation in logging calls defeats the logger's lazy formatting optimization (the string is built even if the log level is filtered out).

### 5. Unused `doc` parameter on static methods (`content_export.py:244+`)
`_build_col0_richtext`, `_build_col1_richtext`, and similar static methods accept a `doc` parameter that is never used in the method body. No type annotation is present. Should either be removed or annotated:
```python
def _build_col0_richtext(doc: DocxTemplate, ...)  # noqa: ARG004
```

### 6. Unparameterized `list` return type (`presentation_export.py:213`)
```python
def _parse_markers_raw(...) -> list | None:
```
Should be parameterized:
```python
def _parse_markers_raw(...) -> list[dict] | None:
```
`list` without a type parameter is incomplete in Python 3.12 typing.

### 7. Incomplete stdlib import (`fhir_clinical_note_accessor.py:14`)
```python
import urllib
```
`urllib` alone does not expose `urllib.parse` as an attribute. Should be:
```python
import urllib.parse
```
Also should be placed before `aiohttp` in the stdlib import group per PEP 8 / isort convention.

### 8. Misplaced import group (`fabric_clinical_note_accessor.py:8`)
```python
import re
```
`re` appears after stdlib imports with a blank line separating it, making it visually appear to be a third-party import. It should be grouped with the other stdlib imports above the blank line.

## Proposed Solutions

### Option A
Fix all 8 items in a single cleanup commit.

**Pros:** Clears all small issues in one pass; keeps diff reviewable; no behavioral change.
**Cons:** Wide file touch (5 files); minor merge conflict risk if other branches are active on the same files.
**Effort:** Small
**Risk:** Low

## Technical Details

**Affected files:**
- `fabric_clinical_note_accessor.py` (issues 1, 2, 3, 8)
- `fhir_clinical_note_accessor.py` (issues 3, 7)
- `content_export.py` (issues 4, 5)
- `presentation_export.py` (issues 4, 6)

## Acceptance Criteria

- [ ] `fabric_clinical_note_accessor.py:123`: dead `isoformat()` call removed
- [ ] `fabric_clinical_note_accessor.py:57`: f-string prefix removed from URL literal
- [ ] `fhir_clinical_note_accessor.py` and `fabric_clinical_note_accessor.py`: trailing newlines added
- [ ] `content_export.py:198` and `presentation_export.py:183`: f-strings in `logger.info` calls replaced with `%s` deferred formatting
- [ ] `content_export.py`: unused `doc` parameter on static methods removed or annotated with `# noqa: ARG004`
- [ ] `presentation_export.py:213`: `list` return type parameterized as `list[dict]`
- [ ] `fhir_clinical_note_accessor.py:14`: `import urllib` replaced with `import urllib.parse` and placed in correct stdlib group
- [ ] `fabric_clinical_note_accessor.py:8`: `import re` moved into the stdlib import group
- [ ] `ruff check` and `flake8` pass with no new violations on all 4 affected files

## Work Log

- 2026-04-02: Identified in code review

## Resources

- Branch: fix/accessor-protocol-cache-quality-015-022
