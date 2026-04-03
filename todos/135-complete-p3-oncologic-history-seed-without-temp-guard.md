---
status: complete
priority: p3
issue_id: "135"
tags: [code-review, python, quality, reliability]
dependencies: []
---

# 135 — Oncologic history extractor uses `seed=42` without `temperature=0` guard

## Problem Statement

`oncologic_history_extractor.py:199` constructs `AzureChatPromptExecutionSettings(seed=42)` without setting `temperature=0` and without applying the `model_supports_temperature()` guard used elsewhere in the codebase. All other LLM calls either set `temperature=0` for GPT-4o or omit the parameter for reasoning models via that guard. On reasoning models, `seed` is silently ignored. When using GPT-4o, the deployment default temperature (~1.0) is inherited, making oncologic history extraction non-deterministic across identical inputs despite the intent of `seed=42`.

## Findings

- `oncologic_history_extractor.py:199` — `AzureChatPromptExecutionSettings(seed=42)` with no temperature or model guard

## Proposed Solution

Apply the `model_supports_temperature()` guard consistent with other LLM calls in the codebase:

```python
if model_supports_temperature():
    settings = AzureChatPromptExecutionSettings(seed=42, temperature=0.0)
else:
    settings = AzureChatPromptExecutionSettings()
```

Alternatively, use the forthcoming `make_structured_settings()` helper from todo 127 if that abstraction covers this call site.

## Acceptance Criteria

- [ ] `temperature=0.0` is applied when `model_supports_temperature()` returns `True`
- [ ] `seed=42` is preserved on models that support it
- [ ] Reasoning model path omits temperature (guard returns `False` → settings constructed without temperature)
- [ ] Oncologic history extraction is deterministic for identical inputs on GPT-4o
