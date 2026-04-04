---
status: complete
priority: p2
issue_id: "090"
tags: [code-review, reliability, architecture]
dependencies: []
---

# P2 — No retry on transient blob upload errors; `export_to_word_doc` blob write unguarded

## Problem Statement

Two issues: (1) The PPTX blob upload catches exceptions but returns immediately with no retry — a single transient Azure Storage HTTP 503 or connection reset loses the rendered PPTX permanently since the temp file is already deleted. (2) The Word document blob write in `content_export.py` has NO try/except at all — a storage failure propagates as an unhandled exception to the SK agent.

## Findings

**`presentation_export.py`, lines 237-248:** Catches `Exception`, logs, and returns error string. No retry. The bytes are in memory but the temp file is gone. Single failure point for a transient network error.

**`content_export.py`, line 251** (approximately):
```python
await self.data_access.chat_artifact_accessor.write(artifact)
```
Completely unguarded. An Azure Storage failure here becomes an unhandled exception in a `@kernel_function` method — same P1 propagation issue as todo 082, but for the Word doc.

Architecture agent: "The inconsistency between the two files is an architectural inconsistency."

## Proposed Solution

**Part A — Add try/except to content_export.py word doc write:**
```python
try:
    await self.data_access.chat_artifact_accessor.write(artifact)
except Exception as exc:
    logger.error("Word doc upload failed for conv=%s: %s", self.chat_ctx.conversation_id, type(exc).__name__)
    return "Word document was generated but could not be saved. Please try again."
```

**Part B — Add single retry to both:**
```python
async def _write_with_retry(accessor, artifact, max_attempts=2):
    for attempt in range(max_attempts):
        try:
            await accessor.write(artifact)
            return
        except Exception:
            if attempt == max_attempts - 1:
                raise
            await asyncio.sleep(1.0)
```

## Acceptance Criteria
- [ ] `content_export.py` blob write wrapped in try/except returning user-facing string
- [ ] Both export plugins attempt at least one retry on storage failure before returning error
- [ ] Retry delay is non-zero (prevents thundering-herd on storage throttle)
