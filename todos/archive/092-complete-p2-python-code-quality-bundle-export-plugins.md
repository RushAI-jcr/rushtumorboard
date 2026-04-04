---
status: complete
priority: p2
issue_id: "092"
tags: [code-review, quality, python]
dependencies: []
---

# P2 — Python code quality issues: deferred import, stderr fallback semantics, empty-dict edge case

## Problem Statement

Three distinct code quality issues in `presentation_export.py` introduced or surfaced by this changeset. Each is independently fixable.

## Findings

**A — `import html as _html` inside function body (`presentation_export.py`, line 250):**
```python
import html as _html
safe_url = _html.escape(output_url, quote=True)
```
Module-level import at the top of the file is the Python convention. Deferred imports inside methods are appropriate only for optional heavy dependencies; `html` is stdlib. The underscore alias signals a private import at module level (not function scope) and confuses readers. `content_export.py` already imports `html` correctly at the top.

**B — `(stderr or stdout or b"")` is semantically wrong (`presentation_export.py`, line 214):**
```python
err_text = (stderr or stdout or b"").decode(errors="replace")
```
`proc.communicate()` with both `stdout=PIPE` and `stderr=PIPE` never returns `None` for either. When `stderr` is `b""` (empty, falsy), the expression falls back to `stdout` — which may contain the temp file path (written by Node on success), producing a misleading "error" message containing the output path. The correct expression makes intent explicit:
```python
err_text = (stderr if stderr else stdout).decode(errors="replace")
```

**C — `all(isinstance(v, dict) for v in data.values())` is vacuously True on empty dict (`presentation_export.py`, line 283):**
```python
elif all(isinstance(v, dict) for v in data.values()):
```
`all([])` returns `True` in Python. If `data` is `{}`, this branch passes and `next(iter(data.values()), {})` returns `{}`, silently producing an empty `data_points` list. The downstream length check catches it, but the vacuous-truth behaviour is a correctness-by-accident anti-pattern:
```python
elif data and all(isinstance(v, dict) for v in data.values()):
```

**D — `_MAX_ACTION_ITEM_CHARS = 200` at function scope (`content_export.py`, line 410):**
All other cap constants in this module are at module level with consistent naming. This one is inside `_summarize_for_tumor_board_doc`. Move to module level alongside `_MAX_ONCOLOGIC_HISTORY_CHARS` etc.

## Proposed Solution

Four independent one-line (or few-line) fixes as described in each finding.

## Acceptance Criteria
- [ ] `import html` moved to module level in `presentation_export.py`; alias `_html` removed
- [ ] `(stderr or stdout or b"")` replaced with `(stderr if stderr else stdout)`
- [ ] `elif data and all(...)` guards against empty dict in `_parse_markers_raw`
- [ ] `_MAX_ACTION_ITEM_CHARS = 200` moved to module level in `content_export.py`
