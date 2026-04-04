---
status: complete
priority: p2
issue_id: "094"
tags: [code-review, agent-native, usability]
dependencies: []
---

# P2 — `export_to_word_doc` return format is asymmetric with `export_to_pptx`

## Problem Statement

The two paired export tools (always called together per `agents.yaml`) now return structurally different success strings. `export_to_pptx` includes a plain-text `Download URL:` line for programmatic extraction; `export_to_word_doc` embeds the URL only inside an HTML anchor. A consuming agent must apply two different parsing strategies for what is logically one combined operation.

## Findings

**`export_to_pptx` success return (updated):**
```
PowerPoint presentation created: {filename}
Download URL: {url}

<a href='{url}'>{filename}</a>
```

**`export_to_word_doc` success return (unchanged):**
```
The tumor board Word document has been created. Download: <a href="{url}">{filename}</a>
```

Agent-native reviewer: "These two tools are supposed to be called as a pair. The ReportCreation agent must now apply two different extraction patterns... to reconstruct the file list."

## Proposed Solution

Align `export_to_word_doc` to the same format as `export_to_pptx`:

```python
return (
    f"Word document created successfully.\n"
    f"Download URL: {safe_url}\n\n"
    f'<a href="{safe_url}">Download Tumor Board Handout</a>'
)
```

## Acceptance Criteria
- [ ] `export_to_word_doc` success return includes `Download URL:` on its own line
- [ ] `export_to_word_doc` HTML anchor text is generic (not the filename containing patient_id)
- [ ] Both tools return the same structural format for success and failure
