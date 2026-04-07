---
status: pending
priority: p2
issue_id: "211"
tags: [code-review, performance, async]
dependencies: []
---

# Blocking DocxTemplate Rendering in Async Context

## Problem Statement
`DocxTemplate(path)`, `doc.render(data)`, and `doc.save(stream)` are synchronous, CPU-bound operations that block the event loop. With large templates and RichText content, this stalls all concurrent requests.

## Findings
- **File**: `src/scenarios/default/tools/content_export/content_export.py`, lines 408-434

## Proposed Solution
Wrap in `run_in_executor`:
```python
loop = asyncio.get_running_loop()
await loop.run_in_executor(None, self._render_doc_sync, doc_template_path, doc_data, stream)
```

- **Effort**: Small (15 lines — extract sync render method + await in executor)

## Acceptance Criteria
- [ ] DocxTemplate rendering runs in thread pool executor
- [ ] Event loop not blocked during document generation
