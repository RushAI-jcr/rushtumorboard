---
name: unescaped-html-download-link-word-pptx
description: Download link HTML in content_export.py and presentation_export.py is built without html.escape(), creating a latent XSS vector if validation is ever loosened
type: code-review
status: complete
priority: p2
issue_id: 050
tags: [code-review, security, xss]
---

## Problem Statement

`content_export.py:236-239` builds `f'Download: <a href="{doc_output_url}">{artifact_id.filename}</a>'` without `html.escape()` on either value. `presentation_export.py:199-207` has the same pattern. While `validate_patient_id` currently prevents injection characters, this creates a latent XSS vector: if the validation regex is ever loosened, or if `artifact_id.filename` is ever derived from user input, the download link becomes exploitable. The return value is consumed by Semantic Kernel and may reach the chat UI as innerHTML.

## Findings

- `content_export.py:236-239`: unescaped f-string HTML: `f'Download: <a href="{doc_output_url}">{artifact_id.filename}</a>'`
- `presentation_export.py:199-207`: same unescaped HTML construction pattern
- `validate_patient_id` currently prevents `<`, `>`, `"`, `&` in `patient_id` — mitigating the risk today
- `artifact_id.filename` derivation path is not validated against the same regex
- The return value of both export kernel functions flows to the Semantic Kernel chat response and may be rendered as innerHTML in the chat UI
- If validation is loosened or bypassed, attacker-controlled note content could propagate to `artifact_id.filename` and inject arbitrary HTML

## Proposed Solutions

### Option A
Apply `html.escape()` to both `doc_output_url` and `str(artifact_id.filename)` before interpolating into the HTML anchor tag in both `content_export.py:236-239` and `presentation_export.py:199-207`.

```python
safe_url = html.escape(doc_output_url)
safe_filename = html.escape(str(artifact_id.filename))
f'Download: <a href="{safe_url}">{safe_filename}</a>'
```

**Pros:** Defense-in-depth against XSS regardless of upstream validation; follows OWASP output encoding guidance; trivial change; no functional impact on valid inputs
**Cons:** None
**Effort:** Trivial (< 15 minutes)
**Risk:** None

## Recommended Action

## Technical Details

**Affected files:**
- `src/plugins/content_export.py` (lines 236-239)
- `src/plugins/presentation_export.py` (lines 199-207)

Requires adding `import html` to both files if not already present.

## Acceptance Criteria

- [ ] `html.escape()` applied to `doc_output_url` in `content_export.py`
- [ ] `html.escape()` applied to `artifact_id.filename` in `content_export.py`
- [ ] Same escaping applied in `presentation_export.py`
- [ ] `import html` present in both files
- [ ] Unit test: verify that a filename containing `<script>` is escaped in the returned HTML string

## Work Log

- 2026-04-02: Identified in code review

## Resources

- Branch: fix/accessor-protocol-cache-quality-015-022
