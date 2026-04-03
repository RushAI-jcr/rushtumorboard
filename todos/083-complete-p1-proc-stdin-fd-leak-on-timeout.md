---
status: complete
priority: p1
issue_id: "083"
tags: [code-review, reliability, performance]
dependencies: []
---

# P1 — `proc.stdin` pipe not closed after timeout cancellation — FD leak

## Problem Statement

When `asyncio.wait_for` cancels `proc.communicate()` on timeout, the `proc.stdin` StreamWriter is never explicitly closed. The file descriptor remains open until Python garbage collects the process object. In a long-running Gunicorn/Uvicorn server handling multiple tumor board meetings, FD leaks accumulate and can exhaust the OS process's file descriptor limit.

## Findings

**`presentation_export.py`, lines 204-207:**
```python
except asyncio.TimeoutError:
    proc.kill()
    await proc.wait()
    return "Error generating PPTX: slide renderer timed out."
```

`proc.communicate()` cancellation does NOT close `proc.stdin`. The Node.js process was waiting for stdin EOF; `proc.kill()` (SIGKILL) terminates it, so Node does not hang. But `proc.stdin` — a live `asyncio.StreamWriter` — remains open. The StreamWriter wraps a pipe file descriptor. On Linux, each leaked FD consumes a slot in the process's file descriptor table (default limit 1024). A 15-patient meeting with one timeout per patient would leak 15 FDs.

Performance agent confirmed: this is a genuine file descriptor leak in production server scenarios.

Additionally, `proc.kill()` itself can raise `ProcessLookupError` in a race where the process exits between the timeout and the kill call. This unhandled exception would bypass the `return` statement.

## Proposed Solution

```python
except asyncio.TimeoutError:
    try:
        proc.kill()
    except ProcessLookupError:
        pass  # process already exited
    if proc.stdin and not proc.stdin.is_closing():
        proc.stdin.close()
    await proc.wait()
    return "Error generating PPTX: slide renderer timed out."
```

## Acceptance Criteria
- [ ] `proc.stdin.close()` called explicitly after `proc.kill()` on timeout path
- [ ] `proc.kill()` wrapped in `try/except ProcessLookupError` to handle race condition
- [ ] `await proc.wait()` still called to reap the process exit status
