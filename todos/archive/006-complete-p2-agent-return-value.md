---
status: complete
priority: p2
issue_id: "006"
tags: [code-review, agent-native, usability]
dependencies: []
---

# P2 — `export_to_pptx` return value is HTML-only; opaque to downstream agents

## Problem Statement

`export_to_pptx` returns an HTML anchor tag string. While this renders correctly in the
Teams chat UI, a downstream agent (e.g., Orchestrator confirming success, or a follow-up
tool that needs the blob URL) cannot extract the URL or confirm success programmatically.

Also: the `@kernel_function` description doesn't differentiate this tool from
`export_to_word_doc` well enough for an LLM to choose between them correctly.

## Findings

**Return value (`presentation_export.py`, lines ~215–219`):**
```python
return (
    f"The PowerPoint presentation has been successfully created. "
    f'<a href="{safe_url}">{safe_name}</a>'
)
```
The URL is embedded inside HTML. An agent that needs to confirm the file was created,
or log the artifact path, must regex-parse HTML — a fragile pattern.

**`@kernel_function` description:**
```
"Generate a 5-slide PowerPoint presentation for the GYN tumor board — one slide
per column: Patient, Diagnosis, Previous Tx (with CA-125 chart), Imaging, Discussion."
```
This is accurate but doesn't say *when* to call it vs. `export_to_word_doc`. An LLM
orchestrator may call both or neither.

**`tumor_markers` docstring:**
```
tumor_markers: Tumor marker trends (CA-125, HE4, etc.) as JSON or text.
```
"JSON or text" is too vague. The actual expected format is the JSON output of
`get_tumor_marker_trend` — the agent docstring should say this explicitly.

## Proposed Solution

Return a plain-text string with the URL on a predictable line, plus the HTML anchor:
```python
return (
    f"PowerPoint presentation created: {artifact_id.filename}\n"
    f"Download URL: {safe_url}\n\n"
    f'<a href="{safe_url}">{safe_name}</a>'
)
```

Update `@kernel_function` description to clarify:
```
"Generate a 5-slide PowerPoint (.pptx) tumor board presentation. Call this in addition 
to export_to_word_doc — one generates the handout, the other the slide deck. 
Pass tumor_markers as the raw JSON output from get_tumor_marker_trend."
```

## Acceptance Criteria
- [x] Return value includes a plain-text `Download URL: <url>` line before the HTML anchor
- [x] `@kernel_function` description distinguishes this from `export_to_word_doc`
- [x] `tumor_markers` parameter docstring specifies it expects `get_tumor_marker_trend` JSON output
