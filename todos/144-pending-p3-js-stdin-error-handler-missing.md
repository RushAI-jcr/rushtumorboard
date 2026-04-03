---
status: pending
priority: p3
issue_id: "144"
tags: [code-review, reliability, javascript]
dependencies: []
---

# 144 — Node.js subprocess has no stdin error handler — pipe errors waste full timeout

## Problem Statement

`tumor_board_slides.js:488-522` reads all stdin data by accumulating chunks into a string (`raw += c`) with no `process.stdin.on("error")` handler registered. If the Python process closes its write end of the pipe unexpectedly (crash, cancellation, or `TimeoutError` on the Python side), the Node.js subprocess receives a broken pipe error on stdin. Without an error handler, Node.js silently stalls waiting for more input. The subprocess does not exit until the 60-second `_NODE_TIMEOUT_SECS` elapses, wasting the entire timeout window and delaying the error surfaced to the Python caller by up to a minute.

## Findings

- `scripts/tumor_board_slides.js:488-522` — stdin accumulation loop with no error handler

## Proposed Solution

Add an error handler on `process.stdin` that writes a diagnostic message to stderr and exits immediately with a non-zero code:

```javascript
process.stdin.on("error", (err) => {
    process.stderr.write("stdin error: " + err.message + "\n");
    process.exit(1);
});
```

Place this handler registration alongside the existing `"data"` and `"end"` listeners so it is always active during stdin reading.

## Acceptance Criteria

- [ ] `process.stdin.on("error", ...)` handler is registered before stdin reading begins
- [ ] Subprocess exits with a non-zero exit code immediately on stdin pipe error
- [ ] Error message is written to stderr so it is captured in Python-side subprocess logging
- [ ] No regression: normal stdin EOF still triggers the existing `"end"` handler and processing proceeds correctly
