---
name: note-dict-text-missing-str-coercion-phi-traceback
description: note_dict["text"] used without str() coercion — TypeError traceback may expose PHI in Application Insights
type: code-review
status: pending
priority: p1
issue_id: 035
tags: [code-review, security, phi, xss]
---

## Problem Statement
In `grounded_clinical_note.py`, `note_dict["text"]` is used directly without `str()` coercion before being sliced and passed to `html.escape()`. If the Epic note JSON returns a non-string (malformed data), `_highlight_note_text` raises `TypeError` at the slice operation. The stack traceback logged to Azure Application Insights would contain note content — PHI disclosure.

## Findings
- `src/routes/views/grounded_clinical_note.py:16-17`: `note_dict["text"]` is sliced and passed to `html.escape()` without type coercion. A non-string value from Epic's note JSON (e.g., `None`, `int`) triggers `TypeError` mid-slice, and the full traceback including note content is emitted to Application Insights logs.

## Proposed Solutions
### Option A
Add `str()` coercion before the evidences branch: `note_text = str(note_dict.get("text", ""))`.

**Pros:** One-line fix; eliminates TypeError entirely; safe default for all falsy values including None
**Cons:** None
**Effort:** Small
**Risk:** Low

### Option B
Wrap the whole rendering in try/except and return a safe fallback HTML string on any exception.

**Pros:** Broader protection; prevents any rendering-time exception from leaking note content in logs
**Cons:** Silently swallows other errors that may need visibility; harder to debug legitimate issues
**Effort:** Small
**Risk:** Low

## Recommended Action
(leave blank)

## Technical Details
**Affected files:**
- `src/routes/views/grounded_clinical_note.py:16-17`

## Acceptance Criteria
- [ ] `note_dict["text"]` is coerced to `str` before any slice or `html.escape()` call
- [ ] A unit test passes a `None` and an `int` value for `note_dict["text"]` and asserts no exception is raised and output is valid HTML
- [ ] No PHI-containing TypeErrors appear in Application Insights for malformed note payloads

## Work Log
- 2026-04-02: Identified in code review

## Resources
- Branch: fix/accessor-protocol-cache-quality-015-022
