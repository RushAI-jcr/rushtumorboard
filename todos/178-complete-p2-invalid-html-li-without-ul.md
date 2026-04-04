---
status: pending
priority: p2
issue_id: "178"
tags: [code-review, python, html]
dependencies: []
---

# Fix invalid HTML: <li> tags without parent <ul> in append_links()

## Problem Statement
`append_links()` in `message_enrichment.py` wraps clinical trial links in `<li>` tags without enclosing them in a parent `<ul>` or `<ol>` element. This produces invalid HTML per the W3C spec, which requires `<li>` elements to be direct children of `<ul>`, `<ol>`, or `<menu>`. While most browsers render this tolerantly, strict HTML parsers (accessibility tools, email clients, PDF converters) may discard or misformat the list items.

## Findings
- **Source**: Kieran Python Reviewer (Moderate)
- `src/utils/message_enrichment.py:30-32` -- `<li>` tags generated in a loop without a wrapping list element

## Proposed Solutions
1. **Wrap the loop output in `<ul>...</ul>`**
   - Add `<ul>` before the loop and `</ul>` after
   - Pros: Minimal change, valid HTML, correct semantics
   - Cons: None
   - Effort: ~5 minutes

2. **Switch to `<div>` with CSS list styling**
   - Replace `<li>` with `<div class="trial-link">` entries
   - Pros: Avoids list semantics if not truly a list
   - Cons: Less semantic, more CSS required
   - Effort: ~10 minutes

## Acceptance Criteria
- [ ] Clinical trial links are wrapped in a `<ul>` (or `<ol>`) parent element
- [ ] Output passes W3C HTML validation (no orphaned `<li>` elements)
- [ ] Visual rendering in the chat UI is unchanged or improved
- [ ] All existing tests pass
