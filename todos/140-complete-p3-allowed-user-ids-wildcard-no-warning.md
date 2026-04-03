---
status: complete
priority: p3
issue_id: "140"
tags: [code-review, security, access-control]
dependencies: []
---

# 140 — Wildcard `ADDITIONAL_ALLOWED_USER_IDS` active with no operator warning

## Problem Statement

`access_control_middleware.py:90-91` — when `ADDITIONAL_ALLOWED_USER_IDS` is set to `"*"`, the middleware silently grants access to any authenticated Teams user in the allowed tenant, bypassing per-user ACL entirely. No warning is emitted when this wildcard is active. An operator relying on logs or alerts to verify ACL configuration would have no indication that per-user access control is disabled. This setting could be inadvertently carried into production from a development `.env` file.

## Findings

- `src/bots/access_control_middleware.py:90-91` — wildcard check with no associated log warning

## Proposed Solution

Emit a prominent warning log at application startup (once, not per-request) when the wildcard is active:

```python
if settings.additional_allowed_user_ids == "*":
    logger.warning(
        "ADDITIONAL_ALLOWED_USER_IDS is set to wildcard '*' — "
        "per-user ACL is DISABLED. All tenant users have access."
    )
```

Place this check in the middleware `__init__` or in the application lifespan startup handler so it fires exactly once per process. Optionally, require an additional explicit `ALLOW_ALL_USERS=true` environment variable to be set alongside `"*"` to enable the wildcard, providing defense against accidental misconfiguration.

## Acceptance Criteria

- [ ] A `WARNING`-level log is emitted at startup when `ADDITIONAL_ALLOWED_USER_IDS == "*"`
- [ ] The warning message clearly states that per-user ACL is disabled
- [ ] The warning is logged once per process, not on every request
- [ ] No behavior change to the allow/deny logic itself
