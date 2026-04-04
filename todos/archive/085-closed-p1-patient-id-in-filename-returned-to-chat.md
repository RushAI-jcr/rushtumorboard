---
status: closed
priority: p1
issue_id: "085"
tags: [code-review, security, hipaa]
dependencies: []
---

# P1 — `patient_id` embedded in artifact filename returned verbatim to chat

## Problem Statement

`artifact_id.filename` is `"tumor_board_slides-{patient_id}.pptx"`. This string appears three times in the `export_to_pptx` success return: once as plain text on the first line, once in `safe_name` (HTML-escaped but still readable), and once embedded in `safe_url` as a URL path segment. The return value is injected into SK group chat history — propagating the patient identifier to Teams messages, Azure Monitor, and conversation logs.

## Findings

**`presentation_export.py`, lines 253-257:**
```python
return (
    f"PowerPoint presentation created: {artifact_id.filename}\n"   # patient_id here
    f"Download URL: {safe_url}\n\n"                                # patient_id in URL path
    f'<a href="{safe_url}">{safe_name}</a>'                        # patient_id twice more
)
```

Where `artifact_id.filename = OUTPUT_PPTX_FILENAME.format(patient_id)` = `"tumor_board_slides-patient_gyn_001.pptx"`.

The blob path structure also embeds `patient_id` as a URL segment (`/{patient_id}/filename`), which appears verbatim in the `Download URL:` line.

Security agent (Finding 2): this places a direct PHI identifier in every logging stream that receives SK tool results.

The same pattern exists in `content_export.py` — that file is not part of the current PR but should be fixed simultaneously.

## Proposed Solution

Scrub patient ID from the text returned to the agent. The download link can use generic anchor text:

```python
return (
    f"PowerPoint presentation created successfully.\n"
    f"Download URL: {safe_url}\n\n"
    f'<a href="{safe_url}">Download Tumor Board Slides</a>'
)
```

The URL itself still contains the patient_id in the path (that is a separate architectural concern requiring filename scheme changes), but at minimum remove it from the plain-text line and the anchor text.

Longer-term: use a session-scoped UUID instead of `patient_id` in filenames.

## Acceptance Criteria
- [ ] `artifact_id.filename` (which contains `patient_id`) not returned in plain text
- [ ] HTML anchor text is generic ("Download Tumor Board Slides"), not the filename
- [ ] Same fix applied to `export_to_word_doc` in `content_export.py`
- [ ] `validate_patient_id()` called at entry of both export functions (mirrors other plugins)
