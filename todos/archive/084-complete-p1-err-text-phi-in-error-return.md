---
status: complete
priority: p1
issue_id: "084"
tags: [code-review, security, hipaa]
dependencies: []
---

# P1 — `err_text[:200]` returned to chat may contain PHI from Node stderr

## Problem Statement

`tumor_board_slides.js` receives the full `SlideContent` payload — patient last name, stage, genetics, clinical bullets — via stdin JSON. When PptxGenJS crashes during slide construction, stack traces can echo object property values. The first 200 characters of stderr (or stdout) are returned verbatim into the SK group chat history, from which they propagate to Teams messages, Azure Monitor traces, and conversation logs. This is a HIPAA violation.

## Findings

**`presentation_export.py`, lines 214-215:**
```python
err_text = (stderr or stdout or b"").decode(errors="replace")
return f"Error generating PPTX: renderer exited {proc.returncode} — {err_text[:200]}"
```

Example Node crash output that could appear in the return string:
```
TypeError: Cannot read properties of undefined (reading 'slice')
    at buildSlide5 (…) input: { "patient_title": "Case 1 — Martinez", "stage": "IIIC" }
```

The `stdout or` fallback compounds this: on a non-zero exit where stderr is empty but stdout contains partial output, stdout (which includes the temp file path — itself containing `patient_id`) is returned.

Security agent confirmed: this is a direct HIPAA violation. The patient name, stage, and genetics appear in an error channel that bypasses all PHI controls.

## Proposed Solution

Return an opaque error code. Log the raw text at DEBUG level keyed only by `conversation_id`:

```python
if proc.returncode != 0:
    logger.error(
        "tumor_board_slides.js exited %d — check stderr for details",
        proc.returncode,
    )
    logger.debug(
        "tumor_board_slides.js stderr (conv=%s): %s",
        self.chat_ctx.conversation_id,
        (stderr or stdout or b"").decode(errors="replace")[:2000],
    )
    return f"Error generating PPTX: renderer failed (exit {proc.returncode}). Contact support."
```

## Acceptance Criteria
- [ ] No raw stderr or stdout content in the return string from `export_to_pptx`
- [ ] Raw error text moved to DEBUG-level log keyed by `conversation_id` (not `patient_id`)
- [ ] Return string is opaque and clinically safe to display in Teams chat
- [ ] `logger.error` at ERROR level contains only exit code (no content)
