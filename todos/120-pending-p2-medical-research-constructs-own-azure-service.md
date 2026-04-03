---
status: pending
priority: p2
issue_id: "120"
tags: [code-review, architecture, reliability]
dependencies: []
---

# 120 — `MedicalResearchPlugin` bypasses kernel service registry with its own `AzureChatCompletion`

## Problem Statement

`MedicalResearchPlugin.__init__` instantiates its own `AzureChatCompletion` service with `service_id="research-synthesis"` directly from `os.environ`, bypassing the kernel's service registry and centralized credential management. This creates a second Azure OpenAI connection pool, hardcodes `api_version="2025-04-01-preview"`, unconditionally passes `temperature=0` at line 558 (which raises an error for reasoning models), and contains a stale comment referencing `gpt-5.4` which is not a real model identifier. All sibling export plugins use `self.kernel.get_service(service_id="default")`.

## Findings

- `medical_research.py:138-156` — direct `AzureChatCompletion(...)` instantiation in `__init__`; reads `os.environ` directly
- `medical_research.py:558` — unconditional `temperature=0` passed to reasoning-model-incompatible settings
- Stale `gpt-5.4` comment in the same file

## Proposed Solution

1. Remove the `AzureChatCompletion` instantiation block from `__init__`.
2. Retrieve the service from the kernel: `self._chat_service = self.kernel.get_service(service_id="default")` (matching the pattern in export plugins).
3. Replace the hardcoded `temperature=0` at line 558 with a `model_supports_temperature()` guard:

```python
settings = AzureChatPromptExecutionSettings()
if model_supports_temperature(self.kernel):
    settings.temperature = 0.0
```

4. Remove or correct the stale `gpt-5.4` comment.

## Acceptance Criteria

- [ ] `MedicalResearchPlugin.__init__` does not instantiate `AzureChatCompletion` directly
- [ ] The plugin retrieves its LLM service from `self.kernel.get_service(...)` like all sibling plugins
- [ ] `temperature=0` is only applied when `model_supports_temperature()` returns `True`
- [ ] No references to `gpt-5.4` or hardcoded `api_version` in this plugin
- [ ] Single Azure OpenAI connection pool used across all plugins
