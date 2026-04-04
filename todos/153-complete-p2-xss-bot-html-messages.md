---
status: pending
priority: p2
issue_id: "153"
tags: [code-review, security, xss]
dependencies: []
---

# XSS Risk in Bot HTML Message Construction

## Problem Statement

`assistant_bot.py` lines 196-205 (`_append_links_to_msg`) injects URLs and filenames from `chat_ctx.display_image_urls` and `chat_ctx.display_clinical_trials` directly into HTML without escaping. A compromised clinical note containing a crafted URL could result in stored XSS.

## Findings

- **Source**: Security Sentinel
- **Evidence**: `src/bots/assistant_bot.py` lines 196-205
- **Contrast**: `grounded_clinical_note.py` properly uses `html.escape()`

## Proposed Solutions

### Option A: Apply html.escape (Recommended)
```python
msgText += f"<img src='{html.escape(url, quote=True)}' alt='{html.escape(filename)}' height='300px'/>"
msgText += f"<li><a href='{html.escape(url, quote=True)}'>{html.escape(trial)}</a></li>"
```
- **Effort**: Small
- **Risk**: None

## Acceptance Criteria
- [ ] All dynamic values in HTML strings use `html.escape()`
- [ ] URLs use `quote=True` for attribute context

## Work Log
- 2026-04-02: Identified during code review (security-sentinel)
