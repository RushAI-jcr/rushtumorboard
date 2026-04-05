---
status: complete
priority: p3
issue_id: "195"
tags: [code-review, security, python]
dependencies: []
---

# Env Var Resolver: Debug Logging + Optional Allowlist

## Problem Statement

`_resolve_env_vars_in_agents()` in `config.py` silently resolves unset env vars to empty strings. No logging. Also has no allowlist — any env var can be pulled into agent configs.

## Findings

**Flagged by:** Kieran Python Reviewer (logging), Security Sentinel (allowlist)

1. **No debug logging**: When `${VAR}` resolves to empty, there is no log output. Misconfigurations are invisible at startup.

2. **No allowlist**: Any env var (`PATH`, `AWS_SECRET_ACCESS_KEY`, etc.) could be pulled into agent config strings if someone added `${AWS_SECRET_ACCESS_KEY}` to agents.yaml. Low risk since agents.yaml is under source control.

## Proposed Solutions

### Logging (do this)
Add `logger.debug("Env var %s not set, resolving to empty", m.group(1))` when a var is unset.

### Allowlist (optional, defense-in-depth)
Restrict to `AZURE_OPENAI_*` prefix or explicit allowlist. Warn if other vars referenced.

## Acceptance Criteria

- [x] Debug log emitted when env var resolves to empty
- [ ] (Optional) Allowlist or prefix restriction on resolvable env vars — deferred, low risk since agents.yaml is source-controlled

## Work Log

- 2026-04-04: Created from code review (Python Reviewer + Security Sentinel)
- 2026-04-04: Fixed — Added logger.debug in _resolve_env_vars_in_agents when env var is unset
