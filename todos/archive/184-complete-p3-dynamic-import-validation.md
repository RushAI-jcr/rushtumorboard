---
status: pending
priority: p3
issue_id: "184"
tags: [code-review, security]
dependencies: []
---

# Dynamic Module Import Without Input Sanitization

## Problem Statement

`src/group_chat.py` line 242: `SCENARIO` environment variable and `tool_name` from agents.yaml are used directly in `importlib.import_module(f"scenarios.{scenario}.tools.{tool_name}")` without format validation.

## Findings

- **Source**: Security Sentinel (MEDIUM)
- **Evidence**: Line 242 — no regex validation on SCENARIO or tool_name
- **Existing mitigation**: `_validate_agent_config()` in config.py verifies module is importable at startup
- **Exploitability**: Low in production (env vars set by deployment infrastructure)

## Proposed Solutions

### Option A: Add regex validation (Recommended)
```python
import re
scenario = os.environ.get("SCENARIO")
if not re.match(r'^[a-z0-9_]+$', scenario or ''):
    raise ValueError(f"Invalid SCENARIO: {scenario}")
```
- **Effort**: Small (10 min)
- **Risk**: None

## Acceptance Criteria
- [ ] SCENARIO validated against allowlist or regex before import
- [ ] tool_name validated against ^[a-z0-9_]+$ pattern
