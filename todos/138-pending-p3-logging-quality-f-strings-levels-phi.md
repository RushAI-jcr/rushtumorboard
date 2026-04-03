---
status: pending
priority: p3
issue_id: "138"
tags: [code-review, python, quality, performance]
dependencies: []
---

# 138 — Logging quality bundle: f-strings, wrong levels, incorrect count, syntax error

## Problem Statement

A set of independent logging defects across multiple files:

**(A) Eager f-string evaluation:** `logger.info(f"...")` and `logger.error(f"...")` calls in `content_export.py:229`, `timeline_image.py:196-199`, `medical_research.py:174,189,197-199`, and `clinical_trials.py:155` evaluate the format expression unconditionally, even when the log level is disabled. The `logging` module's lazy `%`-style formatting avoids this cost.

**(B) Wrong log level for external failures:** `medical_research.py:174,189` logs external search source failures at `WARNING`. These failures are expected, handled gracefully, and require no operator intervention. `WARNING` implies a condition needing attention; `INFO` is appropriate.

**(C) Incorrect NCCN page count:** `nccn_guidelines.py:77` logs `"Loaded X pages"` where X is computed as `sum(len(v) for v in cls._disease_index.values())`. This counts disease-index entries, not unique pages — the same page appearing under multiple disease keys is counted multiple times. The correct expression is `len(cls._pages)`.

**(D) Nested-quote f-string syntax error:** `clinical_trials.py:155` contains `f"Clinical trials found: {len(result["studies"])}"` — nested double quotes inside an f-string expression are a `SyntaxError` in Python 3.14 (where the old leniency was removed).

## Findings

- `content_export.py:229` — f-string in logger call
- `timeline_image.py:196-199` — f-strings in logger calls
- `medical_research.py:174,189` — `WARNING` level for expected external source failures; also f-strings at `:197-199`
- `clinical_trials.py:155` — f-string with nested double quotes (Python 3.14 SyntaxError)
- `nccn_guidelines.py:77` — page count uses disease-index sum instead of `len(cls._pages)`

## Proposed Solution

- Replace all f-strings in logger calls with `%`-style formatting: `logger.info("Template not found: %s", path)`. This keeps format evaluation lazy.
- Change `logger.warning(...)` to `logger.info(...)` for external API source failures in `medical_research.py:174,189`.
- Fix `nccn_guidelines.py:77` to use `len(cls._pages)` for the logged page count.
- Fix `clinical_trials.py:155` nested-quote f-string using a temporary variable or single-quoted inner key:

```python
study_count = len(result["studies"])
logger.info("Clinical trials found: %s", study_count)
```

## Acceptance Criteria

- [ ] No f-strings used inside any `logger.*()` call across the codebase
- [ ] External API source failures in `medical_research.py` logged at `INFO` not `WARNING`
- [ ] NCCN startup log uses `len(cls._pages)` for page count
- [ ] `clinical_trials.py:155` nested-quote f-string removed; no `SyntaxError` on Python 3.14
