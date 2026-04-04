---
status: complete
priority: p1
issue_id: "082"
tags: [code-review, reliability, architecture]
dependencies: []
---

# P1 — `RuntimeError` from empty-file check propagates out of `@kernel_function`

## Problem Statement

`export_to_pptx` raises `RuntimeError("PPTX renderer produced an empty file")` inside the subprocess `try` block. Semantic Kernel requires `@kernel_function` methods to return a value — an unhandled exception exits the tool call and propagates to the group chat's `chat.invoke()` loop, where it is caught at the adapter level and surfaced as a generic "try again" message. The Word document (if already delivered) is reported as complete while the PPTX delivery is silently interrupted.

## Findings

**`presentation_export.py`, line 222:**
```python
if not pptx_bytes:
    raise RuntimeError("PPTX renderer produced an empty file")
```
Every other error path in this function uses `return "Error generating PPTX: ..."`. This `raise` is inconsistent with the entire function's error contract and with Semantic Kernel's tool calling convention.

Architecture agent confirmed: the unhandled `RuntimeError` terminates the `ReportCreation` agent turn, interrupting any remaining tool calls in the same turn and delivering a generic error to the Teams UI rather than an actionable message.

Python reviewer confirmed: the declared return type is `str`; a `raise` violates that contract.

## Proposed Solution

Replace the `raise` with a string return matching the existing error pattern:

```python
if not pptx_bytes:
    logger.error(
        "PPTX renderer produced an empty file (conv=%s)",
        self.chat_ctx.conversation_id,
    )
    return "Error generating PPTX: renderer produced an empty file."
```

## Acceptance Criteria
- [ ] `export_to_pptx` never raises from the empty-file path — returns error string instead
- [ ] Log uses `conversation_id`, not `patient_id`, to avoid PHI in logs
- [ ] All error return strings follow the `"Error generating PPTX: ..."` prefix convention
