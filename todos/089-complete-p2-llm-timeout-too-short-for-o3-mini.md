---
status: complete
priority: p2
issue_id: "089"
tags: [code-review, performance, reliability]
dependencies: []
---

# P2 — 90s LLM timeout may be insufficient for o3-mini reasoning model under load

## Problem Statement

`_LLM_TIMEOUT_SECS = 90.0` is applied uniformly to both `content_export.py` and `presentation_export.py`. Azure OpenAI `o3-mini` uses chain-of-thought reasoning tokens internally. With a ~20KB input payload and structured output schema, o3-mini at P95 latency under load can exceed 90 seconds, causing silent fallback to degraded clinical content.

## Findings

Performance agent: "90 seconds is fine for GPT-4o but insufficient for reasoning models at P95 latency." The `model_supports_temperature()` branch already distinguishes reasoning vs. non-reasoning models at execution time — the same branch should control the timeout value.

Batch E2E solution (`docs/solutions/integration-issues/batch-e2e-validation-15-patients.md`) established that the full 10-agent pipeline requires 300s minimum; individual LLM calls for the export step can consume 50-90s for reasoning models.

The PPTX fallback `SlideContent` is clinically silent — there is no visible indicator in the slide deck that fallback content was used. A clinician may rely on a degraded presentation without knowing it. The Word doc fallback includes `"⚠ Export used LLM fallback"` in action_items; the PPTX has no equivalent.

## Proposed Solution

```python
# Use separate timeout for reasoning vs standard models
_LLM_TIMEOUT_SECS_STANDARD  = 90.0   # GPT-4o and similar
_LLM_TIMEOUT_SECS_REASONING = 150.0  # o3-mini, o3

# In _summarize_for_slides:
timeout = _LLM_TIMEOUT_SECS_REASONING if not model_supports_temperature() else _LLM_TIMEOUT_SECS_STANDARD
response = await asyncio.wait_for(..., timeout=timeout)
```

Also add a visible degradation indicator in the PPTX fallback:

```python
# In the SlideContent fallback return in presentation_export.py:
discussion_bullets=[
    "[FALLBACK] LLM summarization failed — verify all fields before presenting",
    all_data.get("treatment_plan", "No treatment plan")[:80],
    ...
],
```

## Acceptance Criteria
- [ ] Separate timeout constants for standard vs reasoning models
- [ ] PPTX fallback `SlideContent` includes a visible `[FALLBACK]` indicator in `discussion_bullets`
- [ ] Same timeout differentiation applied in `content_export.py`
