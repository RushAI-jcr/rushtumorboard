---
status: pending
priority: p3
issue_id: "145"
tags: [code-review, simplicity, quality]
dependencies: []
---

# 145 — `RUSH_ORDER_CODES` module-level dict is decorative — actual lookups use a parallel inline dict

## Problem Statement

`pretumor_board_checklist.py:29-60` defines `RUSH_ORDER_CODES` as a 24-entry module-level dict, apparently as the central source of truth for lab and imaging order codes. However, `_check_labs` and `_check_imaging` define their own parallel inline dict inside the inner `_check()` closure (`pretumor_board_checklist.py:270-274`) and look up order codes from that local dict rather than from `RUSH_ORDER_CODES`. The module-level constant is never referenced by the lookup logic, functioning only as documentation. Any new order code added to `RUSH_ORDER_CODES` must be manually duplicated in the inline dict or it will have no effect, and there is no mechanism to detect the divergence.

## Findings

- `pretumor_board_checklist.py:29-60` — `RUSH_ORDER_CODES` module-level dict (never used as lookup)
- `pretumor_board_checklist.py:270-274` — inline order-code dict inside `_check()` closure (actual lookup source)

## Proposed Solution

Replace the inline dict in `_check()` with a direct lookup against `RUSH_ORDER_CODES`:

```python
order_code = RUSH_ORDER_CODES.get(label, "")
```

Remove the inline dict. Audit all labels passed to `_check_labs` and `_check_imaging` to confirm they all exist as keys in `RUSH_ORDER_CODES`; add any missing entries to the module-level dict. After this change, `RUSH_ORDER_CODES` becomes the single source of truth.

## Acceptance Criteria

- [ ] `_check_labs` and `_check_imaging` resolve order codes via `RUSH_ORDER_CODES.get(label, "")`
- [ ] No parallel inline order-code dict exists in `_check()` or anywhere else in the module
- [ ] All labels referenced in `_check_labs` / `_check_imaging` call sites exist as keys in `RUSH_ORDER_CODES`
- [ ] Adding a new order code to `RUSH_ORDER_CODES` is sufficient to make it available to the checklist logic
