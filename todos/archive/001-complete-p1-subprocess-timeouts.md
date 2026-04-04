---
status: complete
priority: p1
issue_id: "001"
tags: [code-review, performance, reliability]
dependencies: []
---

# P1 — Missing timeouts on LLM call and Node.js subprocess

## Problem Statement

Two `await` expressions in `presentation_export.py` have no timeout. Either one can hang
indefinitely, stalling the ReportCreation agent for all remaining patients in the meeting.
The Gunicorn worker timeout (600s) will eventually kill the worker, dropping all in-flight
conversations.

## Findings

**LLM call — `_summarize_for_slides`, line ~252:**
```python
response = await chat_service.get_chat_message_content(
    chat_history=chat_history, settings=settings   # no timeout
)
```
Azure OpenAI stalls during throttling, model cold starts, and transient network partitions.
A 15-patient meeting with one stalled call blocks all subsequent patients.

**Node.js subprocess — `export_to_pptx`, line ~188:**
```python
_, stderr = await proc.communicate(input=js_input.encode())  # no timeout
```
If PptxGenJS hangs (OOM, corrupt internal state, Node crash without stderr output), the
coroutine waits forever. The zombie Node process and open file descriptor both persist.
The `finally` block does NOT reap the process — only deletes the temp file.

## Proposed Solution

```python
# _summarize_for_slides — wrap LLM call
try:
    response = await asyncio.wait_for(
        chat_service.get_chat_message_content(chat_history=chat_history, settings=settings),
        timeout=90.0,
    )
except asyncio.TimeoutError:
    logger.warning("SlideContent LLM call timed out for patient %s", patient_id)
    # fall through to existing SlideContent fallback

# export_to_pptx — wrap subprocess communicate
try:
    _, stderr = await asyncio.wait_for(
        proc.communicate(input=js_input.encode()),
        timeout=60.0,
    )
except asyncio.TimeoutError:
    proc.kill()
    await proc.wait()
    return "Error generating PPTX: slide renderer timed out."
```

Also apply the same LLM timeout fix to `content_export.py` `_summarize_for_tumor_board_doc`.

## Acceptance Criteria
- [x] `_summarize_for_slides` raises/handles `asyncio.TimeoutError` within 90s
- [x] `proc.communicate` raises/handles `asyncio.TimeoutError` within 60s; process is killed and reaped
- [x] Same fix applied to `content_export.py`
- [x] Timeout values are constants at module level (not magic numbers inline)
