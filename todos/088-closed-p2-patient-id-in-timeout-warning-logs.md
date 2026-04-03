---
status: closed
priority: p2
issue_id: "088"
tags: [code-review, security, hipaa]
dependencies: []
---

# P2 — Raw `patient_id` logged in LLM TimeoutError warnings

## Problem Statement

Both export plugins log the raw `patient_id` in `asyncio.TimeoutError` warning messages. Under HIPAA, patient identifiers are PHI. The logging backend (Azure Monitor via OpenTelemetry) receives all logger output from the root logger. An opaque correlation ID (`conversation_id`) should be used instead.

## Findings

**`presentation_export.py`, lines 313-317:**
```python
except asyncio.TimeoutError:
    logger.warning(
        "SlideContent LLM call timed out for patient %s",
        all_data.get("patient_id", "Unknown"),
    )
```

**`content_export.py`, lines 419-424:**
```python
except asyncio.TimeoutError:
    logger.warning(
        "TumorBoardDocContent LLM call timed out for patient %s",
        all_data.get("patient_id", "Unknown"),
    )
```

`patient_id` in this system maps to Epic MRN-linked identifiers. It is a direct PHI identifier under HIPAA. The `conversation_id` (a UUID generated at session creation) is the appropriate non-PHI correlation token.

## Proposed Solution

Replace `patient_id` with `self.chat_ctx.conversation_id` in both warning messages:

```python
# presentation_export.py
except asyncio.TimeoutError:
    logger.warning(
        "SlideContent LLM call timed out (conv=%s)",
        self.chat_ctx.conversation_id,
    )

# content_export.py — same pattern
```

Note: `_summarize_for_slides` is a `@staticmethod` in the current code but accesses `all_data` — confirm `self.chat_ctx` is accessible (it may need to be an instance method or the conversation_id passed as parameter).

## Acceptance Criteria
- [ ] `patient_id` replaced with `conversation_id` in both TimeoutError warning logs
- [ ] Same fix applied to any other logger calls in the export plugins that use `patient_id`
