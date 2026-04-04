---
status: complete
priority: p2
issue_id: "093"
tags: [code-review, agent-native, usability]
dependencies: []
---

# P2 — Export error strings carry no machine-readable error class for agent retry logic

## Problem Statement

`export_to_pptx` returns three structurally different error strings that are all plain text. A downstream Orchestrator or ReportCreation agent cannot programmatically distinguish a transient retryable storage failure from a permanent render failure, making automatic recovery impossible.

## Findings

Three error paths (agent-native reviewer):
1. `"Error generating PPTX: slide renderer timed out."` — permanent for this invocation
2. `"Error generating PPTX: renderer exited {N} — ..."` — permanent
3. `"PPTX was generated but could not be saved. Storage error: {exc_type}"` — transient, retryable

An agent checking `if "Error" in result` misses case 3 (starts with "PPTX was generated"). An agent checking `result.startswith("Error")` also misses case 3. There is no reliable discriminant.

The Orchestrator cannot: implement retry for case 3 only; correctly report failure cause; decide whether to skip PPTX and still deliver Word doc.

## Proposed Solution

Add a machine-readable prefix tag on its own line:

```
ERROR_TYPE: RENDER_TIMEOUT
Error generating PPTX: slide renderer timed out.
```
```
ERROR_TYPE: RENDER_FAILED
Error generating PPTX: renderer exited 1 — ...
```
```
ERROR_TYPE: STORAGE_FAILED
PPTX was generated but could not be saved. Please try again.
```

The Orchestrator's system prompt should instruct: "If a tool returns a string beginning with `ERROR_TYPE:`, parse the type and handle accordingly: STORAGE_FAILED is retryable; RENDER_* are not."

## Acceptance Criteria
- [ ] All three error paths in `export_to_pptx` include `ERROR_TYPE:` on the first line
- [ ] `agents.yaml` `ReportCreation` instructions reference how to handle each `ERROR_TYPE`
- [ ] Same pattern applied to `export_to_word_doc` for consistency
