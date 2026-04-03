---
status: pending
priority: p3
issue_id: "142"
tags: [code-review, architecture, quality]
dependencies: []
---

# 142 — Azure OpenAI `api_version` hardcoded in multiple files with version skew in tests

## Problem Statement

The Azure OpenAI `api_version` string is hardcoded in at least three locations: `group_chat.py:127` (`"2025-04-01-preview"`), `medical_research.py:144` (`"2025-04-01-preview"`), and `test_local_agents.py:313` (`"2024-12-01-preview"`). The test file uses a different, older API version than production, meaning no test exercises the production API version's behavior. When Azure retires or changes a preview API, the version string must be updated in 3 or more files, and the likelihood of the test version being forgotten is high.

## Findings

- `group_chat.py:127` — `api_version="2025-04-01-preview"`
- `medical_research.py:144` — `api_version="2025-04-01-preview"`
- `src/tests/test_local_agents.py:313` — `api_version="2024-12-01-preview"` (different from production)

## Proposed Solution

Centralize the API version in `config.py` as a constant populated from an environment variable with a default:

```python
AZURE_OPENAI_API_VERSION: str = os.environ.get(
    "AZURE_OPENAI_API_VERSION", "2025-04-01-preview"
)
```

All other files import and use `settings.AZURE_OPENAI_API_VERSION` (or the equivalent constant). Remove all hardcoded version strings from non-config files. The test file uses the same import, ensuring test and production use the same version.

## Acceptance Criteria

- [ ] API version defined in exactly one place (`config.py` or `.env` default)
- [ ] `group_chat.py` and `medical_research.py` import the version from config
- [ ] `test_local_agents.py` uses the same version constant as production — no separate hardcoded string
- [ ] No hardcoded API version strings remain in non-config source files
