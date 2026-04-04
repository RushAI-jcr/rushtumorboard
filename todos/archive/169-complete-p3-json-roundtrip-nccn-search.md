---
status: complete
priority: p3
issue_id: "169"
tags: [code-review, performance, nccn]
dependencies: []
---

# Unnecessary json.loads(json.dumps()) Round-Trip in search_nccn_guidelines

## Problem Statement

`search_nccn_guidelines` calls `self._format_page_response(page)` which serializes to a JSON string, then immediately calls `json.loads(page_response)` to deserialize it back to a dict. This is a redundant allocation per result page (up to 7 pages per query).

**Why:** Minor performance issue. Not a hot path (called at most a few times per tumor board session), but unnecessary complexity.

## Findings

**Source:** performance-oracle

```python
# src/scenarios/default/tools/nccn_guidelines.py
for code, _ in ranked[:7]:
    page = self._pages[code]
    page_response = self._format_page_response(page, include_full_markdown=True)  # returns str
    if total_chars + len(page_response) > MAX_RESPONSE_CHARS:
        results.append(self._format_page_summary(page))
    else:
        results.append(json.loads(page_response))  # ← deserialize back to dict
        total_chars += len(page_response)
```

`_format_page_response` builds a dict and then calls `json.dumps()`. The caller immediately `json.loads()` it back.

## Proposed Solution

Refactor `_format_page_response` to return `dict[str, Any]` directly. Add a separate `_format_page_response_json` if a string representation is needed elsewhere.

```python
def _format_page_response(self, page: dict[str, Any], include_full_markdown: bool = True) -> dict[str, Any]:
    # return dict directly instead of json.dumps(...)

# Then in search_nccn_guidelines:
results.append(self._format_page_response(page))
```

**Effort:** Small — check all callers of `_format_page_response` first.

## Acceptance Criteria

- [ ] `_format_page_response` returns dict, not str
- [ ] No `json.loads(page_response)` call in the search loop
- [ ] All existing callers updated
- [ ] 0 Pyright errors

## Work Log

- 2026-04-03: Identified by performance-oracle during code review
