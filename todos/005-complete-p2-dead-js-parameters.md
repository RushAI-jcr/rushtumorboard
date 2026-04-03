---
status: complete
priority: p2
issue_id: "005"
tags: [code-review, simplicity, javascript]
dependencies: []
---

# P2 — Dead / YAGNI parameters in `tumor_board_slides.js` helpers

## Problem Statement

Three helper functions carry parameters that are never given non-default values anywhere
in the file. They add apparent configurability that doesn't exist in practice and will
mislead future maintainers.

## Findings

**A — `frame()` `total` parameter (`line ~43`):**
```js
function frame(prs, slide, titleText, subtitleText, slideNum, total = 5)
```
`total` is always omitted at every call site. The presentation is permanently 5 slides.
Remove the parameter; hardcode `5` in the badge text string.

**B — `hRule()` `xOff` and `wAdj` parameters (`line ~95`):**
```js
function hRule(prs, slide, y, color = RULE, xOff = 0, wAdj = 0)
```
`xOff` and `wAdj` are never given non-zero values. Every call passes only `y` or `y` +
`color`. Remove both parameters; the body simplifies from
`x: MARGIN + xOff, w: W - MARGIN * 2 + wAdj` to `x: MARGIN, w: W - MARGIN * 2`.

**C — `mkLabelValue()` option defaults never used (`line ~131`):**
```js
function mkLabelValue(items, { size = 14, gap = 9 } = {}) { ... }
```
The one call site passes `{ size: 15, gap: 11 }` — the defaults `14` / `9` are never
used. Either remove the options object entirely and hardcode `15`/`11`, or rename to
make clear these are the only valid values.

## Proposed Solution

Inline the one call site's values and remove the option destructuring:
```js
// Before
function mkLabelValue(items, { size = 14, gap = 9 } = {}) { ... }
// After
function mkLabelValue(items) {
  const size = 15, gap = 11;
  ...
}
```

Same treatment for `frame` and `hRule`.

## Acceptance Criteria
- [ ] `frame` no longer accepts `total`; badge hardcodes `/ 5`
- [ ] `hRule` signature is `(prs, slide, y, color = RULE)`
- [ ] `mkLabelValue` has no options parameter
- [ ] All existing tests still pass after parameter removal
