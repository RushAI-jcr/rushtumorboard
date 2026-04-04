---
status: complete
priority: p2
issue_id: "019"
tags: [code-review, security, xss, html, phi]
dependencies: []
---

## Problem Statement

Clinical note content is rendered into an HTML template in `grounded_clinical_note.py` without HTML escaping. Clinical notes can contain angle brackets (e.g., `<3 cm`, `<abnormal>`, copy-paste from Word with HTML entities), which would break the HTML structure or — in a web UI context — execute as script tags.

While the current demo client may sanitize on the frontend, the backend should not produce unsafe HTML. If the output is ever rendered in a different context (Teams bot, email, PDF via Chromium), XSS is possible.

## Findings

- **File:** `src/scenarios/default/tools/content_export/grounded_clinical_note.py` (exact line TBD — search for f-string or `.format()` injecting note content into HTML)
- **Reported by:** security-sentinel
- **Severity:** P2 — XSS in healthcare context; clinical note content is user-controlled (sourced from Epic)

## Proposed Solutions

### Option A (Recommended): Use `html.escape()` on all dynamic content
```python
import html

# Before injecting into HTML template:
safe_text = html.escape(note_content)
```
- **Pros:** Zero-dependency stdlib fix; surgical
- **Cons:** None
- **Effort:** Small
- **Risk:** None (escaping is idempotent for safe content)

### Option B: Use a templating engine (Jinja2) with auto-escaping
Replace f-string HTML assembly with Jinja2 template + `autoescape=True`.
- **Pros:** Systematic; harder to miss
- **Cons:** Adds Jinja2 dependency if not already present; larger refactor
- **Effort:** Medium

## Recommended Action

Option A — add `html.escape()` around all clinical content injected into HTML strings. Verify the file first to identify all injection points.

## Technical Details

- **Affected file:** `src/scenarios/default/tools/content_export/grounded_clinical_note.py`
- **Pattern to find:** f-strings or `.format()` calls that embed note text/patient data into HTML
- **Risk scenario:** Note containing `<script>alert(1)</script>` or `</div><div class="injected">` breaks layout or executes

## Acceptance Criteria

- [ ] All clinical note content injected into HTML passes through `html.escape()` first
- [ ] Test: note with `<b>bold</b>` text renders as literal `&lt;b&gt;bold&lt;/b&gt;` in HTML output
- [ ] No raw patient content in HTML without escaping

## Work Log

- 2026-04-02: Identified by security-sentinel during code review
- 2026-04-02: Already resolved — html.escape() applied to all 6 injection points (patient_id, note_id, date, note_type, note text, highlighted spans) in grounded_clinical_note.py.
