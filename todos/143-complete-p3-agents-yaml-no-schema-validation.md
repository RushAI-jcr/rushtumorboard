---
status: complete
priority: p3
issue_id: "143"
tags: [code-review, architecture, reliability]
dependencies: []
---

# 143 — `agents.yaml` loaded without schema validation — typos surface as runtime `KeyError`

## Problem Statement

`config.py:83-85` loads `agents.yaml` with `yaml.safe_load()` and passes the raw dict to `group_chat.py`, where individual agent entries are accessed via `.get("name")`, `.get("tools")`, `.get("description")`, etc. If an agent entry contains a typo (e.g., `agent_name` instead of `name`, or `tool` instead of `tools`), the error is not surfaced at startup. Instead, it causes a `KeyError` or silent `None` during the first message that invokes the affected agent in production, often with no clear indication of where the misconfiguration is.

## Findings

- `src/config.py:83-85` — `yaml.safe_load()` with no post-load validation
- `src/group_chat.py` — multiple `.get()` calls on raw agent config dicts without validation

## Proposed Solution

Add a Pydantic model for agent entries and validate the loaded YAML at application startup:

```python
class AgentConfig(BaseModel):
    name: str
    description: str
    instructions: str
    tools: list[str] = []

    @field_validator("name", "description")
    @classmethod
    def non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must be non-empty")
        return v
```

After loading, validate each entry: `agents = [AgentConfig.model_validate(a) for a in raw_agents]`. Run this before any agent is instantiated so deployment fails fast on misconfiguration with a clear error message identifying the problematic entry.

## Acceptance Criteria

- [ ] `agents.yaml` contents validated against a schema at application startup
- [ ] Missing or empty `name` or `description` raises a clear error that identifies the offending agent entry
- [ ] Validation runs before any agent is instantiated — process does not start with invalid config
- [ ] The rest of `group_chat.py` consumes typed `AgentConfig` objects instead of raw dicts
