---
status: complete
priority: p2
issue_id: "118"
tags: [code-review, performance, reliability]
dependencies: []
---

# 118 — `MedicalReportExtractorBase._extract` has no LLM timeout

## Problem Statement

`MedicalReportExtractorBase._extract` in `medical_report_extractor.py:171` calls `chat_completion_service.get_chat_message_content(...)` with no `asyncio.wait_for` timeout. The Pathology, Radiology, and OncologicHistory extractor agents all inherit this base class. If Azure OpenAI is slow or unresponsive, the call hangs indefinitely, blocking the entire orchestration turn and preventing any agent response from being returned to the clinician. All sibling export tools consistently use `_LLM_TIMEOUT_SECS_STANDARD = 90.0` — this base class does not follow that pattern.

## Findings

- `medical_report_extractor.py:171` — `await chat_completion_service.get_chat_message_content(...)` with no timeout wrapper

## Proposed Solution

1. Add a module-level timeout constant: `_LLM_TIMEOUT_SECS = 90.0`
2. Wrap the LLM call with `asyncio.wait_for`:

```python
try:
    response = await asyncio.wait_for(
        chat_completion_service.get_chat_message_content(...),
        timeout=_LLM_TIMEOUT_SECS,
    )
except asyncio.TimeoutError:
    logger.warning("LLM extraction timed out after %.0fs", _LLM_TIMEOUT_SECS)
    return {"error": "LLM extraction timed out", "fields": {}}
```

3. Ensure the `asyncio.TimeoutError` handler returns a structured error dict consistent with other extraction error paths (not a bare string or `None`).

## Acceptance Criteria

- [ ] `_extract` wraps the LLM call in `asyncio.wait_for` with an explicit timeout
- [ ] `asyncio.TimeoutError` is caught and returns a structured error dict rather than hanging or propagating
- [ ] Timeout constant is defined at module level with a descriptive name (e.g., `_LLM_TIMEOUT_SECS`)
- [ ] Timeout value is consistent with the `90.0` second standard used in sibling export tools
