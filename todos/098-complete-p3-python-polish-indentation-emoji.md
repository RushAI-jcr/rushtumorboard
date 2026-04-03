---
status: complete
priority: p3
issue_id: "098"
tags: [code-review, quality, python]
dependencies: []
---

# P3 — Python polish: fallback SlideContent over-indented; emoji in action_item; missing type hints

## Problem Statement

Three cosmetic/polish issues in the export plugins that reduce internal consistency.

## Findings

**A — Fallback `SlideContent` constructor over-indented (`presentation_export.py`, lines 324-348):**
The constructor arguments appear at 16-space indentation (4 levels) but the `return SlideContent(` is at 8-space indentation (2 levels). This is a legacy of the refactor from inside an `except` block to function body level. Arguments should be at 12-space indentation.

**B — `⚠` emoji in `action_items` fallback (`content_export.py`, line 464):**
```python
action_items=["⚠ Export used LLM fallback — review all fields before printing."],
```
Unicode warning symbols render inconsistently across Word versions and printers — may appear as `□` on Windows machines without emoji fonts. The rest of the codebase uses plain ASCII for clinical content. Replace with `[FALLBACK]` prefix.

**C — Missing return type on `create_plugin` and untyped `kernel` parameter (`presentation_export.py`, lines 103-115):**
```python
def create_plugin(plugin_config: PluginConfiguration):  # no return type
    ...
class PresentationExportPlugin:
    def __init__(self, kernel, ...):  # kernel untyped
```
`content_export.py` annotates `kernel: Kernel` explicitly. Both files should be consistent.

## Proposed Solution

A: Realign `SlideContent(...)` arguments to 12-space indentation.
B: Replace `⚠` with `[FALLBACK]`.
C: Add `-> PresentationExportPlugin` to `create_plugin` and `kernel: Kernel` to `__init__`.

## Acceptance Criteria
- [ ] Fallback `SlideContent` constructor arguments consistently indented at 12 spaces
- [ ] `⚠` emoji replaced with `[FALLBACK]` prefix in `content_export.py` action_items fallback
- [ ] `create_plugin` has return type annotation; `__init__` `kernel` parameter is typed
