---
status: pending
priority: p2
issue_id: "127"
tags: [code-review, simplicity, quality]
dependencies: []
---

# 127 — `model_supports_temperature` guard pattern repeated 4+ times; one site omits it entirely

## Problem Statement

The pattern `if model_supports_temperature(): settings = AzureChatPromptExecutionSettings(temperature=0.0, ...) else: settings = AzureChatPromptExecutionSettings(...)` appears at least four times across `presentation_export.py`, `content_export.py`, `clinical_trials.py`, and `oncologic_history_extractor.py`. Every repeat must be updated if default settings change (e.g., adding `seed`, changing `max_tokens`). Worse, `oncologic_history_extractor.py:199` calls `AzureChatPromptExecutionSettings(seed=42)` without the temperature guard at all — on a reasoning model this will produce an API error that silently fails extraction.

## Findings

- `presentation_export.py:337-342` — temperature guard pattern (repeated)
- `content_export.py:404-409` — temperature guard pattern (repeated)
- `clinical_trials.py:130-133` — temperature guard pattern (repeated)
- `oncologic_history_extractor.py:199` — uses `seed=42` with no `model_supports_temperature()` guard

## Proposed Solution

Add a `make_structured_settings(response_format=None, **kwargs) -> AzureChatPromptExecutionSettings` helper to `utils/model_utils.py`:

```python
def make_structured_settings(
    kernel: Kernel,
    response_format=None,
    **kwargs,
) -> AzureChatPromptExecutionSettings:
    settings = AzureChatPromptExecutionSettings(response_format=response_format, **kwargs)
    if model_supports_temperature(kernel):
        settings.temperature = 0.0
    return settings
```

All four call sites are then reduced to one line. Fix `oncologic_history_extractor.py` to use this helper (removing the unguarded `seed=42`).

## Acceptance Criteria

- [ ] `make_structured_settings` helper exists in `utils/model_utils.py`
- [ ] All four call sites listed in Findings use the helper instead of the inline guard pattern
- [ ] `oncologic_history_extractor.py` no longer sets `seed=42` without a temperature guard
- [ ] Helper is covered by a unit test that verifies `temperature` is absent when `model_supports_temperature` returns `False`
