---
status: pending
priority: p2
issue_id: "117"
tags: [code-review, performance, reliability]
dependencies: []
---

# 117 — `x_ray_findings` list has no length or per-element cap before LLM serialization

## Problem Statement

In `content_export.py:_summarize_for_tumor_board_doc`, `x_ray_findings` (a `list[str]`) is serialized to `json.dumps` with no per-element character cap and no list-length cap. `ct_scan_findings` has a per-element cap of 3000 chars but no list-length cap. A patient with many imaging studies (25 CT scans, 25 X-rays) could send 25 × 3000 + 25 × (unlimited) characters to the LLM context window, causing context overflow, truncated responses, or inflated inference cost. `tumor_markers` is also passed as a raw string with no length guard.

## Findings

- `content_export.py` — `_summarize_for_tumor_board_doc` function; search for `x_ray_findings` and `ct_scan_findings` in the serialization block
- `ct_scan_findings` has `str(f)[:3000]` per-element guard but no `[:N]` list slice
- `x_ray_findings` has neither a list-length slice nor a per-element char cap
- `tumor_markers` passed as a raw string before serialization

## Proposed Solution

Apply the same capping pattern already used for `pathology_findings` to all imaging and marker fields:

```python
"x_ray_findings": [str(f)[:3000] for f in x_ray_findings[:10]],
"ct_scan_findings": [str(f)[:3000] for f in ct_scan_findings[:10]],
"tumor_markers": str(tumor_markers)[:2000],
```

Define a module-level constant `_MAX_IMAGING_ITEMS = 10` to make the cap explicit and easy to adjust.

## Acceptance Criteria

- [ ] `x_ray_findings` capped to at most 10 items, each truncated to 3000 characters
- [ ] `ct_scan_findings` list-length capped to at most 10 items (per-element cap already present)
- [ ] `tumor_markers` string length capped before serialization (≤ 2000 chars or a documented constant)
- [ ] Cap constants are named at module level, not magic numbers inline
- [ ] No regression to `pathology_findings` capping which already works correctly
