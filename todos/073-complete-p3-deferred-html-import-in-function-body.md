---
status: pending
priority: p3
issue_id: "073"
tags: [code-review, style, python, imports]
dependencies: []
---

## Problem Statement

`presentation_export.py` imports `html` as `_html` inside the `export_to_pptx` method body rather than at the module level:

```python
import html as _html  # inside the method
safe_url = _html.escape(output_url, quote=True)
```

`html` is a Python stdlib module. There is no performance, circular-import, or conditional-use reason to defer this import. `content_export.py` correctly imports `html` at the module top-level. This inconsistency signals the import was added late without refactoring.

## Findings

- **File:** `src/scenarios/default/tools/presentation_export.py`, method body of `export_to_pptx`
- **Reported by:** security-sentinel, kieran-python-reviewer
- **Severity:** P3 — style inconsistency; no functional impact

## Proposed Solutions

Move `import html` (or `import html as _html` if the alias is wanted) to the top of `presentation_export.py` with other stdlib imports. Update all usages.

## Acceptance Criteria

- [ ] `import html` (or `import html as _html`) at module level in `presentation_export.py`
- [ ] No import statement for `html` inside any method or function body

## Work Log

- 2026-04-02: Identified during code review.
